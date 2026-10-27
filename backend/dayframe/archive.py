"""Filesystem authority and a disposable SQLite projection.

All mutations are serialized. Originals commit before metadata; a failed metadata
write may leave an orphan, but can never make an acknowledged record lose bytes.
"""
import copy
import hashlib
import io
import json
import os
import re
import sqlite3
import stat
import threading
import uuid
import warnings
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from .models import ArchiveMetadata, Entry, EntryUpdate, Letter, Photo, Settings

MAX_UPLOAD = 50 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 40_000_000
register_heif_opener()


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def local_date(value):
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('date must be YYYY-MM-DD')
    return date.fromisoformat(value).isoformat()


def safe_relative(root, relative):
    """Deny device paths, Windows ADS, traversal, and every symlink component."""
    if not isinstance(relative, str) or not relative or any(ord(char) < 32 or char in '\\:<>|?*"' for char in relative):
        raise ValueError('unsafe relative path')
    parts = relative.split('/')
    if any(part in ('', '.', '..') or part.endswith(('.', ' ')) for part in parts):
        raise ValueError('unsafe relative path')
    if PurePosixPath(relative).is_absolute():
        raise ValueError('absolute paths are forbidden')
    current = Path(root)
    for part in [None, *parts]:
        if part is not None:
            if part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}:
                raise ValueError('device path forbidden')
            current = current / part
        try:
            attributes = os.lstat(current)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(attributes.st_mode) or getattr(attributes, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
            raise ValueError('symlink or junction forbidden')
    # Each relative component is lexical and every existing component was
    # checked with lstat. No resolve() is needed; it redundantly walks all
    # ancestors and made large archives particularly slow on Windows.
    return current


def sync_directory(path):
    if os.name != 'nt':
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        with temporary.open('xb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path, data):
    atomic_bytes(path, (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def image_info(raw):
    if not raw or len(raw) > MAX_UPLOAD:
        raise ValueError('image exceeds 50 MiB limit or is empty')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                kind = image.format
                image.verify()
            if kind not in ('JPEG', 'PNG', 'WEBP', 'HEIF'):
                raise ValueError('supported images: JPEG, PNG, WebP, HEIC/HEIF')
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
            return {'JPEG': ('.jpg', 'image/jpeg'), 'PNG': ('.png', 'image/png'), 'WEBP': ('.webp', 'image/webp'), 'HEIF': ('.heic', 'image/heic')}[kind]
    except (OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('invalid, corrupt or oversized image') from exc


class Archive:
    def __init__(self, root):
        self.root = Path(root).absolute()
        if self.root.is_symlink():
            raise ValueError('archive root must not be a symlink')
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.issues = []
        metadata_path = self.safe_path('archive.json')
        if metadata_path.exists():
            raw = self.read_json(metadata_path)
            if raw.get('format_version') != 1:
                raise ValueError('unsupported archive format version; original archive untouched')
            self.metadata = ArchiveMetadata.model_validate(raw).model_dump(mode='json')
        else:
            # Never silently adopt a non-empty directory as a fresh archive.
            if any(p.name != '.dayframe.lock' for p in self.root.iterdir()):
                raise ValueError('non-empty directory has no archive.json')
            self.metadata = ArchiveMetadata(archive_id=str(uuid.uuid4()), created_at_utc=now(), archive_start_date=date.today()).model_dump(mode='json')
            atomic_json(metadata_path, self.metadata)
        for directory in ['photos', 'entries', 'letters', 'index', 'thumbnails', 'cache', 'exports', 'trash', 'recovery']:
            self.safe_path(directory).mkdir(exist_ok=True)
        self.index_path = self.safe_path('index/dayframe.sqlite3')
        settings_path = self.safe_path('settings.json')
        self.settings = Settings.model_validate(self.read_json(settings_path) if settings_path.exists() else {}).model_dump()
        if not settings_path.exists():
            atomic_json(settings_path, self.settings)
        self.rebuild()

    def safe_path(self, relative):
        return safe_relative(self.root, relative)

    @staticmethod
    def read_json(path):
        if path.stat().st_size > 5 * 1024 * 1024:
            raise ValueError('metadata file exceeds limit')
        return json.loads(path.read_text(encoding='utf-8'))

    def entry_path(self, day):
        day = local_date(day)
        return self.safe_path(f'entries/{day[:4]}/{day[5:7]}/{day}.json')

    def validate_entry(self, raw, path=None):
        entry = Entry.model_validate(raw).model_dump(mode='json')
        if path is not None and Path(path) != self.entry_path(entry['record_date']):
            raise ValueError('sidecar date disagrees with path')
        for photo in entry['photos']:
            self.safe_path(photo['relative_path'])
            expected_prefix = 'trash/' if photo['trashed_at_utc'] else 'photos/'
            if not photo['relative_path'].startswith(expected_prefix):
                raise ValueError('photo path outside media subtree')
        return entry

    @contextmanager
    def _connect(self, path=None):
        connection = sqlite3.connect(path or self.index_path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def rebuild(self, progress=None):
        with self.lock:
            self.issues = []
            temporary = self.safe_path(f'index/rebuild-{uuid.uuid4().hex}.sqlite3')
            paths = list(self.safe_path('entries').rglob('*.json'))
            ids, photo_ids, photo_paths = set(), set(), set()
            try:
                with self._connect(temporary) as db:
                    db.execute('CREATE TABLE entries (record_date TEXT PRIMARY KEY, mood TEXT, note TEXT, document TEXT NOT NULL)')
                    db.execute('CREATE INDEX entries_mood ON entries(mood,record_date)')
                    db.execute('CREATE TABLE photos (photo_id TEXT PRIMARY KEY, record_date TEXT NOT NULL, relative_path TEXT UNIQUE NOT NULL, sha256 TEXT NOT NULL)')
                    db.execute('CREATE INDEX photos_sha256 ON photos(sha256)')
                    db.execute('CREATE INDEX photos_record_date ON photos(record_date)')
                    for index, path in enumerate(sorted(paths)):
                        if progress:
                            progress(index * 90 / max(len(paths), 1))
                        try:
                            path = self.safe_path(path.relative_to(self.root).as_posix())
                            entry = self.validate_entry(self.read_json(path), path)
                            if entry['entry_id'] in ids or any(p['photo_id'] in photo_ids or p['relative_path'] in photo_paths for p in entry['photos']):
                                raise ValueError('duplicate entry ID, photo ID or media path')
                            self._index(db, entry)
                            ids.add(entry['entry_id'])
                            photo_ids.update(p['photo_id'] for p in entry['photos'])
                            photo_paths.update(p['relative_path'] for p in entry['photos'])
                            for photo in entry['photos']:
                                if not self.safe_path(photo['relative_path']).is_file():
                                    self.issues.append({'code': 'missing_photo', 'path': photo['relative_path'], 'photo_id': photo['photo_id']})
                        except (ValueError, OSError) as exc:
                            self.issues.append({'code': 'invalid_sidecar', 'path': path.relative_to(self.root).as_posix(), 'message': str(exc)[:500]})
                with temporary.open('r+b') as out:
                    os.fsync(out.fileno())
                os.replace(temporary, self.index_path)
                # This index always uses DELETE journaling. Old WAL files from a
                # previous external process are not replayed onto the new index.
                for suffix in ['-wal', '-shm', '-journal']:
                    self.safe_path('index/dayframe.sqlite3' + suffix).unlink(missing_ok=True)
                self._update_start()
                self._check_letters()
                self._scan_media(photo_paths)
                return {'entry_count': len(ids), 'photo_count': len(photo_ids), 'issues': copy.deepcopy(self.issues)}
            finally:
                temporary.unlink(missing_ok=True)

    def _index(self, db, entry):
        day = entry['record_date']
        db.execute('INSERT OR REPLACE INTO entries VALUES (?,?,?,?)', (day, entry['mood'], entry['note'], json.dumps(entry, ensure_ascii=False)))
        db.execute('DELETE FROM photos WHERE record_date=?', (day,))
        db.executemany('INSERT INTO photos VALUES (?,?,?,?)', [(p['photo_id'], day, p['relative_path'], p['sha256']) for p in entry['photos']])

    def _update_start(self, day=None):
        if day is None:
            with self._connect() as db:
                day = db.execute('SELECT MIN(record_date) FROM entries').fetchone()[0]
        if day and day < self.metadata['archive_start_date']:
            metadata = {**self.metadata, 'archive_start_date': day}
            atomic_json(self.safe_path('archive.json'), metadata)
            self.metadata = metadata

    def _check_letters(self):
        for path in self.safe_path('letters').glob('*.json'):
            try:
                checked = self.safe_path(path.relative_to(self.root).as_posix())
                letter = Letter.model_validate(self.read_json(checked))
                if path.name != letter.letter_id + '.json':
                    raise ValueError('letter ID disagrees with path')
            except (ValueError, OSError) as exc:
                self.issues.append({'code': 'invalid_letter', 'path': path.relative_to(self.root).as_posix(), 'message': str(exc)[:500]})

    def _scan_media(self, referenced):
        for subtree in ['photos', 'trash']:
            for path in self.safe_path(subtree).rglob('*'):
                relative = path.relative_to(self.root).as_posix()
                try:
                    checked = self.safe_path(relative)
                    if checked.is_file() and relative not in referenced:
                        self.issues.append({'code': 'orphan_photo', 'path': relative})
                except (ValueError, OSError) as exc:
                    self.issues.append({'code': 'unsafe_media_path', 'path': relative, 'message': str(exc)[:500]})

    def _raw_entry(self, day):
        day = local_date(day)
        path = self.entry_path(day)
        if not path.exists():
            raise KeyError('entry not found')
        return self.validate_entry(self.read_json(path), path)

    def _new_entry(self, day):
        return Entry(entry_id=str(uuid.uuid4()), record_date=local_date(day), created_at_utc=now(), updated_at_utc=now()).model_dump(mode='json')

    def _persist(self, entry):
        entry['updated_at_utc'] = now()
        entry = self.validate_entry(entry)
        atomic_json(self.entry_path(entry['record_date']), entry)
        # Index failure after durable commit is repaired from authority. The
        # caller receives success only after the projection is usable again.
        try:
            with self._connect() as db:
                self._index(db, entry)
        except sqlite3.DatabaseError:
            self.rebuild()
        self._update_start(entry['record_date'])
        return self.augment(entry)

    def augment(self, entry):
        entry = copy.deepcopy(entry)
        for photo in entry['photos']:
            photo['missing'] = not self.safe_path(photo['relative_path']).is_file()
            photo['url'] = f"/api/photos/{photo['photo_id']}?thumbnail=true"
        return entry

    def get_entry(self, day):
        with self.lock:
            return self.augment(self._raw_entry(day))

    def entries(self, start=None, end=None, mood='', tag='', q='', offset=0, limit=40):
        where, values = [], []
        for column, operator, value in [('record_date', '>=', start), ('record_date', '<=', end), ('mood', '=', mood)]:
            if value:
                where.append(f'{column} {operator} ?')
                values.append(local_date(value) if column == 'record_date' else value)
        sql = 'SELECT document FROM entries' + (' WHERE ' + ' AND '.join(where) if where else '') + ' ORDER BY record_date DESC'
        with self.lock, self._connect() as db:
            documents = [json.loads(row[0]) for row in db.execute(sql, values)]
            filtered = [e for e in documents if (not tag or tag in e['tags']) and (not q or q.casefold() in (e['note'] + ' ' + e['mood'] + ' ' + e['location']['label'] + ' ' + e['location']['city'] + ' ' + ' '.join(e['tags'])).casefold())]
            return {'entries': [self.augment(e) for e in filtered[offset:offset+limit]], 'total': len(filtered)}

    def import_photo(self, day, raw, source='import', captured_at_utc=None, captured_timezone=None, captured_offset_minutes=None, make_primary=False, allow_duplicate=False):
        day = local_date(day)
        extension, mime = image_info(raw)
        digest = hashlib.sha256(raw).hexdigest()
        with self.lock:
            try:
                entry = self._raw_entry(day)
            except KeyError:
                entry = self._new_entry(day)
            if any(p['sha256'] == digest for p in entry['photos']):
                raise ValueError('duplicate image for this date')
            with self._connect() as db:
                duplicate = db.execute('SELECT 1 FROM photos WHERE sha256=? AND record_date<>? LIMIT 1', (digest, day)).fetchone()
            if duplicate and not allow_duplicate:
                raise ValueError('duplicate image exists on another date; confirm to copy')
            if entry['primary_photo_id'] and make_primary:
                raise ValueError('use confirmed primary endpoint to replace an existing primary')
            pid = str(uuid.uuid4())
            relative = f'photos/{day[:4]}/{day[5:7]}/{day}_{pid}{extension}'
            photo = Photo(photo_id=pid, relative_path=relative, sha256=digest, byte_size=len(raw), mime_type=mime, captured_at_utc=captured_at_utc, captured_timezone=captured_timezone, captured_offset_minutes=captured_offset_minutes, imported_at_utc=now(), source=source).model_dump(mode='json')
            destination = self.safe_path(relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation: original bytes are never replaced, even in the
            # astronomically unlikely event of a UUID collision.
            with destination.open('xb') as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
            sync_directory(destination.parent)
            entry['photos'].append(photo)
            if not entry['primary_photo_id']:
                entry['primary_photo_id'] = pid
            entry['status'] = 'recorded'
            return self._persist(entry)

    def update_entry(self, day, updates):
        update = EntryUpdate.model_validate(updates)
        changes = update.model_dump(mode='json', exclude_unset=True)
        confirmed = changes.pop('confirmed', False)
        with self.lock:
            try:
                entry = self._raw_entry(day)
            except KeyError:
                entry = self._new_entry(day)
            if 'primary_photo_id' in changes and changes['primary_photo_id'] != entry['primary_photo_id'] and not confirmed:
                raise ValueError('primary replacement requires confirmation')
            if changes.get('status') == 'skipped' and any(not p['trashed_at_utc'] for p in entry['photos']) and not confirmed:
                raise ValueError('skipping a day with photos requires confirmation')
            for key, value in changes.items():
                if value is None and key != 'primary_photo_id':
                    raise ValueError(f'{key} cannot be null')
                entry[key] = value
            if entry['status'] == 'recorded':
                primary = next((p for p in entry['photos'] if p['photo_id'] == entry['primary_photo_id'] and not p['trashed_at_utc']), None)
                if primary is None or not self.safe_path(primary['relative_path']).is_file():
                    raise ValueError('recorded day requires an existing primary photo')
            return self._persist(entry)

    def primary(self, day, photo_id):
        return self.update_entry(day, {'primary_photo_id': photo_id, 'status': 'recorded', 'confirmed': True})

    def _move_trash(self, day, photo_id, to_trash):
        with self.lock:
            entry = self._raw_entry(day)
            photo = next((p for p in entry['photos'] if p['photo_id'] == photo_id), None)
            if photo is None:
                raise KeyError('photo not found in this entry')
            if bool(photo['trashed_at_utc']) == to_trash:
                return self.augment(entry)
            source = self.safe_path(photo['relative_path'])
            if not source.is_file():
                raise ValueError('original missing; cannot move it')
            if to_trash:
                relative = f'trash/{photo_id}{source.suffix}'
            else:
                relative = f'photos/{day[:4]}/{day[5:7]}/{day}_{photo_id}{source.suffix}'
            destination = self.safe_path(relative)
            data = source.read_bytes()
            if destination.exists():
                if hashlib.sha256(destination.read_bytes()).hexdigest() != photo['sha256']:
                    raise ValueError('destination conflict; existing bytes protected')
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open('xb') as out:
                    out.write(data)
                    out.flush()
                    os.fsync(out.fileno())
            photo['relative_path'] = relative
            photo['trashed_at_utc'] = now() if to_trash else None
            active = [p for p in entry['photos'] if not p['trashed_at_utc'] and self.safe_path(p['relative_path']).is_file()]
            if to_trash and entry['primary_photo_id'] == photo_id:
                entry['primary_photo_id'] = active[0]['photo_id'] if active else None
            elif not to_trash and not entry['primary_photo_id']:
                entry['primary_photo_id'] = photo_id
            entry['status'] = 'recorded' if entry['primary_photo_id'] else 'skipped'
            result = self._persist(entry)
            source.unlink()
            sync_directory(source.parent)
            return result

    def trash(self, day, photo_id):
        return self._move_trash(local_date(day), photo_id, True)

    def untrash(self, day, photo_id):
        return self._move_trash(local_date(day), photo_id, False)

    def photo(self, photo_id):
        uuid.UUID(photo_id)
        with self.lock, self._connect() as db:
            row = db.execute('SELECT record_date FROM photos WHERE photo_id=?', (photo_id,)).fetchone()
            if row is None:
                raise KeyError('photo not found')
            entry = self._raw_entry(row[0])
            return next(p for p in entry['photos'] if p['photo_id'] == photo_id)

    def photo_bytes(self, photo_id):
        photo = self.photo(photo_id)
        return self.safe_path(photo['relative_path']).read_bytes()

    def thumbnail(self, photo_id):
        with self.lock:
            photo = self.photo(photo_id)
            original = self.safe_path(photo['relative_path'])
            if not original.is_file():
                raise KeyError('original photo missing')
            path = self.safe_path(f'thumbnails/{photo_id}-{photo["sha256"][:12]}.jpg')
            if not path.exists():
                with Image.open(original) as image:
                    image = ImageOps.exif_transpose(image)
                    image.thumbnail((640, 640))
                    buffer = io.BytesIO()
                    image.convert('RGB').save(buffer, 'JPEG', quality=85)
                    atomic_bytes(path, buffer.getvalue())
            return path

    def stats(self, start=None, end=None, today=None):
        today = date.fromisoformat(local_date(today or date.today()))
        start = date.fromisoformat(local_date(start or self.metadata['archive_start_date']))
        end = date.fromisoformat(local_date(end or today))
        if start > end:
            raise ValueError('start must not be after end')
        all_entries = self.entries(limit=1_000_000)['entries']
        recorded = {e['record_date'] for e in all_entries if e['status'] == 'recorded' and any(p['photo_id'] == e['primary_photo_id'] and not p['missing'] and not p['trashed_at_utc'] for p in e['photos'])}
        archive_start = date.fromisoformat(self.metadata['archive_start_date'])
        lower, upper = max(start, archive_start), min(end, today)
        eligible = max(0, (upper-lower).days+1)
        selected = [e for e in all_entries if lower.isoformat() <= e['record_date'] <= upper.isoformat()] if eligible else []
        recorded_count = sum(e['record_date'] in recorded for e in selected)
        skipped = sum(e['status'] == 'skipped' for e in selected)
        cursor = today if today.isoformat() in recorded else today-timedelta(days=1)
        streak = 0
        while cursor.isoformat() in recorded:
            streak += 1
            cursor -= timedelta(days=1)
        monthly, moods = {}, {}
        for entry in selected:
            if entry['record_date'] in recorded:
                month = entry['record_date'][:7]
                monthly[month] = monthly.get(month, 0)+1
                if entry['mood']:
                    moods[entry['mood']] = moods.get(entry['mood'], 0)+1
        return {'recorded_days': recorded_count, 'eligible_days': eligible, 'recording_rate': recorded_count / eligible if eligible else 0, 'skipped_days': skipped, 'missing_days': max(0, eligible-recorded_count-skipped), 'photo_count': sum(not p['missing'] and not p['trashed_at_utc'] for e in selected for p in e['photos']), 'current_streak': streak, 'total_days': sum(day <= today.isoformat() for day in recorded), 'monthly': [{'month': m, 'count': c} for m, c in sorted(monthly.items())], 'moods': [{'mood': m, 'count': c} for m, c in sorted(moods.items(), key=lambda p: -p[1])]}

    def verify(self, progress=None):
        with self.lock:
            # Re-validate authority, rather than trusting a stale projection.
            self.rebuild(progress)
            issues = copy.deepcopy(self.issues)
            seen = {(issue['code'], issue.get('path')) for issue in issues}
            photos = [p for e in self.entries(limit=1_000_000)['entries'] for p in e['photos']]
            referenced = set()
            for index, photo in enumerate(photos):
                if progress:
                    progress(index*90/max(len(photos), 1))
                path = self.safe_path(photo['relative_path'])
                referenced.add(photo['relative_path'])
                code = None
                if not path.is_file():
                    code = 'missing_photo'
                else:
                    with path.open('rb') as stream:
                        if path.stat().st_size != photo['byte_size'] or hashlib.file_digest(stream, 'sha256').hexdigest() != photo['sha256']:
                            code = 'checksum_mismatch'
                if code and (code, photo['relative_path']) not in seen:
                    issues.append({'code': code, 'path': photo['relative_path'], 'photo_id': photo['photo_id']})
            self.issues = issues
            return {'issues': issues, 'checked_photos': len(photos)}

    def save_settings(self, updates):
        with self.lock:
            settings = Settings.model_validate({**self.settings, **updates}).model_dump()
            atomic_json(self.safe_path('settings.json'), settings)
            self.settings = settings
            return settings

    def add_letter(self, title, content, unlock_date, created_on_date):
        with self.lock:
            if local_date(unlock_date) < local_date(created_on_date):
                raise ValueError('unlock date must not precede created date')
            letter = Letter(letter_id=str(uuid.uuid4()), title=title, content=content, unlock_date=unlock_date, created_on_date=created_on_date, created_at_utc=now()).model_dump(mode='json')
            atomic_json(self.safe_path(f'letters/{letter["letter_id"]}.json'), letter)
            return {k: v for k, v in letter.items() if k != 'content'}

    def letters(self, today):
        today = local_date(today)
        result = []
        with self.lock:
            for path in self.safe_path('letters').glob('*.json'):
                try:
                    path = self.safe_path(path.relative_to(self.root).as_posix())
                    letter = Letter.model_validate(self.read_json(path)).model_dump(mode='json')
                    letter['locked'] = letter['unlock_date'] > today
                    if letter['locked']:
                        letter.pop('content')
                    result.append(letter)
                except (ValueError, OSError):
                    continue  # Recorded as a health issue, never deleted.
        return sorted(result, key=lambda e: e['unlock_date'])
