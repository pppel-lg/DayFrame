"""Offline exports: escaped metadata and embedded derived images, never GPS."""
import base64
import calendar
import csv
import html
import io
import os
import shutil
import subprocess
import sys
import uuid
from datetime import date
from pathlib import Path

from PIL import Image, ImageOps

from .archive import atomic_bytes, local_date


def esc(value):
    return html.escape(str(value), quote=True)


def thumbnail_data(archive, photo_id):
    try:
        raw = archive.thumbnail(photo_id).read_bytes()
        return 'data:image/jpeg;base64,' + base64.b64encode(raw).decode('ascii')
    except (OSError, KeyError, ValueError):
        return ''


def document(title, content):
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>body{{font:16px system-ui,sans-serif;background:#f8f7f3;color:#292d29;max-width:1100px;margin:40px auto;padding:24px}}h1{{font:40px Georgia,serif}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:16px}}article{{background:white;padding:16px;border:1px solid #ddd;border-radius:12px}}img{{width:100%;height:170px;object-fit:cover}}.note{{white-space:pre-wrap}}@media print{{article{{break-inside:avoid}}}}</style><h1>{esc(title)}</h1>{content}</html>'''


def export_calendar(archive, year, progress=None):
    entries = {e['record_date']: e for e in archive.entries(start=f'{year:04d}-01-01', end=f'{year:04d}-12-31', limit=100000)['entries']}
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['date', 'status', 'mood', 'location', 'original_relative_path', 'missing'])
    cards = []
    total_days = 366 if calendar.isleap(year) else 365
    for ordinal in range(total_days):
        from datetime import timedelta
        day = (date(year, 1, 1)+timedelta(days=ordinal)).isoformat()
        entry = entries.get(day)
        status, mood, location, path, missing, image = 'empty', '', '', '', '', ''
        if entry:
            status, mood = entry['status'], entry['mood']
            location = entry['location']['label'] or entry['location']['city']
            photo = next((p for p in entry['photos'] if p['photo_id'] == entry['primary_photo_id']), None)
            if photo:
                path, missing = photo['relative_path'], photo['missing']
                if not missing:
                    image = thumbnail_data(archive, photo['photo_id'])
                else:
                    status = 'missing photo'
        # Prefix spreadsheet formula-like cells. Ordinary CSV consumers retain
        # explicit text while Excel cannot evaluate user diary/location content.
        cells = [day, status, mood, location, path, missing]
        writer.writerow(["'"+c if isinstance(c, str) and c.startswith(('=', '+', '-', '@', '\t', '\r')) else c for c in cells])
        cards.append(f'<article><b>{day}</b><p>{esc(status)} · {esc(mood)}</p>' + (f'<img alt="{day}" src="{image}">' if image else '') + f'<p>{esc(location)}</p></article>')
        if progress:
            progress(ordinal*95/total_days)
    html_relative = f'calendar/{year}.html'
    atomic_bytes(archive.safe_path('exports/'+html_relative), document(f'Dayframe · {year} 日历', '<div class="grid">'+''.join(cards)+'</div>').encode('utf8'))
    atomic_bytes(archive.safe_path(f'exports/calendar/{year}.csv'), ('\ufeff'+stream.getvalue()).encode('utf8'))
    return {'url': '/api/exports/'+html_relative, 'csv_url': f'/api/exports/calendar/{year}.csv'}


def report(archive, year, include_notes=False, progress=None):
    entries = archive.entries(start=f'{year:04d}-01-01', end=f'{year:04d}-12-31', limit=100000)['entries']
    stats = archive.stats(f'{year:04d}-01-01', f'{year:04d}-12-31')
    cities = {}
    for entry in entries:
        city = entry['location']['city'] or entry['location']['label']
        if city:
            cities[city] = cities.get(city, 0)+1
    content = f'<p>记录 {stats["recorded_days"]} 天 · 记录率 {stats["recording_rate"]:.1%} · 照片 {stats["photo_count"]} 张</p>'
    content += '<h2>地点</h2><p>'+esc(' / '.join(f'{k} ({v})' for k, v in cities.items()))+'</p>'
    content += '<h2>自填心情</h2><p>'+esc(' / '.join(f'{m["mood"]} ({m["count"]})' for m in stats['moods']))+'</p><h2>十二个月</h2><div class="grid">'
    for month in range(1, 13):
        candidates = [e for e in entries if int(e['record_date'][5:7]) == month and e['status'] == 'recorded' and any(p['photo_id'] == e['primary_photo_id'] and not p['missing'] for p in e['photos'])]
        entry = candidates[-1] if candidates else None
        content += f'<article><b>{month} 月</b>'
        if entry:
            content += f'<p>{esc(entry["record_date"])}</p><img alt="{esc(entry["record_date"])}" src="{thumbnail_data(archive, entry["primary_photo_id"])}">'
            if include_notes:
                content += '<p class="note">'+esc(entry['note'])+'</p>'
        else:
            content += '<p>暂无记录</p>'
        content += '</article>'
        if progress:
            progress(month*95/12)
    content += '</div><p>此报告未包含精准坐标。记录率以归档开始日至今天为边界。可使用浏览器打印另存 PDF。</p>'
    relative = f'reports/{year}-{uuid.uuid4().hex[:8]}.html'
    atomic_bytes(archive.safe_path('exports/'+relative), document(f'Dayframe · {year} 年度报告', content).encode('utf8'))
    return {'url': '/api/exports/'+relative, 'stats': stats}


def ffmpeg_binary():
    explicit = os.environ.get('DAYFRAME_FFMPEG')
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise ValueError('configured FFmpeg is unavailable; check DAYFRAME_FFMPEG')
        return str(path)
    if getattr(sys, '_MEIPASS', None):
        path = Path(sys._MEIPASS) / 'bin' / 'ffmpeg.exe'
        if path.is_file():
            return str(path)
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise ValueError('FFmpeg is unavailable; install a build with the libx264 encoder, then retry')
    return ffmpeg


def video(archive, start, end, fps=5, progress=None):
    ffmpeg = ffmpeg_binary()
    start, end = local_date(start), local_date(end)
    if start > end:
        raise ValueError('start must not exceed end')
    entries = archive.entries(start=start, end=end, limit=100000)['entries'][::-1]
    photos = [next((p for p in e['photos'] if p['photo_id'] == e['primary_photo_id'] and not p['missing'] and not p['trashed_at_utc']), None) for e in entries if e['status'] == 'recorded']
    photos = [p for p in photos if p]
    if not photos:
        raise ValueError('no valid primary photos in selected range')
    staging = archive.safe_path('cache/video-'+uuid.uuid4().hex)
    staging.mkdir()
    relative = 'videos/'+uuid.uuid4().hex+'.mp4'
    destination = archive.safe_path('exports/'+relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix('.partial.mp4')
    process = None
    try:
        for index, photo in enumerate(photos):
            if progress:
                progress(index*70/len(photos))
            with Image.open(archive.safe_path(photo['relative_path'])) as image:
                frame = ImageOps.pad(ImageOps.exif_transpose(image).convert('RGB'), (720, 960), color='black')
                frame.save(staging / f'{index:06d}.jpg', quality=92)
        command = [ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-framerate', str(fps), '-i', str(staging / '%06d.jpg'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-y', str(partial)]
        with (staging / 'ffmpeg.log').open('wb') as log:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            import time
            while process.poll() is None:
                if progress:
                    progress(80)
                time.sleep(.15)
            if process.returncode:
                raise ValueError('FFmpeg encoding failed: '+(staging / 'ffmpeg.log').read_text(errors='replace')[-1500:])
        os.rename(partial, destination)
        return {'url': '/api/exports/'+relative, 'frame_count': len(photos), 'missing_day_policy': 'skip', 'fps': fps}
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        partial.unlink(missing_ok=True)
        shutil.rmtree(staging)
