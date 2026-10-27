"""Consistent independent snapshots with a complete SHA-256 manifest."""
import hashlib
import os
import re
import shutil
import sqlite3
import uuid
from pathlib import Path

from .archive import Archive, atomic_json, now, safe_relative, sync_directory


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class BackupService:
    def __init__(self, archive, root):
        self.archive = archive
        self.root = Path(root).absolute()
        if self.root.is_symlink() or self.root.resolve().is_relative_to(archive.root.resolve()) or archive.root.resolve().is_relative_to(self.root.resolve()):
            raise ValueError('backup directory must be independent of archive')
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def name(value):
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,100}', value):
            raise ValueError('invalid backup or target name')
        return value

    def _path(self, relative):
        return safe_relative(self.root, relative)

    def create(self, progress=None):
        name = 'backup-' + now().replace(':', '').replace('-', '').replace('.', '') + '-' + uuid.uuid4().hex[:8]
        staging = self._path('staging-' + uuid.uuid4().hex)
        staging.mkdir()
        try:
            with self.archive.lock:
                # Fail closed on malformed sidecars or corrupt/missing originals.
                health = self.archive.verify(progress)
                fatal = [i for i in health['issues'] if i['code'] != 'orphan_photo']
                if fatal:
                    raise ValueError(f'archive health prevents backup: {fatal[0]["code"]}')
                paths = [self.archive.safe_path('archive.json'), self.archive.safe_path('settings.json')]
                for subtree in ['entries', 'photos', 'letters', 'trash']:
                    paths.extend(p for p in self.archive.safe_path(subtree).rglob('*') if p.is_file() or p.is_symlink())
                manifest = {'format': 'dayframe-backup', 'format_version': 1, 'archive_id': self.archive.metadata['archive_id'], 'created_at_utc': now(), 'files': {}}
                for index, path in enumerate(paths):
                    if progress:
                        progress(index*85/max(len(paths), 1))
                    relative = path.relative_to(self.archive.root).as_posix()
                    path = self.archive.safe_path(relative)
                    destination = safe_relative(staging, relative)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with path.open('rb') as src, destination.open('xb') as dst:
                        shutil.copyfileobj(src, dst, 1024*1024)
                        dst.flush()
                        os.fsync(dst.fileno())
                    manifest['files'][relative] = {'sha256': digest(destination), 'byte_size': destination.stat().st_size}
                # SQLite's Online Backup API produces a consistent derived index.
                destination = safe_relative(staging, 'index/dayframe.sqlite3')
                destination.parent.mkdir()
                with self.archive._connect() as source:
                    target = sqlite3.connect(destination)
                    try:
                        source.backup(target)
                    finally:
                        target.close()
                manifest['files']['index/dayframe.sqlite3'] = {'sha256': digest(destination), 'byte_size': destination.stat().st_size}
                atomic_json(staging / 'manifest.json', manifest)
                self.validate(staging, progress)
                if progress:
                    progress(99)
                os.rename(staging, self._path(name))
                sync_directory(self.root)
                return {'name': name, 'created_at_utc': manifest['created_at_utc'], 'file_count': len(manifest['files'])}
        finally:
            if staging.exists():
                # Staging is an internally created, verified direct child.
                shutil.rmtree(staging)

    def validate(self, directory, progress=None):
        directory = Path(directory)
        manifest = Archive.read_json(safe_relative(directory, 'manifest.json'))
        if manifest.get('format') != 'dayframe-backup' or manifest.get('format_version') != 1 or not isinstance(manifest.get('files'), dict):
            raise ValueError('invalid backup manifest')
        files = manifest['files']
        if not {'archive.json', 'settings.json'}.issubset(files):
            raise ValueError('incomplete backup manifest')
        for index, (relative, metadata) in enumerate(files.items()):
            if progress:
                progress(85+index*10/max(len(files), 1))
            path = safe_relative(directory, relative)
            if relative not in ('archive.json', 'settings.json', 'index/dayframe.sqlite3') and relative.split('/')[0] not in ('entries', 'letters', 'photos', 'trash'):
                raise ValueError('unexpected manifest path')
            if not isinstance(metadata, dict) or not path.is_file() or path.stat().st_size != metadata.get('byte_size') or digest(path) != metadata.get('sha256'):
                raise ValueError(f'backup checksum mismatch: {relative}')
        for path in directory.rglob('*'):
            relative = path.relative_to(directory).as_posix()
            safe_relative(directory, relative)
            if path.is_file() and relative != 'manifest.json' and relative not in files:
                raise ValueError('unlisted file in backup')
        return manifest

    def list(self):
        result = []
        for path in self.root.glob('backup-*'):
            try:
                path = self._path(path.name)
                manifest = Archive.read_json(safe_relative(path, 'manifest.json'))
                if manifest.get('format') == 'dayframe-backup' and manifest.get('format_version') == 1:
                    result.append({'name': path.name, 'created_at_utc': manifest['created_at_utc'], 'file_count': len(manifest['files'])})
            except (ValueError, OSError, KeyError):
                continue
        return sorted(result, key=lambda b: b['name'], reverse=True)

    def restore(self, name, target_name):
        name, target_name = self.name(name), self.name(target_name)
        source = self._path(name)
        manifest = self.validate(source)
        restored = self._path('restored')
        restored.mkdir(exist_ok=True)
        target = self._path(f'restored/{target_name}')
        if target.exists():
            raise ValueError('restore target already exists; refusing to merge')
        staging = self._path(f'restored/staging-{uuid.uuid4().hex}')
        staging.mkdir()
        try:
            for relative in manifest['files']:
                src = safe_relative(source, relative)
                dst = safe_relative(staging, relative)
                dst.parent.mkdir(parents=True, exist_ok=True)
                with src.open('rb') as inp, dst.open('xb') as out:
                    shutil.copyfileobj(inp, out, 1024*1024)
                    out.flush()
                    os.fsync(out.fileno())
                if digest(dst) != manifest['files'][relative]['sha256']:
                    raise ValueError('restore checksum mismatch')
            archive = Archive(staging)
            health = archive.verify()
            if any(i['code'] != 'orphan_photo' for i in health['issues']):
                raise ValueError('restored archive failed validation')
            entry_count = archive.entries(limit=0)['total']
            os.rename(staging, target)
            sync_directory(restored)
            return {'path': str(target), 'entry_count': entry_count, 'issues': health['issues']}
        finally:
            if staging.exists():
                shutil.rmtree(staging)
