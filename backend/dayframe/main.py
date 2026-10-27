"""Dayframe single-user application. Importing this module does not open data."""
import ipaddress
import os
import secrets
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from .archive import Archive, MAX_UPLOAD, local_date, safe_relative
from .backup import BackupService
from .jobs import Jobs
from .mobile import BodyLimit, Pairing
from .models import EntryUpdate, JobRequest, LetterRequest, PhotoChoice, RestoreRequest, UntrashChoice


class ArchiveLease:
    """Fail startup instead of letting two workers mutate the same archive."""
    def __init__(self, root):
        root = Path(root).absolute()
        root.mkdir(parents=True, exist_ok=True)
        path = safe_relative(root, '.dayframe.lock')
        self.stream = path.open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.stream.seek(0)
                if self.stream.read(1) == b'':
                    self.stream.write(b'0')
                    self.stream.flush()
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            raise RuntimeError('archive is already open in another Dayframe process') from exc

    def close(self):
        if os.name == 'nt':
            import msvcrt
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        self.stream.close()


class PairRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_url: str | None = None


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    upload_id: str
    confirmed: bool


def create_app(data_root=None, backup_root=None):
    root = Path(data_root or os.environ.get('DAYFRAME_DATA') or os.environ.get('DAYFRAME_DATA_DIR', './DayframeArchive')).absolute()
    backups = Path(backup_root or os.environ.get('DAYFRAME_BACKUPS') or os.environ.get('DAYFRAME_BACKUP_DIR', './DayframeBackups')).absolute()

    @asynccontextmanager
    async def lifespan(app):
        lease = ArchiveLease(root)
        jobs = pairing = None
        try:
            archive = await run_in_threadpool(Archive, root)
            backup = BackupService(archive, backups)
            jobs = Jobs(archive, backup)
            pairing = Pairing(archive, int(os.environ.get('DAYFRAME_MOBILE_PORT', '8766')))
            app.state.archive, app.state.backup = archive, backup
            app.state.jobs, app.state.pairing = jobs, pairing
            yield
        finally:
            if pairing:
                await run_in_threadpool(pairing.close)
            if jobs:
                await run_in_threadpool(jobs.close)
            lease.close()

    app = FastAPI(title='Dayframe', version='1.0.0', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    session = secrets.token_urlsafe(32)
    app.add_middleware(BodyLimit)

    @app.middleware('http')
    async def local_security(request, call_next):
        host_header = request.headers.get('host', '')
        try:
            parsed = urlsplit('http://'+host_header)
            host = parsed.hostname
            if parsed.username or parsed.password or not host:
                raise ValueError()
            allowed = host.lower() == 'localhost' or ipaddress.ip_address(host).is_loopback
        except ValueError:
            allowed = host_header == 'testserver' and request.client and request.client.host == 'testclient'
        if not allowed:
            return JSONResponse({'detail': 'admin service accepts loopback hostnames only'}, status_code=403)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            expected = request.url.scheme+'://'+host_header
            if request.headers.get('sec-fetch-site') == 'cross-site' or (origin and origin != expected):
                return JSONResponse({'detail': 'cross-origin mutation rejected'}, status_code=403)
            # Browser clients acquire an HttpOnly SameSite session on initial
            # load. Non-browser local tools may access the API without cookies.
            if (origin or request.headers.get('sec-fetch-site')) and request.cookies.get('dayframe_session') != session:
                return JSONResponse({'detail': 'load Dayframe before modifying the archive'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Cache-Control'] = 'no-store'
        if request.cookies.get('dayframe_session') != session:
            response.set_cookie('dayframe_session', session, httponly=True, samesite='strict', secure=request.url.scheme == 'https')
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409 if 'duplicate' in str(exc) else 422)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({'detail': str(exc).strip("'")}, status_code=404)

    @app.exception_handler(FileNotFoundError)
    async def missing_file(request, exc):
        return JSONResponse({'detail': 'requested file is missing; run archive verification'}, status_code=404)

    @app.exception_handler(OSError)
    async def io_error(request, exc):
        return JSONResponse({'detail': 'filesystem operation failed; check disk space and archive permissions'}, status_code=503)

    @app.get('/health')
    def health():
        return {'status': 'ok', 'version': '1.0.0'}

    @app.get('/api/status')
    def status():
        archive = app.state.archive
        entries = archive.entries(limit=1_000_000)['entries']
        missing = [{'code': 'missing_photo', 'photo_id': p['photo_id'], 'path': p['relative_path']} for e in entries for p in e['photos'] if p['missing']]
        issues = list(archive.issues)
        seen = {(i['code'], i.get('path')) for i in issues}
        issues.extend(i for i in missing if (i['code'], i.get('path')) not in seen)
        return {'archive': archive.metadata, 'settings': archive.settings, 'health': {'issues': issues}, 'photo_count': sum(not p['missing'] and not p['trashed_at_utc'] for e in entries for p in e['photos']), 'entry_count': len(entries), 'archive_path': str(root), 'backup_path': str(backups)}

    @app.get('/api/entries')
    def entries(start: date | None = None, end: date | None = None, mood: str = '', tag: str = '', q: str = '', offset: int = Query(0, ge=0), limit: int = Query(40, ge=1, le=1000)):
        return app.state.archive.entries(start, end, mood, tag, q, offset, limit)

    @app.get('/api/entries/{day}')
    def entry(day: date):
        return app.state.archive.get_entry(day.isoformat())

    @app.put('/api/entries/{day}')
    def update(day: date, body: EntryUpdate):
        return app.state.archive.update_entry(day.isoformat(), body.model_dump(mode='json', exclude_unset=True))

    @app.post('/api/entries/{day}/photos')
    async def import_photo(day: date, file: UploadFile = File(...), source: str = Form('import'), captured_at_utc: str | None = Form(None), captured_timezone: str | None = Form(None), captured_offset_minutes: int | None = Form(None), make_primary: bool = Form(False), allow_duplicate: bool = Form(False)):
        raw = await file.read(MAX_UPLOAD+1)
        await file.close()
        return await run_in_threadpool(app.state.archive.import_photo, day.isoformat(), raw, source, captured_at_utc, captured_timezone, captured_offset_minutes, make_primary, allow_duplicate)

    @app.post('/api/entries/{day}/primary')
    def primary(day: date, body: PhotoChoice):
        return app.state.archive.primary(day.isoformat(), body.photo_id)

    @app.post('/api/entries/{day}/trash')
    def trash(day: date, body: PhotoChoice):
        return app.state.archive.trash(day.isoformat(), body.photo_id)

    @app.post('/api/entries/{day}/untrash')
    def untrash(day: date, body: UntrashChoice):
        return app.state.archive.untrash(day.isoformat(), body.photo_id)

    @app.get('/api/photos/{photo_id}')
    def photo(photo_id: str, thumbnail: bool = False, download: bool = False):
        archive = app.state.archive
        metadata = archive.photo(photo_id)
        path = archive.thumbnail(photo_id) if thumbnail else archive.safe_path(metadata['relative_path'])
        if not path.is_file():
            raise HTTPException(404, 'original photo missing')
        return FileResponse(path, media_type='image/jpeg' if thumbnail else metadata['mime_type'], filename=path.name if download else None)

    @app.get('/api/stats')
    def stats(start: date | None = None, end: date | None = None, today: date | None = None):
        return app.state.archive.stats(start, end, today)

    @app.get('/api/memories')
    def memories(date: date):
        day = local_date(date)
        return {'entries': [e for e in app.state.archive.entries(end=day, limit=1_000_000)['entries'] if e['record_date'][:4] < day[:4] and e['record_date'][5:] == day[5:]]}

    @app.get('/api/locations')
    def locations(year: int | None = Query(None, ge=1900, le=9999)):
        entries = app.state.archive.entries(start=f'{year:04d}-01-01' if year else None, end=f'{year:04d}-12-31' if year else None, limit=1_000_000)['entries']
        grouped = {}
        for entry in entries:
            loc = entry['location']
            label = loc['label'] or ', '.join(v for v in [loc['city'], loc['region'], loc['country']] if v)
            if not label and loc['latitude'] is None:
                continue
            key = (label, loc['latitude'], loc['longitude'])
            grouped.setdefault(key, {'label': label or '已授权坐标', 'count': 0, 'dates': [], 'latitude': loc['latitude'], 'longitude': loc['longitude']})
            grouped[key]['count'] += 1
            grouped[key]['dates'].append(entry['record_date'])
        return {'locations': list(grouped.values())}

    @app.get('/api/letters')
    def letters(today: date):
        return {'letters': app.state.archive.letters(today.isoformat())}

    @app.post('/api/letters')
    def create_letter(body: LetterRequest):
        return app.state.archive.add_letter(**body.model_dump())

    @app.get('/api/settings')
    def settings():
        return app.state.archive.settings

    @app.put('/api/settings')
    def put_settings(body: dict):
        return app.state.archive.save_settings(body)

    @app.post('/api/jobs')
    def start_job(body: JobRequest):
        return app.state.jobs.start(body)

    @app.get('/api/jobs/{job_id}')
    def get_job(job_id: str):
        return app.state.jobs.get(job_id)

    @app.post('/api/jobs/{job_id}/cancel')
    def cancel_job(job_id: str):
        return app.state.jobs.cancel(job_id)

    @app.get('/api/backups')
    def list_backups():
        return {'backups': app.state.backup.list()}

    @app.post('/api/restore')
    def restore(body: RestoreRequest):
        return app.state.backup.restore(body.name, body.target_name)

    @app.get('/api/exports/{path:path}')
    def artifact(path: str):
        target = app.state.archive.safe_path('exports/'+path)
        if not target.is_file():
            raise HTTPException(404, 'export not found')
        return FileResponse(target)

    @app.get('/api/pairing')
    def pairing_status():
        return app.state.pairing.status()

    @app.post('/api/pairing')
    def start_pairing(body: PairRequest):
        return app.state.pairing.start(body.base_url)

    @app.delete('/api/pairing')
    def stop_pairing():
        app.state.pairing.close()
        return app.state.pairing.status()

    @app.post('/api/pairing/approve')
    def approve(body: ApproveRequest):
        if body.confirmed is not True:
            raise HTTPException(422, 'desktop confirmation required')
        return app.state.pairing.approve(body.upload_id)

    @app.delete('/api/pairing/pending/{upload_id}')
    def reject(upload_id: str):
        app.state.pairing.reject(upload_id)
        return app.state.pairing.status()

    frontend = Path(os.environ.get('FRONTEND_DIST', 'frontend/dist')).absolute()

    @app.get('/{path:path}')
    def frontend_route(path: str):
        if path.startswith('api/') or path == 'api':
            raise HTTPException(404, 'API route not found')
        if path:
            target = safe_relative(frontend, path)
            if target.is_file():
                return FileResponse(target)
            if '.' in Path(path).name:
                raise HTTPException(404, 'asset not found')
        index = safe_relative(frontend, 'index.html')
        if index.is_file():
            return FileResponse(index)
        return HTMLResponse('<h1>Dayframe</h1><p>Frontend bundle missing. Run npm run build in frontend.</p>', status_code=503)

    return app


app = create_app()
