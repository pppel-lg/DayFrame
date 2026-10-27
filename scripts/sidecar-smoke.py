"""Run the packaged backend, not development Python, against synthetic archives."""
import argparse
import base64
from datetime import date
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import queue
import secrets
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request


def launch(executable, data_home, log):
    token = secrets.token_urlsafe(32)
    env = dict(os.environ, DAYFRAME_DATA_HOME=str(data_home))
    for key in ['FRONTEND_DIST', 'DAYFRAME_FFMPEG', 'PYTHONPATH', 'PYTHONHOME']:
        env.pop(key, None)
    process = subprocess.Popen([str(executable)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env,
        stderr=log, text=True, encoding='utf8', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    process.stdin.write(json.dumps({'token': token, 'data_home': str(data_home)}) + '\n')
    process.stdin.flush()
    ready = queue.Queue()
    threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True).start()
    try:
        line = ready.get(timeout=90)
        assert line.startswith('DAYFRAME_READY '), 'Packaged sidecar failed before readiness (see log)'
        port = json.loads(line.split(' ', 1)[1])['port']
        base = f'http://127.0.0.1:{port}'
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        client.open(base + '/desktop/launch?token=' + token, timeout=10).read()
        return process, base, client
    except BaseException:
        process.stdin.close()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        raise


def call(client, base, path, body=None, method=None, content_type='application/json'):
    if body is not None and not isinstance(body, bytes):
        body = json.dumps(body).encode()
    request = urllib.request.Request(base + path, body, method=method, headers={'Origin': base, 'Content-Type': content_type})
    with client.open(request, timeout=30) as response:
        raw = response.read()
        return json.loads(raw) if 'application/json' in response.headers.get('Content-Type', '') else raw


def job(client, base, kind, **fields):
    job_id = call(client, base, '/api/jobs', {'kind': kind, **fields})['job_id']
    for _ in range(300):
        value = call(client, base, '/api/jobs/' + job_id)
        if value['status'] == 'success':
            return value['result']
        assert value['status'] not in ('failed', 'cancelled'), value
        time.sleep(.1)
    raise AssertionError('packaged job timed out: ' + kind)


def stop(process, base):
    process.stdin.close()
    assert process.wait(timeout=20) == 0
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', int(base.rsplit(':', 1)[1]))) != 0, 'sidecar port survived close'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('artifacts/sidecar-smoke'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='DayFrame 中文 smoke ') as temporary, (args.output / 'sidecar.log').open('w', encoding='utf8') as log:
        data_home = Path(temporary) / '独立测试 data'
        # Occupying the historical fixed port cannot break port-0 startup.
        occupied = socket.socket()
        try:
            occupied.bind(('127.0.0.1', 8765))
            occupied.listen()
        except OSError:
            occupied.close()
        process, base, client = launch(args.executable.resolve(), data_home, log)
        try:
            assert b'<html' in call(client, base, '/').lower()
            day = date.today().isoformat()
            png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGOMKEllwAaYsIoOWgkA8uEBQa+UvQwAAAAASUVORK5CYII=')
            boundary = 'dayframe-packaged-smoke'
            raw = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="test.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + png + f'\r\n--{boundary}--\r\n'.encode())
            entry = call(client, base, f'/api/entries/{day}/photos', raw, content_type=f'multipart/form-data; boundary={boundary}')
            call(client, base, '/api/entries/' + day, {'note': '打包后原图与日记持久化', 'mood': 'happy', 'tags': ['smoke'], 'location': {'label': '台北', 'city': '台北', 'precision': 'city'}}, 'PUT')
            assert call(client, base, f'/api/photos/{entry["primary_photo_id"]}?download=true') == png
            assert not job(client, base, 'verify')['issues']
            job(client, base, 'rebuild')
            backup = job(client, base, 'backup')
            assert call(client, base, '/api/restore', {'name': backup['name'], 'target_name': 'packaged-restored', 'confirmed': True})['entry_count'] == 1
            for kind in ['export_calendar', 'report']:
                value = job(client, base, kind, year=int(day[:4]))
                assert b'data:image/jpeg;base64,' in call(client, base, value['url'])
                if kind == 'export_calendar':
                    assert b'original_relative_path' in call(client, base, value['csv_url'])
            value = job(client, base, 'video', start=day, end=day, fps=2)
            assert b'ftyp' in call(client, base, value['url'])[:32]
        finally:
            stop(process, base)
            occupied.close()
        process, base, client = launch(args.executable.resolve(), data_home, log)
        try:
            saved = call(client, base, '/api/entries/' + day)
            assert saved['note'] == '打包后原图与日记持久化'
            assert hashlib.sha256(call(client, base, f'/api/photos/{saved["primary_photo_id"]}?download=true')).hexdigest() == hashlib.sha256(png).hexdigest()
        finally:
            stop(process, base)
    print('Packaged sidecar PASS: loopback/random port, Chinese path, import bytes, metadata, verify/reindex, backup/restore, HTML/CSV/MP4, close/reopen persistence')


if __name__ == '__main__':
    main()
