"""Exercise the actual built container without third-party test dependencies."""
import base64
import argparse
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date

BASE = os.environ.get('DAYFRAME_SMOKE_BASE', 'http://127.0.0.1:8765')
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def request(path, payload=None, method=None, content_type="application/json"):
    if payload is not None and not isinstance(payload, bytes):
        payload = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, payload, method=method)
    req.add_header("Origin", BASE)
    if payload is not None:
        req.add_header("Content-Type", content_type)
    with opener.open(req, timeout=20) as response:
        raw = response.read()
        return json.loads(raw) if "application/json" in response.headers.get("Content-Type", "") else raw


def job(kind, **fields):
    created = request("/api/jobs", {"kind": kind, **fields})
    for _ in range(120):
        result = request("/api/jobs/" + created["job_id"])
        if result["status"] == "success":
            return result["result"]
        if result["status"] in ("failed", "cancelled"):
            raise AssertionError(result)
        time.sleep(0.25)
    raise AssertionError("Job timed out")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--after-restart', action='store_true')
    parser.add_argument('--local', action='store_true', help='Skip container mount-path assertions for local API verification')
    options = parser.parse_args()
    for _ in range(60):
        try:
            assert request("/health")["version"] == "1.0.0"
            break
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    else:
        raise AssertionError("Container did not become healthy")
    assert b"<html" in request("/").lower()
    status = request("/api/status")
    if not options.local:
        assert status['archive_path'] == '/data', status['archive_path']
        assert status['backup_path'] == '/backups', status['backup_path']
    if options.after_restart:
        entries = request('/api/entries?q=Container%20persistence%20smoke')['entries']
        assert len(entries) == 1, entries
        assert entries[0]['note'] == 'Container persistence smoke'
        assert request(f"/api/photos/{entries[0]['primary_photo_id']}?download=true")
        assert request('/api/backups')['backups']
        print('Container restart PASS: original, diary, index and backup remain available')
        return
    today = date.today().isoformat()
    # A valid, deliberately tiny PNG; it is synthetic test input only.
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGOMKEllwAaYsIoOWgkA8uEBQa+UvQwAAAAASUVORK5CYII=")
    boundary = "dayframe-smoke-boundary"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"test.png\"\r\nContent-Type: image/png\r\n\r\n".encode()
            + png + f"\r\n--{boundary}--\r\n".encode())
    entry = request(f"/api/entries/{today}/photos", body, content_type=f"multipart/form-data; boundary={boundary}")
    assert entry["status"] == "recorded"
    saved = request(f"/api/entries/{today}", {"mood": "calm", "note": "Container persistence smoke", "tags": ["smoke"], "location": {"label": "Taipei", "city": "Taipei", "precision": "city"}}, "PUT")
    assert saved["note"] == "Container persistence smoke"
    assert request(f"/api/photos/{entry['primary_photo_id']}?download=true") == png
    job("rebuild")
    assert request(f"/api/entries/{today}")["note"] == saved["note"]
    stats = request(f"/api/stats?start={today}&end={today}&today={today}")
    assert stats["recorded_days"] == 1
    verification = job("verify")
    assert not verification["issues"], verification
    backup = job("backup")
    assert backup
    restored = request('/api/restore', {'name': backup['name'], 'target_name': 'smoke-restored', 'confirmed': True})
    assert restored['entry_count'] == 1, restored
    exported = job("export_calendar", year=int(today[:4]))
    assert request(exported["url"])
    assert b'original_relative_path' in request(exported['csv_url'])
    report = job('report', year=int(today[:4]))
    assert b'data:image/jpeg;base64,' in request(report['url'])
    if not options.local:
        video = job('video', start=today, end=today, fps=2)
        assert video['frame_count'] == 1
        assert b'ftyp' in request(video['url'])[:32]
    print("Container smoke PASS: UI, import, metadata, exact original bytes, reindex, stats, integrity, backup, restore, offline CSV/calendar/report" + (", MP4 video" if not options.local else " (local video skipped)"))


if __name__ == "__main__":
    main()
