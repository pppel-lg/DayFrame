import hashlib
import io
import json
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
from PIL import Image

from backend.tests.test_archive import archive, image_bytes


def test_heif_original_preserved_with_jpeg_thumbnail(archive):
    import pillow_heif
    pillow_heif.register_heif_opener()
    output = io.BytesIO()
    Image.new('RGB', (64, 80), 'green').save(output, format='HEIF')
    raw = output.getvalue()
    entry = archive.import_photo('2026-10-01', raw)
    photo = entry['photos'][0]
    assert photo['mime_type'] == 'image/heic'
    assert archive.photo_bytes(photo['photo_id']) == raw
    with Image.open(archive.thumbnail(photo['photo_id'])) as thumbnail:
        assert thumbnail.format == 'JPEG'


def test_env_archive_configuration(monkeypatch, tmp_path):
    from backend.dayframe.main import create_app
    from fastapi.testclient import TestClient
    data, backups = tmp_path / 'configured-data', tmp_path / 'configured-backups'
    monkeypatch.setenv('DAYFRAME_DATA', str(data))
    monkeypatch.setenv('DAYFRAME_BACKUPS', str(backups))
    with TestClient(create_app()) as client:
        status = client.get('/api/status').json()
        assert status['archive_path'] == str(data)
        assert status['backup_path'] == str(backups)


def test_symlink_directory_escape_is_refused(archive, tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'secret').write_text('private')
    link = archive.root / 'photos' / 'escape'
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('OS account cannot create symlinks; exercised in Linux CI')
    with pytest.raises(ValueError, match='symlink'):
        archive.safe_path('photos/escape/secret')


def test_malformed_sidecar_cannot_read_outside_archive(archive, tmp_path):
    archive.import_photo('2026-10-01', image_bytes())
    path = archive.entry_path('2026-10-01')
    raw = json.loads(path.read_text(encoding='utf8'))
    raw['photos'][0]['relative_path'] = '../secret.jpg'
    path.write_text(json.dumps(raw), encoding='utf8')
    archive.rebuild()
    assert archive.entries()['entries'] == []
    assert archive.issues[0]['code'] == 'invalid_sidecar'


def test_pairing_auth_expiry_isolation_staging_approval_and_close(archive):
    from backend.dayframe.mobile import Pairing
    pairing = Pairing(archive, port=0)
    info = pairing.start('http://127.0.0.1')
    token = info['url'].split('#')[1]
    base = info['url'].split('/#')[0]
    try:
        for _ in range(100):
            if pairing.server.started:
                break
            time.sleep(.01)
        with httpx.Client(base_url=base, trust_env=False) as phone:
            payload = {'file': ('phone.jpg', image_bytes(), 'image/jpeg')}
            assert phone.get('/api/status').status_code == 404
            assert phone.post('/upload', files=payload, data={'record_date': '2026-10-01'}).status_code == 401
            headers = {'Authorization': 'Bearer '+token}
            accepted = phone.post('/upload', files=payload, data={'record_date': '2026-10-01'}, headers=headers)
            assert accepted.status_code == 200, accepted.text
            assert archive.entries()['total'] == 0
            assert len(pairing.status()['pending']) == 1
            entry = pairing.approve(accepted.json()['upload_id'])
            assert entry['photos'][0]['source'] == 'mobile'
            assert archive.entries()['total'] == 1
            pairing.deadline = time.monotonic()-1
            assert phone.post('/upload', files=payload, data={'record_date': '2026-10-02'}, headers=headers).status_code == 401
    finally:
        pairing.close()
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', info['port'])) != 0


def test_backup_cancellation_does_not_replace_prior_snapshot(archive, tmp_path):
    from backend.dayframe.backup import BackupService
    from backend.dayframe.jobs import Cancelled
    archive.import_photo('2026-10-01', image_bytes())
    service = BackupService(archive, tmp_path / 'backups')
    first = service.create()
    def cancel(value):
        raise Cancelled()
    with pytest.raises(Cancelled):
        service.create(cancel)
    assert [backup['name'] for backup in service.list()] == [first['name']]
    assert not list(service.root.glob('staging-*'))
    service.validate(service.root / first['name'])


def test_job_cancellation_before_artifact_commit(archive, tmp_path, monkeypatch):
    from backend.dayframe import exports
    from backend.dayframe.backup import BackupService
    from backend.dayframe.jobs import Jobs
    from backend.dayframe.models import JobRequest
    archive.import_photo('2026-01-01', image_bytes())
    entered, resume = threading.Event(), threading.Event()
    original = exports.thumbnail_data
    def pause(*args):
        entered.set()
        assert resume.wait(5)
        return original(*args)
    monkeypatch.setattr(exports, 'thumbnail_data', pause)
    jobs = Jobs(archive, BackupService(archive, tmp_path / 'backups'))
    try:
        job_id = jobs.start(JobRequest(kind='export_calendar', year=2026))['job_id']
        assert entered.wait(5)
        jobs.cancel(job_id)
        resume.set()
        for _ in range(200):
            job = jobs.get(job_id)
            if job['status'] == 'cancelled':
                break
            time.sleep(.01)
        assert job['status'] == 'cancelled'
        assert not archive.safe_path('exports/calendar/2026.html').exists()
    finally:
        resume.set()
        jobs.close()


def test_backup_manifest_rejects_traversal(archive, tmp_path):
    from backend.dayframe.backup import BackupService
    archive.import_photo('2026-01-01', image_bytes())
    backup = BackupService(archive, tmp_path / 'backups')
    result = backup.create()
    manifest_path = backup.root / result['name'] / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['files']['../escape'] = {'sha256': hashlib.sha256(b'x').hexdigest(), 'byte_size': 1}
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='unsafe'):
        backup.restore(result['name'], 'forbidden')


def test_mobile_page_supports_capture_heif_preview_and_keeps_date():
    from backend.dayframe.mobile import MOBILE_HTML
    assert 'capture="user"' in MOBILE_HTML
    assert '.heic,.heif' in MOBILE_HTML
    assert 'createObjectURL' in MOBILE_HTML
    assert 'selectedDate' in MOBILE_HTML
    assert 'localStorage' not in MOBILE_HTML
