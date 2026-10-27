import time
import pytest
from fastapi.testclient import TestClient
from backend.tests.test_archive import image_bytes


@pytest.fixture
def client(tmp_path):
    from backend.dayframe.main import create_app
    with TestClient(create_app(tmp_path / 'data', tmp_path / 'backups')) as client:
        yield client


def upload(client, day='2026-10-01', color='red'):
    response = client.post(f'/api/entries/{day}/photos', files={'file': ('selfie.jpg', image_bytes(color), 'image/jpeg')})
    assert response.status_code == 200, response.text
    return response.json()


def wait_job(client, payload):
    result = client.post('/api/jobs', json=payload)
    assert result.status_code == 200, result.text
    # Backup performs real fsync/checksum IO; Windows runner scheduling and
    # filesystem scanning must not turn a 200-poll (~2s) assumption into a failure.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        job = client.get('/api/jobs/' + result.json()['job_id']).json()
        if job['status'] in ['success', 'failed', 'cancelled']:
            assert job['status'] == 'success', job
            return job
        time.sleep(.01)
    pytest.fail(f'job did not finish within 30s: {payload}; last state: {job}')


def test_api_persistence_metadata_photos_and_confirmations(client):
    entry = upload(client)
    pid = entry['primary_photo_id']
    assert client.put('/api/entries/2026-10-01', json={'note': '安静', 'mood': '平静'}).json()['note'] == '安静'
    assert client.get(f'/api/photos/{pid}').content == image_bytes()
    assert client.get(f'/api/photos/{pid}?thumbnail=true').headers['content-type'] == 'image/jpeg'
    assert client.post('/api/entries/2026-10-01/trash', json={'photo_id': pid}).status_code == 422
    assert client.post('/api/entries/2026-10-01/trash', json={'photo_id': pid, 'confirmed': True}).status_code == 200
    assert client.post('/api/entries/2026-10-01/untrash', json={'photo_id': pid}).json()['primary_photo_id'] == pid


def test_cross_origin_and_dns_rebinding_rejected(client):
    assert client.put('/api/settings', json={'mirror_preview': False}, headers={'Origin': 'https://evil.test'}).status_code == 403
    assert client.get('/api/status', headers={'Host': 'evil.test'}).status_code == 403
    assert client.get('/health').json() == {'status': 'ok', 'version': '1.0.0'}


def test_calendar_export_backup_restore_and_report(client):
    upload(client)
    client.put('/api/entries/2026-10-01', json={'note': '<script>bad()</script>', 'location': {'city': '台北', 'precision': 'city'}})
    job = wait_job(client, {'kind': 'export_calendar', 'year': 2026})
    html = client.get(job['result']['url']).text
    assert '<script>bad()' not in html
    assert '2026-10-01' in html
    report = wait_job(client, {'kind': 'report', 'year': 2026, 'include_notes': True})
    assert client.get(report['result']['url']).status_code == 200
    backup = wait_job(client, {'kind': 'backup'})
    name = backup['result']['name']
    assert client.get('/api/backups').json()['backups'][0]['name'] == name
    assert client.post('/api/restore', json={'name': name, 'target_name': 'recovered', 'confirmed': True}).status_code == 200


def test_future_letters_and_exact_memories(client):
    upload(client, '2024-02-29')
    assert len(client.get('/api/memories?date=2028-02-29').json()['entries']) == 1
    assert client.get('/api/memories?date=2027-02-28').json()['entries'] == []
    letter = client.post('/api/letters', json={'title': 'future', 'content': 'secret', 'unlock_date': '2027-01-01', 'created_on_date': '2026-10-01'})
    assert letter.status_code == 200, letter.text
    assert 'content' not in client.get('/api/letters?today=2026-12-31').json()['letters'][0]
    assert client.get('/api/letters?today=2027-01-01').json()['letters'][0]['content'] == 'secret'


def test_invalid_image_and_field_validation(client):
    assert client.post('/api/entries/2026-10-01/photos', files={'file': ('bad.jpg', b'not image', 'image/jpeg')}).status_code == 422
    assert client.put('/api/entries/../../outside', json={'status': 'skipped'}).status_code != 200
    assert client.put('/api/entries/2026-10-01', json={'location': {'precision': 'exact', 'latitude': 999}}).status_code == 422
