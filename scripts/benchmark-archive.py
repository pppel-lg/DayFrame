"""Synthetic 10,000-day archive benchmark. Never uses a personal archive."""
import argparse
import hashlib
import io
import json
import sys
import tempfile
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from backend.dayframe.archive import Archive, now


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=10000)
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix='dayframe-synthetic-benchmark-'))
    archive = Archive(root / 'archive')
    image = io.BytesIO()
    Image.new('RGB', (32, 40), '#587465').save(image, 'JPEG')
    raw = image.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    first = date(1999, 1, 1)
    timestamp = now()
    begin = time.perf_counter()
    for index in range(args.count):
        day = (first + timedelta(days=index)).isoformat()
        photo_id = str(uuid.uuid4())
        relative = f'photos/{day[:4]}/{day[5:7]}/{day}_{photo_id}.jpg'
        image_path = archive.safe_path(relative)
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(raw)
        sidecar = archive.entry_path(day)
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        entry = {'schema_version': 1, 'entry_id': str(uuid.uuid4()), 'record_date': day, 'status': 'recorded', 'primary_photo_id': photo_id, 'mood': 'calm', 'note': 'Synthetic benchmark fixture', 'tags': ['synthetic'], 'location': {}, 'photos': [{'photo_id': photo_id, 'relative_path': relative, 'sha256': digest, 'byte_size': len(raw), 'mime_type': 'image/jpeg', 'imported_at_utc': timestamp}], 'created_at_utc': timestamp, 'updated_at_utc': timestamp}
        sidecar.write_text(json.dumps(entry), encoding='utf-8')
    generated = time.perf_counter() - begin
    begin = time.perf_counter()
    rebuilt = archive.rebuild()
    rebuild_seconds = time.perf_counter() - begin
    assert rebuilt['entry_count'] == args.count and rebuilt['photo_count'] == args.count and not rebuilt['issues'], rebuilt
    last = first + timedelta(days=args.count-1)
    begin = time.perf_counter()
    page = archive.entries(start=(last-timedelta(days=30)).isoformat(), end=last.isoformat(), limit=31)
    calendar_seconds = time.perf_counter() - begin
    assert len(page['entries']) == 31
    begin = time.perf_counter()
    stats = archive.stats(f'{last.year}-01-01', last.isoformat(), last.isoformat())
    stats_seconds = time.perf_counter() - begin
    assert stats['recorded_days'] > 0
    print(json.dumps({'fixture': str(root), 'days': args.count, 'photos': args.count, 'fixture_generation_seconds': round(generated, 3), 'index_rebuild_seconds': round(rebuild_seconds, 3), 'month_query_seconds': round(calendar_seconds, 3), 'year_statistics_seconds': round(stats_seconds, 3), 'result': 'PASS'}, indent=2))


if __name__ == '__main__':
    main()
