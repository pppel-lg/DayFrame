import copy
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from . import exports


class Cancelled(Exception):
    pass


class Jobs:
    def __init__(self, archive, backup):
        self.archive, self.backup = archive, backup
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='dayframe-job')
        self.lock = threading.Lock()
        self.jobs = {}
        self.events = {}

    def start(self, request):
        job_id = str(uuid.uuid4())
        with self.lock:
            self.jobs[job_id] = {'job_id': job_id, 'kind': request.kind, 'status': 'queued', 'progress': 0}
            self.events[job_id] = threading.Event()
        self.executor.submit(self._run, job_id, request)
        return {'job_id': job_id}

    def _run(self, job_id, request):
        def progress(value):
            if self.events[job_id].is_set():
                raise Cancelled()
            with self.lock:
                self.jobs[job_id]['progress'] = max(self.jobs[job_id]['progress'], min(99, round(value)))
        with self.lock:
            self.jobs[job_id]['status'] = 'running'
        try:
            progress(0)
            year = request.year or date.today().year
            if request.kind == 'verify':
                result = self.archive.verify(progress)
            elif request.kind == 'rebuild':
                result = self.archive.rebuild(progress)
            elif request.kind == 'backup':
                result = self.backup.create(progress)
            elif request.kind == 'export_calendar':
                result = exports.export_calendar(self.archive, year, progress)
            elif request.kind == 'report':
                result = exports.report(self.archive, year, request.include_notes, progress)
            else:
                result = exports.video(self.archive, request.start or f'{year}-01-01', request.end or f'{year}-12-31', request.fps, progress)
            with self.lock:
                self.jobs[job_id].update(status='success', progress=100, result=result)
        except Cancelled:
            with self.lock:
                self.jobs[job_id]['status'] = 'cancelled'
        except Exception as exc:
            with self.lock:
                self.jobs[job_id].update(status='failed', error=str(exc)[:2000])

    def get(self, job_id):
        with self.lock:
            if job_id not in self.jobs:
                raise KeyError('job not found')
            return copy.deepcopy(self.jobs[job_id])

    def cancel(self, job_id):
        with self.lock:
            if job_id not in self.jobs:
                raise KeyError('job not found')
            if self.jobs[job_id]['status'] in ('queued', 'running'):
                self.events[job_id].set()
            return copy.deepcopy(self.jobs[job_id])

    def close(self):
        for event in self.events.values():
            event.set()
        self.executor.shutdown(wait=True, cancel_futures=True)
