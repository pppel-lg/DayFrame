"""Install and exercise the actual NSIS application using isolated synthetic data.

WebView2 remote debugging is enabled only for this explicitly instrumented test.
No private archive, development server, Python sidecar or globally installed codec
is used by the installed application.
"""
import argparse
import base64
import ctypes
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request

from playwright.sync_api import expect, sync_playwright

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGOMKEllwAaYsIoOWgkA8uEBQa+UvQwAAAAASUVORK5CYII=')


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def wait_for(check, timeout=100, label='condition'):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(.15)
    raise AssertionError('Timed out: ' + label)


def read_status(path):
    try:
        value = json.loads(path.read_text(encoding='utf8'))
        if value.get('state') == 'failed':
            raise AssertionError(value.get('message', 'native startup failed'))
        return value if value.get('state') == 'ready' else None
    except (OSError, json.JSONDecodeError):
        return None


def cdp_ready(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version', timeout=1) as response:
            return json.load(response).get('webSocketDebuggerUrl')
    except OSError:
        return None


def close_window(process):
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    handles = []
    @callback_type
    def collect(window, _):
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(window), ctypes.byref(pid))
        if pid.value == process.pid and user32.IsWindowVisible(ctypes.c_void_p(window)):
            handles.append(window)
        return True
    user32.EnumWindows(collect, 0)
    assert handles, 'Installed app has no visible native window'
    for window in handles:
        user32.PostMessageW(ctypes.c_void_p(window), 0x0010, 0, 0)
    assert process.wait(timeout=30) == 0, 'Native app did not exit cleanly'


def port_closed(port):
    with socket.socket() as probe:
        probe.settimeout(.2)
        return probe.connect_ex(('127.0.0.1', port)) != 0


def api(page, path, payload=None, method='GET'):
    return page.evaluate('''async ({path,payload,method}) => {
      const r=await fetch('/api'+path,{method,credentials:'same-origin',
        ...(payload===null?{}:{body:JSON.stringify(payload),headers:{'Content-Type':'application/json'}})});
      if(!r.ok)throw Error('API '+r.status+' '+await r.text());return r.json();
    }''', {'path': path, 'payload': payload, 'method': method})


def job(page, kind, **fields):
    job_id = api(page, '/jobs', {'kind': kind, **fields}, 'POST')['job_id']
    def result():
        value = api(page, '/jobs/' + job_id)
        assert value['status'] not in ('failed', 'cancelled'), value
        return value.get('result') if value['status'] == 'success' else None
    return wait_for(result, timeout=90, label=kind)


def launch(executable, home, status_path, debug_port):
    if status_path.exists():
        status_path.unlink()
    env = dict(os.environ, DAYFRAME_DATA_HOME=str(home), DAYFRAME_SMOKE_STATUS=str(status_path), DAYFRAME_TEST_DEBUG_PORT=str(debug_port))
    # The installed app must find all of its own runtimes and codecs.
    env['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
    for key in ['PYTHONHOME', 'PYTHONPATH', 'FRONTEND_DIST', 'DAYFRAME_FFMPEG']:
        env.pop(key, None)
    process = subprocess.Popen([str(executable)], env=env, cwd=executable.parent)
    try:
        value = wait_for(lambda: read_status(status_path), label='installed app readiness')
        wait_for(lambda: cdp_ready(debug_port), label='WebView2 debug target')
        return process, value
    except BaseException:
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--installer', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('artifacts/windows-smoke'))
    args = parser.parse_args()
    if os.name != 'nt':
        raise SystemExit('Installed-app smoke requires Windows.')
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    results = {'installer': args.installer.name, 'checks': [], 'errors': [], 'external_requests': []}
    install = Path(tempfile.gettempdir()) / ('DayFrameInstall-' + str(os.getpid()))
    home = args.output / '全新用户 data'
    status_path = args.output / 'native-status.json'
    # NSIS /D is last. This unique temporary target contains no user installation.
    subprocess.run([str(args.installer.resolve()), '/S', '/D=' + str(install)], check=True, timeout=240)
    executable = install / 'dayframe.exe'
    assert executable.is_file(), 'Installer did not install the real application'
    assert (install / 'dayframe-server.exe').is_file(), 'Installer omitted the packaged Python sidecar'
    results['checks'].append('silent current-user NSIS installation with embedded sidecar')
    occupied = socket.socket()
    try:
        occupied.bind(('127.0.0.1', 8765))
        occupied.listen()
    except OSError:
        occupied.close()
    process = None
    try:
        port = free_port()
        process, status = launch(executable, home, status_path, port)
        backend_port = status['port']
        results['checks'].append('native launch + bundled backend with historical port 8765 occupied')
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
            context = browser.contexts[0]
            page = wait_for(lambda: next((p for p in context.pages if p.url.startswith(f'http://127.0.0.1:{backend_port}/')), None), label='real React webview')
            page.on('pageerror', lambda error: results['errors'].append(str(error)))
            page.on('request', lambda request: results['external_requests'].append(request.url) if request.url.startswith(('http://', 'https://')) and not request.url.startswith((f'http://127.0.0.1:{backend_port}/', 'http://ipc.localhost/')) else None)
            expect(page.locator('main h1')).to_be_visible(timeout=30000)
            assert page.title().lower().startswith('dayframe')
            assert page.evaluate('!!window.__TAURI_INTERNALS__'), 'This must be the installed Tauri webview'
            expect(page.locator('nav[aria-label="主导航"] a')).to_have_count(8)
            results['checks'].append('actual installed WebView2 renders React and all 8 navigation items')
            page.screenshot(path=str(args.output / 'installed-today-empty.png'))
            day = date.today().isoformat()
            page.locator('input[type=file]').first.set_input_files({'name': 'synthetic.png', 'mimeType': 'image/png', 'buffer': PNG})
            wait_for(lambda: api(page, '/entries?start=' + day + '&end=' + day)['entries'], label='UI import persisted')
            # Save through visible controls; names are stable accessibly-labelled UI fields.
            note_field = page.get_by_label('日记', exact=True)
            note_field.fill('Windows 安装验收 · 日记持久化')
            page.get_by_label('城市', exact=True).fill('台北')
            page.get_by_label('标签', exact=True).fill('验收, 离线')
            page.get_by_role('button', name='开心', exact=True).click()
            page.get_by_role('button', name='保存记录', exact=True).click()
            wait_for(lambda: api(page, '/entries/' + day)['note'] == 'Windows 安装验收 · 日记持久化', label='UI metadata save')
            entry = api(page, '/entries/' + day)
            assert entry['tags'] == ['验收', '离线'] and entry['location']['city'] == '台北'
            original = page.evaluate('''async id=>Array.from(new Uint8Array(await (await fetch('/api/photos/'+id+'?download=true')).arrayBuffer()))''', entry['primary_photo_id'])
            assert bytes(original) == PNG
            results['checks'].append('UI photo import + exact original bytes, diary, mood, city and tags')
            page.screenshot(path=str(args.output / 'installed-today-saved.png'))
            # Camera uses WebView2's synthetic media device; physical hardware remains manual QA.
            page.get_by_role('button', name='再拍一张', exact=True).click()
            wait_for(lambda: page.locator('video').count() and page.locator('video').evaluate('(v)=>v.readyState>=2'), label='WebView2 synthetic camera permission and video')
            capture = page.get_by_role('button', name='拍下今天', exact=True)
            capture.click()
            page.get_by_role('button', name='保存今天的一帧', exact=True).click()
            wait_for(lambda: len(api(page, '/entries/' + day)['photos']) == 2, label='camera photo persisted')
            results['checks'].append('WebView2 synthetic camera permission, preview, capture and save')
            for route in ['calendar', 'timeline', 'memories', 'locations', 'letters', 'report', 'settings']:
                page.goto(f'http://127.0.0.1:{backend_port}/#{route}')
                expect(page.locator('main h1')).to_be_visible()
                expect(page.locator('.loading')).to_have_count(0, timeout=30000)
                page.screenshot(path=str(args.output / ('installed-' + route + '.png')))
            page.goto(f'http://127.0.0.1:{backend_port}/#timeline')
            search = page.get_by_placeholder('搜索日记与地点')
            if search.count():
                search.fill('Windows 安装验收')
                page.get_by_role('button', name='筛选', exact=True).click()
                expect(page.locator('.timeline-card')).to_have_count(1)
            letter = api(page, '/letters', {'title': '安装验收未来信', 'content': '到期前不应显示的正文', 'created_on_date': day, 'unlock_date': (date.today()+timedelta(days=1)).isoformat()}, 'POST')
            assert letter
            locked = api(page, '/letters?today=' + day)['letters'][0]
            assert locked['locked'] and 'content' not in locked
            assert api(page, '/letters?today=' + (date.today()+timedelta(days=1)).isoformat())['letters'][0]['content'] == '到期前不应显示的正文'
            assert api(page, '/stats?today=' + day)['recorded_days'] == 1
            assert not job(page, 'verify')['issues']
            job(page, 'rebuild')
            backup = job(page, 'backup')
            assert api(page, '/restore', {'name': backup['name'], 'target_name': 'installed-restored', 'confirmed': True}, 'POST')['entry_count'] == 1
            for kind in ['export_calendar', 'report']:
                exported = job(page, kind, year=int(day[:4]))
                content = page.evaluate('async path=>(await fetch(path)).text()', exported['url'])
                assert '<html' in content and 'data:image/jpeg;base64,' in content
                if kind == 'export_calendar':
                    assert 'original_relative_path' in page.evaluate('async path=>(await fetch(path)).text()', exported['csv_url'])
                else:
                    # This verifies HTML printability; the physical WebView2 print dialog remains manual QA.
                    pdf_browser = playwright.chromium.launch()
                    pdf_page = pdf_browser.new_page()
                    pdf_page.set_content(content, wait_until='load')
                    pdf_page.pdf(path=str(args.output / 'annual-report.pdf'))
                    pdf_browser.close()
            movie = job(page, 'video', start=day, end=day, fps=2)
            magic = page.evaluate('async path=>Array.from(new Uint8Array(await (await fetch(path)).arrayBuffer()).slice(0,32))', movie['url'])
            assert b'ftyp' in bytes(magic)
            results['checks'].append('calendar/timeline/memories/locations/letters/report/settings; locked letters, stats, integrity, reindex, verified backup/restore, HTML/CSV, Chromium PDF printability, FFmpeg MP4')
            assert not results['errors'], results['errors']
            assert not results['external_requests'], results['external_requests']
            close_window(process)
            process = None
        wait_for(lambda: port_closed(backend_port), label='backend port released after native window close')
        results['checks'].append('native window close terminates sidecar and releases listening port')
        port = free_port()
        process, status = launch(executable, home, status_path, port)
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
            page = wait_for(lambda: next((p for p in browser.contexts[0].pages if p.url.startswith(f'http://127.0.0.1:{status["port"]}/')), None), label='reopened webview')
            expect(page.locator('main h1')).to_be_visible()
            entry = api(page, '/entries/' + day)
            assert entry['note'] == 'Windows 安装验收 · 日记持久化' and len(entry['photos']) == 2
            duplicate = subprocess.Popen([str(executable)], env=dict(os.environ, DAYFRAME_DATA_HOME=str(home)))
            assert duplicate.wait(timeout=15) == 0, 'Duplicate launch must focus original and exit'
            close_window(process)
            process = None
        assert (home / 'Archive' / 'archive.json').is_file()
        # Reinstall the real package, then uninstall it, preserving the independent data root.
        subprocess.run([str(args.installer.resolve()), '/S', '/D=' + str(install)], check=True, timeout=240)
        assert (home / 'Archive' / 'archive.json').is_file()
        uninstaller = next(install.glob('*ninstall*.exe'), None)
        assert uninstaller, 'Uninstaller missing'
        subprocess.run([str(uninstaller), '/S'], check=True, timeout=120)
        assert (home / 'Archive' / 'archive.json').is_file()
        results['checks'].append('reopen persistence, duplicate-instance protection, reinstall and uninstall preserve archive')
        results['passed'] = True
    finally:
        if process is not None and process.poll() is None:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
        occupied.close()
        (args.output / 'acceptance.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf8')
    print('Installed Windows acceptance PASS (' + str(len(results['checks'])) + ' check groups)')


if __name__ == '__main__':
    main()
