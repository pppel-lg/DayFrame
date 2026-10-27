"""Desktop-only path settings, kept outside the portable archive."""
import json
import os
from pathlib import Path
import stat
import sys
import threading
import uuid

from .archive import Archive, atomic_json, safe_relative
from .models import ArchiveMetadata


def _directory(value):
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip():
        raise ValueError('select an absolute directory path')
    path = Path(value)
    if not path.is_absolute():
        raise ValueError('directory path must be absolute')
    # Resolve lexical .. only after rejecting every existing link/junction.
    for component in [path, *path.parents]:
        try:
            attrs = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(attrs.st_mode) or getattr(attrs, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
            raise ValueError('directory must not contain a symlink or junction')
    return path.resolve()


def _overlaps(first, second):
    return first.is_relative_to(second) or second.is_relative_to(first)


def _writable(path):
    probe = path / ('.dayframe-write-check-' + uuid.uuid4().hex)
    try:
        path.mkdir(parents=True, exist_ok=True)
        with probe.open('xb') as stream:
            stream.write(b'DayFrame directory write check')
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise ValueError('directory is not writable; choose another folder or check permissions') from exc
    finally:
        probe.unlink(missing_ok=True)


class DesktopConfig:
    def __init__(self, data_home=None):
        default = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'DayFrame'
        selected_home = data_home if data_home is not None else default
        self.home = _directory(os.environ.get('DAYFRAME_DATA_HOME') or selected_home)
        self.logs = self.home / 'Logs'
        self.settings = self.home / 'Settings'
        self.lock = threading.RLock()
        _writable(self.logs)
        _writable(self.settings)
        self.config_file = self.settings / 'desktop.json'
        defaults = {'archive': str(self.home / 'Archive'), 'backups': str(self.home / 'Backups')}
        try:
            saved = Archive.read_json(self.config_file) if self.config_file.exists() else defaults
            self.paths = self._validate(saved)
        except (OSError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError('desktop path settings cannot be read; original archives are unchanged') from exc
        self.pending = dict(self.paths)

    def _validate(self, paths):
        if not isinstance(paths, dict) or set(paths) != {'archive', 'backups'}:
            raise ValueError('archive and backups directory paths are required')
        try:
            archive, backups = _directory(paths['archive']), _directory(paths['backups'])
            if _overlaps(archive, backups):
                raise ValueError('archive and backup directories must not overlap')
            protected = [self.logs, self.settings]
            if getattr(sys, '_MEIPASS', None):
                protected.append(Path(sys._MEIPASS).resolve())
            if getattr(sys, 'frozen', False):
                protected.append(Path(sys.executable).resolve().parent)
            if any(_overlaps(path, reserved) for path in (archive, backups) for reserved in protected):
                raise ValueError('archive and backups must be outside application, Settings and Logs directories')
            if hasattr(self, 'paths'):
                active_archive = Path(self.paths['archive'])
                active_backups = Path(self.paths['backups'])
                if _overlaps(archive, active_backups) or _overlaps(backups, active_archive):
                    raise ValueError('new paths must not overlap the currently active archive or backups')
                if archive != active_archive and _overlaps(archive, active_archive):
                    raise ValueError('new archive must not overlap the currently active archive')
                if backups != active_backups and _overlaps(backups, active_backups):
                    raise ValueError('new backups must not overlap currently active backups')
            if archive.exists():
                metadata = safe_relative(archive, 'archive.json')
                if metadata.exists():
                    raw = Archive.read_json(metadata)
                    if not isinstance(raw, dict) or raw.get('format_version') != 1:
                        raise ValueError('unsupported archive format version; original archive untouched')
                    ArchiveMetadata.model_validate(raw)
                elif any(path.name != '.dayframe.lock' for path in archive.iterdir()):
                    raise ValueError('non-empty directory has no compatible archive.json')
            _writable(archive)
            _writable(backups)
            return {'archive': str(archive), 'backups': str(backups)}
        except (OSError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError('cannot use selected directories; check permissions and archive compatibility') from exc

    def status(self):
        with self.lock:
            return {'desktop': True, 'paths': dict(self.paths), 'pending_restart': self.pending != self.paths}

    def save_paths(self, paths):
        with self.lock:
            validated = self._validate(paths)
            atomic_json(self.config_file, validated)
            self.pending = validated
            return self.status()


def frontend_directory():
    explicit = os.environ.get('FRONTEND_DIST')
    if explicit:
        return Path(explicit).absolute()
    if getattr(sys, '_MEIPASS', None):
        return Path(sys._MEIPASS) / 'frontend'
    return Path('frontend/dist').absolute()


def create_desktop_app(token, data_home=None):
    if not isinstance(token, str) or len(token) < 12 or len(token) > 1024:
        raise ValueError('a per-launch desktop token is required')
    from .main import create_app
    config = DesktopConfig(data_home)
    return create_app(config.paths['archive'], config.paths['backups'], desktop=config, desktop_token=token)
