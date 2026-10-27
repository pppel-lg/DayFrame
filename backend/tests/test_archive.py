import hashlib
import io
import json
import shutil
from datetime import date

import pytest
from PIL import Image


def image_bytes(color='red'):
    out = io.BytesIO()
    Image.new('RGB', (80, 100), color).save(out, format='JPEG')
    return out.getvalue()


@pytest.fixture
def archive(tmp_path):
    from backend.dayframe.archive import Archive
    return Archive(tmp_path / 'data')


def test_original_immutable_and_sidecar_survives_lost_index(archive):
    raw = image_bytes()
    entry = archive.import_photo('2026-02-28', raw)
    photo = entry['photos'][0]
    archive.update_entry('2026-02-28', {'note': '真实日记', 'mood': '平静', 'tags': ['life']})
    assert archive.safe_path(photo['relative_path']).read_bytes() == raw
    assert photo['sha256'] == hashlib.sha256(raw).hexdigest()
    assert not __import__('pathlib').PurePosixPath(photo['relative_path']).is_absolute()
    archive.index_path.unlink()
    archive.rebuild()
    assert archive.get_entry('2026-02-28')['note'] == '真实日记'


def test_duplicate_and_multiple_photos_preserve_primary(archive):
    first = archive.import_photo('2026-10-01', image_bytes())
    second = archive.import_photo('2026-10-01', image_bytes('blue'))
    assert len(second['photos']) == 2
    assert first['primary_photo_id'] == second['primary_photo_id']
    with pytest.raises(ValueError, match='duplicate'):
        archive.import_photo('2026-10-01', image_bytes())


def test_missing_original_keeps_diary_but_is_not_recorded(archive):
    entry = archive.import_photo('2026-10-01', image_bytes())
    archive.update_entry('2026-10-01', {'note': 'keep me'})
    archive.safe_path(entry['photos'][0]['relative_path']).unlink()
    assert archive.get_entry('2026-10-01')['note'] == 'keep me'
    assert archive.verify()['issues'][0]['code'] == 'missing_photo'
    assert archive.stats('2026-10-01', '2026-10-01', '2026-10-01')['recorded_days'] == 0


def test_statistics_dates_streak_and_backfill(archive):
    for day in ['2024-02-28', '2024-02-29', '2024-03-01']:
        archive.import_photo(day, image_bytes(), allow_duplicate=True)
    archive.update_entry('2024-03-02', {'status': 'skipped'})
    stats = archive.stats('2024-02-01', '2024-02-29', '2024-03-01')
    assert stats['eligible_days'] == 2
    assert stats['recorded_days'] == 2
    assert stats['recording_rate'] == 1
    assert stats['current_streak'] == 3
    assert archive.stats('2024-03-01', '2024-03-31', '2024-03-03')['current_streak'] == 0


@pytest.mark.parametrize('path', ['../secret', '/etc/passwd', 'C:/Windows/a', 'photos/../../a', 'photos\\a', '//server/file', 'photos/a:ads'])
def test_paths_reject_traversal(archive, path):
    with pytest.raises(ValueError):
        archive.safe_path(path)


def test_corrupt_database_recovered_and_bad_sidecar_reported(archive):
    archive.import_photo('2026-10-01', image_bytes())
    archive.index_path.write_bytes(b'broken sqlite')
    archive.safe_path('entries/2026/10/2026-10-02.json').write_text('{bad', encoding='utf8')
    archive.rebuild()
    assert archive.get_entry('2026-10-01')['status'] == 'recorded'
    assert any(i['code'] == 'invalid_sidecar' for i in archive.issues)


def test_trash_untrash_preserves_original(archive):
    entry = archive.import_photo('2026-10-01', image_bytes())
    pid = entry['primary_photo_id']
    trashed = archive.trash('2026-10-01', pid)
    assert trashed['status'] == 'skipped'
    assert trashed['photos'][0]['trashed_at_utc']
    assert archive.untrash('2026-10-01', pid)['primary_photo_id'] == pid
    assert archive.photo_bytes(pid) == image_bytes()


def test_future_schema_not_overwritten(tmp_path):
    from backend.dayframe.archive import Archive
    root = tmp_path / 'future'
    root.mkdir()
    (root / 'archive.json').write_text(json.dumps({'format': 'dayframe-archive', 'format_version': 999}))
    with pytest.raises(ValueError, match='version'):
        Archive(root)
    assert json.loads((root / 'archive.json').read_text())['format_version'] == 999


def test_backup_manifest_corruption_and_safe_restore(archive, tmp_path):
    from backend.dayframe.backup import BackupService
    archive.import_photo('2026-10-01', image_bytes())
    backup = BackupService(archive, tmp_path / 'backups')
    result = backup.create()
    restored = backup.restore(result['name'], 'fresh')
    from backend.dayframe.archive import Archive
    moved = Archive(restored['path'])
    assert moved.photo_bytes(moved.get_entry('2026-10-01')['primary_photo_id']) == image_bytes()
    with pytest.raises(ValueError):
        backup.restore(result['name'], '../escape')
    manifest = json.loads((backup.root / result['name'] / 'manifest.json').read_text())
    photo_path = next(p for p in manifest['files'] if p.startswith('photos/'))
    (backup.root / result['name'] / photo_path).write_bytes(b'tampered')
    with pytest.raises(ValueError, match='checksum'):
        backup.restore(result['name'], 'corrupt')
    assert not (backup.root / 'restored' / 'corrupt').exists()


def test_backup_inside_archive_rejected(archive):
    from backend.dayframe.backup import BackupService
    with pytest.raises(ValueError):
        BackupService(archive, archive.root / 'bad-backups')


def test_atomic_sidecar_failure_leaves_prior_entry(archive, monkeypatch):
    archive.import_photo('2026-10-01', image_bytes())
    import backend.dayframe.archive as mod
    old = mod.os.replace
    def fail(src, dst):
        if str(dst).endswith('2026-10-01.json'):
            raise OSError('disk full')
        return old(src, dst)
    monkeypatch.setattr(mod.os, 'replace', fail)
    with pytest.raises(OSError):
        archive.update_entry('2026-10-01', {'note': 'lost update'})
    assert archive.get_entry('2026-10-01')['note'] == ''


def test_cross_date_duplicate_requires_explicit_copy_confirmation(archive):
    archive.import_photo('2026-10-01', image_bytes())
    with pytest.raises(ValueError, match='duplicate image exists on another date; confirm to copy'):
        archive.import_photo('2026-10-02', image_bytes())
    copied = archive.import_photo('2026-10-02', image_bytes(), allow_duplicate=True)
    assert copied['record_date'] == '2026-10-02'


def test_interrupted_import_is_diagnosed_without_deleting_original(archive, monkeypatch):
    import backend.dayframe.archive as mod
    previous = mod.os.replace
    def fail(src, dst):
        if str(dst).endswith('2026-10-01.json'):
            raise OSError('interrupted sidecar save')
        return previous(src, dst)
    monkeypatch.setattr(mod.os, 'replace', fail)
    with pytest.raises(OSError):
        archive.import_photo('2026-10-01', image_bytes())
    monkeypatch.setattr(mod.os, 'replace', previous)
    recovered = mod.Archive(archive.root)
    assert recovered.entries()['total'] == 0
    assert any(issue['code'] == 'orphan_photo' for issue in recovered.issues)
    originals = list(recovered.safe_path('photos').rglob('*.jpg'))
    assert len(originals) == 1 and originals[0].read_bytes() == image_bytes()


def test_duplicate_media_paths_in_sidecar_are_reported_as_invalid(archive):
    archive.import_photo('2026-10-01', image_bytes())
    archive.import_photo('2026-10-01', image_bytes('blue'))
    path = archive.entry_path('2026-10-01')
    raw = json.loads(path.read_text(encoding='utf8'))
    raw['photos'][1]['relative_path'] = raw['photos'][0]['relative_path']
    path.write_text(json.dumps(raw), encoding='utf8')
    archive.rebuild()
    assert any(i['code'] == 'invalid_sidecar' for i in archive.issues)
