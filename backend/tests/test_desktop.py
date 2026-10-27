"""Desktop contracts use disposable archives and exercise the actual HTTP process."""
import importlib
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.dayframe.main import create_app


def desktop_module():
    return importlib.import_module('backend.dayframe.desktop')


def launch(client, token='isolated-test-launch-secret'):
    response = client.get('/desktop/launch', params={'token': token}, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert response.headers['location'] == '/'
    return response


@pytest.fixture
def desktop_client(tmp_path, monkeypatch):
    monkeypatch.delenv('DAYFRAME_DATA_HOME', raising=False)
    app = desktop_module().create_desktop_app('isolated-test-launch-secret', tmp_path / '桌面 home')
    with TestClient(app) as client:
        yield client


def test_default_home_is_outside_install_and_environment_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'Local AppData'))
    monkeypatch.delenv('DAYFRAME_DATA_HOME', raising=False)
    config = desktop_module().DesktopConfig()
    assert config.paths == {
        'archive': str(tmp_path / 'Local AppData' / 'DayFrame' / 'Archive'),
        'backups': str(tmp_path / 'Local AppData' / 'DayFrame' / 'Backups'),
    }
    assert config.logs == tmp_path / 'Local AppData' / 'DayFrame' / 'Logs'
    monkeypatch.setenv('DAYFRAME_DATA_HOME', str(tmp_path / '测试 data home'))
    override = desktop_module().DesktopConfig(tmp_path / 'ignored')
    assert override.paths['archive'] == str(tmp_path / '测试 data home' / 'Archive')


@pytest.mark.parametrize('invalid_home', ['', False, 0, [], {}])
def test_invalid_explicit_home_cannot_silently_open_the_default_archive(tmp_path, monkeypatch, invalid_home):
    monkeypatch.delenv('DAYFRAME_DATA_HOME', raising=False)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'never open default'))
    with pytest.raises(ValueError, match='directory'):
        desktop_module().DesktopConfig(invalid_home)
    assert not (tmp_path / 'never open default').exists()


def test_all_desktop_private_gets_require_bootstrap(desktop_client):
    assert desktop_client.get('/health').json() == {'status': 'ok', 'version': '1.0.0'}
    assert not desktop_client.cookies
    for path in ['/', '/api/status', '/api/settings', '/api/desktop', '/api/exports/private.html', '/assets/app.js']:
        assert desktop_client.get(path).status_code == 401, path
    assert not desktop_client.cookies


def test_bootstrap_cookie_is_http_only_single_use_and_protects_mutations(desktop_client):
    assert desktop_client.get('/desktop/launch?token=wrong').status_code == 403
    response = launch(desktop_client)
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    assert 'isolated-test-launch-secret' not in cookie
    assert desktop_client.get('/api/status').status_code == 200
    assert desktop_client.get('/desktop/launch?token=isolated-test-launch-secret', follow_redirects=False).status_code == 403
    assert desktop_client.put('/api/settings', json={'mirror_preview': False}, headers={'Origin': 'https://evil.test'}).status_code == 403
    assert desktop_client.put('/api/settings', json={'mirror_preview': False}, headers={'Origin': 'http://testserver'}).status_code == 200
    assert desktop_client.get('/api/status', headers={'Host': 'evil.test'}).status_code == 403
    desktop_client.cookies.clear()
    assert desktop_client.put('/api/settings', json={'mirror_preview': True}).status_code == 401


def test_malformed_bootstrap_token_is_rejected_without_server_error(desktop_client):
    response = desktop_client.get('/desktop/launch', params={'token': '错误令牌'})
    assert response.status_code == 403
    launch(desktop_client)


def test_normal_mode_keeps_health_and_has_no_desktop_routes(tmp_path, monkeypatch):
    frontend = tmp_path / 'frontend'
    frontend.mkdir()
    (frontend / 'index.html').write_text('<h1>SPA</h1>', encoding='utf8')
    monkeypatch.setenv('FRONTEND_DIST', str(frontend))
    with TestClient(create_app(tmp_path / 'archive', tmp_path / 'backups')) as client:
        assert client.get('/health').json() == {'status': 'ok', 'version': '1.0.0'}
        assert client.get('/api/desktop').status_code == 404
        assert client.put('/api/desktop/paths', json={}).status_code == 404
        assert client.get('/desktop/launch?token=anything').status_code == 404


def test_export_artifacts_download_with_original_filenames(desktop_client):
    from backend.dayframe.exports import export_calendar
    launch(desktop_client)
    archive = desktop_client.app.state.archive
    calendar = export_calendar(archive, 2026)
    # The transport must preserve an encoder-produced file without interpreting it.
    movie = archive.safe_path('exports/videos/2026-memory.mp4')
    movie.parent.mkdir(parents=True)
    movie.write_bytes(b'\x00\x00\x00\x18ftypmp42video-transport-fixture')
    for url, filename in [(calendar['url'], '2026.html'), (calendar['csv_url'], '2026.csv'), ('/api/exports/videos/2026-memory.mp4', '2026-memory.mp4')]:
        response = desktop_client.get(url)
        assert response.status_code == 200
        assert response.headers['content-disposition'] == f'attachment; filename="{filename}"'
        assert response.content == archive.safe_path('exports/' + url.removeprefix('/api/exports/')).read_bytes()


def test_path_change_persists_chinese_spaces_but_only_applies_on_restart(desktop_client, tmp_path):
    launch(desktop_client)
    before = desktop_client.get('/api/desktop').json()
    assert before['desktop'] is True and before['pending_restart'] is False
    paths = {'archive': str(tmp_path / '新 归档'), 'backups': str(tmp_path / '新 备份')}
    saved = desktop_client.put('/api/desktop/paths', json=paths)
    assert saved.status_code == 200, saved.text
    assert saved.json()['pending_restart'] is True
    assert desktop_client.get('/api/status').json()['archive_path'] == before['paths']['archive']
    assert (Path(before['paths']['archive']) / 'archive.json').is_file()
    assert not (Path(paths['archive']) / 'archive.json').exists()
    reloaded = desktop_module().DesktopConfig(tmp_path / '桌面 home')
    assert reloaded.paths == paths
    assert reloaded.status()['pending_restart'] is False
    assert not list((tmp_path / '桌面 home' / 'Settings').glob('*.tmp'))


@pytest.mark.parametrize('kind', ['relative', 'same', 'nested', 'reverse-nested', 'settings', 'unrelated', 'invalid-version', 'malformed', 'file'])
def test_path_validation_preserves_previous_config(desktop_client, tmp_path, kind):
    launch(desktop_client)
    initial = desktop_client.get('/api/desktop').json()
    archive, backups = tmp_path / 'candidate', tmp_path / 'backup candidate'
    if kind == 'relative':
        archive = Path('relative-folder')
    elif kind == 'same':
        backups = archive
    elif kind == 'nested':
        backups = archive / 'backups'
    elif kind == 'reverse-nested':
        archive = backups / 'archive'
    elif kind == 'settings':
        archive = tmp_path / '桌面 home' / 'Settings'
    elif kind == 'unrelated':
        archive.mkdir()
        (archive / 'keep.txt').write_text('do not adopt', encoding='utf8')
    elif kind in ('invalid-version', 'malformed'):
        archive.mkdir()
        (archive / 'archive.json').write_text('{"format_version": 2}' if kind == 'invalid-version' else '{oops', encoding='utf8')
    elif kind == 'file':
        archive.write_text('do not replace', encoding='utf8')
    response = desktop_client.put('/api/desktop/paths', json={'archive': str(archive), 'backups': str(backups)})
    assert response.status_code == 422, response.text
    assert desktop_client.get('/api/desktop').json() == initial
    assert desktop_module().DesktopConfig(tmp_path / '桌面 home').paths == initial['paths']


def test_unwritable_path_is_rejected_before_config_commit(desktop_client, tmp_path, monkeypatch):
    launch(desktop_client)
    original = Path.open
    blocked = tmp_path / 'blocked'

    def guarded(path, *args, **kwargs):
        if path.is_relative_to(blocked):
            raise PermissionError('access denied')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', guarded)
    response = desktop_client.put('/api/desktop/paths', json={'archive': str(blocked), 'backups': str(tmp_path / 'new backups')})
    assert response.status_code == 422
    assert desktop_client.get('/api/desktop').json()['pending_restart'] is False


def test_existing_v1_archive_can_be_selected_without_modifying_it(desktop_client, tmp_path):
    from backend.dayframe.archive import Archive
    existing = Archive(tmp_path / 'existing archive')
    metadata = (existing.root / 'archive.json').read_bytes()
    launch(desktop_client)
    response = desktop_client.put('/api/desktop/paths', json={'archive': str(existing.root), 'backups': str(tmp_path / 'new backups')})
    assert response.status_code == 200, response.text
    assert (existing.root / 'archive.json').read_bytes() == metadata


def test_selected_paths_cannot_repurpose_the_active_archive(desktop_client, tmp_path):
    launch(desktop_client)
    original = desktop_client.get('/api/desktop').json()
    active = Path(original['paths']['archive'])
    for archive, backups in [(tmp_path / 'new archive', active), (active / 'nested archive', tmp_path / 'new backups')]:
        response = desktop_client.put('/api/desktop/paths', json={'archive': str(archive), 'backups': str(backups)})
        assert response.status_code == 422
    assert desktop_client.get('/api/desktop').json() == original


def test_packaged_frontend_is_served_same_origin(desktop_client, tmp_path, monkeypatch):
    bundle = tmp_path / 'bundled resources'
    (bundle / 'frontend').mkdir(parents=True)
    (bundle / 'frontend' / 'index.html').write_text('<h1>Bundled 中文</h1>', encoding='utf8')
    monkeypatch.setattr(sys, '_MEIPASS', str(bundle), raising=False)
    monkeypatch.delenv('FRONTEND_DIST', raising=False)
    app = desktop_module().create_desktop_app('second-test-secret', tmp_path / 'packaged home')
    with TestClient(app) as client:
        launch(client, 'second-test-secret')
        assert 'Bundled 中文' in client.get('/').text
        assert 'Bundled 中文' in client.get('/calendar').text


def test_frozen_application_paths_cannot_store_the_archive(tmp_path, monkeypatch):
    installation = tmp_path / 'Program Files' / 'DayFrame'
    installation.mkdir(parents=True)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(installation / 'dayframe-server.exe'))
    monkeypatch.delenv('DAYFRAME_DATA_HOME', raising=False)
    config = desktop_module().DesktopConfig(tmp_path / 'persistent home')
    with pytest.raises(ValueError, match='outside application'):
        config.save_paths({'archive': str(installation / 'Archive'), 'backups': str(tmp_path / 'Backups')})


def test_video_uses_explicit_ffmpeg_path_then_packaged_binary(tmp_path, monkeypatch):
    from backend.dayframe import exports
    bundle = tmp_path / '中文 bundle'
    (bundle / 'bin').mkdir(parents=True)
    bundled = bundle / 'bin' / 'ffmpeg.exe'
    bundled.write_bytes(b'executable-fixture')
    monkeypatch.setattr(sys, '_MEIPASS', str(bundle), raising=False)
    monkeypatch.delenv('DAYFRAME_FFMPEG', raising=False)
    assert exports.ffmpeg_binary() == str(bundled)
    explicit = tmp_path / 'chosen FFmpeg.exe'
    explicit.write_bytes(b'executable-fixture')
    monkeypatch.setenv('DAYFRAME_FFMPEG', str(explicit))
    assert exports.ffmpeg_binary() == str(explicit)
    monkeypatch.setenv('DAYFRAME_FFMPEG', str(tmp_path / 'missing.exe'))
    with pytest.raises(ValueError, match='FFmpeg'):
        exports.ffmpeg_binary()


def start_sidecar(home, token, env=None):
    environment = os.environ.copy()
    environment['PYTHONIOENCODING'] = 'utf-8'
    environment.pop('DAYFRAME_DATA_HOME', None)
    environment.update(env or {})
    process = subprocess.Popen(
        [sys.executable, '-m', 'backend.dayframe.desktop_entry'],
        cwd=Path(__file__).resolve().parents[2], env=environment,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding='utf8',
    )
    process.stdin.write(json.dumps({'token': token, 'data_home': str(home)}, ensure_ascii=False)+'\n')
    process.stdin.flush()
    lines = queue.Queue()
    threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
    try:
        line = lines.get(timeout=20)
        assert line.startswith('DAYFRAME_READY '), line or process.stderr.read()
        ready = json.loads(line.removeprefix('DAYFRAME_READY '))
        assert type(ready['port']) is int and 0 < ready['port'] < 65536
        return process, ready['port']
    except BaseException:
        process.kill()
        process.wait(timeout=10)
        raise


@pytest.mark.parametrize('close', ['blank', 'eof'])
def test_sidecar_ready_is_initialized_loopback_and_close_releases_archive(tmp_path, close):
    token = 'process-launch-secret-never-log'
    home = tmp_path / '独立 桌面'
    for attempt in range(2):
        process, port = start_sidecar(home, token)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False) as client:
                assert client.get('/health').json()['status'] == 'ok'
                assert client.get('/api/status').status_code == 401
                assert client.get('/desktop/launch', params={'token': token}).status_code == 303
                assert client.get('/api/status').json()['archive']['format_version'] == 1
                assert client.get('/api/desktop').json()['paths']['archive'] == str(home / 'Archive')
            if close == 'blank':
                process.stdin.write('\n')
                process.stdin.flush()
            else:
                process.stdin.close()
            assert process.wait(timeout=15) == 0
            assert process.stdout.read() == ''
            assert token not in process.stderr.read()
            with socket.socket() as probe:
                assert probe.connect_ex(('127.0.0.1', port)) != 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)


def test_sidecar_rejects_second_archive_writer_without_ready_or_secret_log(tmp_path):
    process, _ = start_sidecar(tmp_path / 'exclusive', 'first-secret')
    second = None
    try:
        environment = os.environ.copy()
        environment.pop('DAYFRAME_DATA_HOME', None)
        second = subprocess.run(
            [sys.executable, '-m', 'backend.dayframe.desktop_entry'],
            cwd=Path(__file__).resolve().parents[2], env=environment,
            input=json.dumps({'token': 'second-secret', 'data_home': str(tmp_path / 'exclusive')})+'\n',
            capture_output=True, text=True, encoding='utf8', timeout=20,
        )
        assert second.returncode != 0
        assert second.stdout == ''
        assert 'second-secret' not in second.stderr
    finally:
        process.stdin.close()
        assert process.wait(timeout=15) == 0


def test_occupied_legacy_port_does_not_prevent_random_port_launch(tmp_path):
    with socket.socket() as occupied:
        try:
            occupied.bind(('127.0.0.1', 8765))
            occupied.listen()
        except OSError:
            pass  # An already occupied legacy port exercises the same contract.
        process, port = start_sidecar(tmp_path / 'random port', 'random-port-test-secret')
        try:
            assert port != 8765
            with httpx.Client(trust_env=False) as client:
                assert client.get(f'http://127.0.0.1:{port}/health').status_code == 200
        finally:
            process.stdin.close()
            assert process.wait(timeout=15) == 0


@pytest.mark.parametrize('message', ['not-json', '{"token":"short"}', '{"token":"invalid-payload-secret", "extra":true}'])
def test_invalid_stdin_message_has_no_ready_or_secret_echo(tmp_path, message):
    environment = os.environ.copy()
    environment['DAYFRAME_DATA_HOME'] = str(tmp_path / 'invalid startup')
    result = subprocess.run(
        [sys.executable, '-m', 'backend.dayframe.desktop_entry'],
        cwd=Path(__file__).resolve().parents[2], env=environment,
        input=message+'\n', capture_output=True, text=True, timeout=15,
    )
    assert result.returncode != 0
    assert result.stdout == ''
    assert 'invalid-payload-secret' not in result.stderr
    assert not (tmp_path / 'invalid startup' / 'Archive').exists()
