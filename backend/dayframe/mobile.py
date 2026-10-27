"""An opt-in, expiring upload-only listener. No admin router is mounted here."""
import hashlib
import hmac
import ipaddress
import secrets
import socket
import threading
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

import uvicorn
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from .archive import MAX_UPLOAD, atomic_bytes, image_info, local_date


MOBILE_HTML = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Dayframe 手机上传</title>
<style>body{font:18px system-ui;background:#f8f7f3;color:#303a32;max-width:450px;margin:40px auto;padding:24px}input,button{display:block;margin:16px 0;width:100%;font:inherit;padding:12px;box-sizing:border-box}button{background:#587465;color:white;border:0;border-radius:8px}p{line-height:1.7}img{width:100%;max-height:360px;object-fit:contain;border-radius:8px}</style>
<h1>留下一帧</h1><p>照片先暂存到电脑，需在电脑确认后才会加入归档。配对将在 10 分钟后失效。请在可信任的 Wi-Fi 下使用。</p>
<form id="upload"><label>记录日期<input id="day" type="date" required></label><label>拍摄自拍<input id="camera" type="file" accept="image/*,.heic,.heif" capture="user"></label><label>或从相册选择<input id="photo" type="file" accept="image/*,.heic,.heif"></label><p id="filename"></p><img id="preview" alt="待上传照片预览" hidden><button>上传到电脑</button></form><p id="result" role="status"></p>
<script>
const token=location.hash.slice(1);history.replaceState(null,'',location.pathname);
const day=document.querySelector('#day'),out=document.querySelector('#result'),preview=document.querySelector('#preview'),filename=document.querySelector('#filename');
const d=new Date();day.value=[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');
let selectedFile=null,previewUrl=null;
for(const id of ['camera','photo']){document.getElementById(id).onchange=e=>{selectedFile=e.target.files[0]||null;document.getElementById(id==='camera'?'photo':'camera').value='';if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=null;preview.hidden=true;filename.textContent=selectedFile?selectedFile.name:'';out.textContent='';if(selectedFile){previewUrl=URL.createObjectURL(selectedFile);preview.onerror=()=>{preview.hidden=true;out.textContent='此格式无法在浏览器预览，仍可保留原件上传。'};preview.onload=()=>{preview.hidden=false};preview.src=previewUrl}}}
document.querySelector('#upload').onsubmit=async e=>{e.preventDefault();if(!selectedFile){out.textContent='请先拍照或选择照片。';return}if(selectedFile.size>50*1024*1024){out.textContent='照片不能超过 50 MiB。';return}const button=document.querySelector('button');button.disabled=true;const selectedDate=day.value;try{const f=new FormData();f.append('file',selectedFile);f.append('record_date',selectedDate);const r=await fetch('/upload',{method:'POST',headers:{Authorization:'Bearer '+token},body:f});const j=await r.json();if(!r.ok)throw Error(j.detail||'上传失败');out.textContent='已暂存，请在电脑上确认。';e.target.reset();day.value=selectedDate;selectedFile=null;preview.hidden=true;filename.textContent='';if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=null}catch(x){out.textContent=x.message}finally{button.disabled=false}};
</script></html>'''


class BodyLimit:
    """Reject oversized bodies before multipart parsing, including chunked data."""
    def __init__(self, app, maximum=MAX_UPLOAD+1024*1024):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        try:
            length = int(headers.get(b'content-length', b'0'))
        except ValueError:
            length = self.maximum+1
        if length > self.maximum:
            from starlette.responses import JSONResponse
            return await JSONResponse({'detail': 'upload exceeds 50 MiB limit'}, status_code=413)(scope, receive, send)
        received = 0
        async def limited():
            nonlocal received
            message = await receive()
            received += len(message.get('body', b''))
            if received > self.maximum:
                raise HTTPException(413, 'upload exceeds 50 MiB limit')
            return message
        return await self.app(scope, limited, send)


class Pairing:
    def __init__(self, archive, port=8766):
        self.archive, self.port = archive, port
        self.lock = threading.RLock()
        self.token = None
        self.deadline = 0
        self.server = self.thread = self.timer = self.socket = None
        self.pending = {}
        self.failures = {}
        self.stage = archive.safe_path('recovery/mobile')
        self.stage.mkdir(exist_ok=True)
        # Bytes from an interrupted pairing never become authoritative records.
        for path in self.stage.glob('*.stage'):
            archive.safe_path(path.relative_to(archive.root).as_posix()).unlink()

    def active(self):
        return self.token is not None and time.monotonic() < self.deadline

    def authenticate(self, authorization, address='unknown'):
        with self.lock:
            if not self.active():
                raise HTTPException(401, 'pairing expired or closed')
            attempts, since = self.failures.get(address, (0, time.monotonic()))
            if time.monotonic()-since > 60:
                attempts, since = 0, time.monotonic()
            if attempts >= 10:
                raise HTTPException(429, 'too many failed pairing attempts; retry in one minute')
            if not hmac.compare_digest(authorization or '', 'Bearer '+self.token):
                self.failures[address] = (attempts+1, since)
                raise HTTPException(401, 'invalid pairing credentials')

    def mobile_app(self):
        from fastapi import Request
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        app.add_middleware(BodyLimit)

        @app.get('/', response_class=HTMLResponse)
        def index():
            if not self.active():
                raise HTTPException(410, 'pairing expired')
            return HTMLResponse(MOBILE_HTML, headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff'})

        @app.post('/upload')
        async def upload(request: Request, file: UploadFile = File(...), record_date: str = Form(...), authorization: str | None = Header(default=None)):
            address = request.client.host if request.client else 'unknown'
            self.authenticate(authorization, address)
            raw = await file.read(MAX_UPLOAD+1)
            await file.close()
            try:
                day = local_date(record_date)
                image_info(raw)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            with self.lock:
                self.authenticate(authorization, address)
                if len(self.pending) >= 20 or sum(p['byte_size'] for p in self.pending.values())+len(raw) > 200*1024*1024:
                    raise HTTPException(429, 'pending upload limit reached; approve or reject on desktop')
                upload_id = str(uuid.uuid4())
                filename = (file.filename or 'mobile-photo').replace('\\', '/').split('/')[-1][:200]
                path = self.archive.safe_path(f'recovery/mobile/{upload_id}.stage')
                atomic_bytes(path, raw)
                self.pending[upload_id] = {'upload_id': upload_id, 'record_date': day, 'filename': filename, 'byte_size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                return {'upload_id': upload_id, 'status': 'pending_desktop_approval'}
        return app

    def start(self, base_url=None):
        with self.lock:
            if self.active():
                raise ValueError('pairing already active; close it before starting another')
        self.close()
        if base_url:
            parsed = urlsplit(base_url)
            if parsed.scheme != 'http' or parsed.username or parsed.password or not parsed.hostname or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
                raise ValueError('base_url must be a local http origin')
            host = parsed.hostname
            try:
                address = ipaddress.ip_address(host)
                if not (address.is_private or address.is_loopback) or address.is_unspecified or address.is_multicast:
                    raise ValueError('base_url must use a private LAN address')
            except ValueError as exc:
                if host != 'localhost':
                    raise ValueError('enter the computer private LAN IP address') from exc
        else:
            host = '127.0.0.1'
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # UDP connect chooses the LAN route without sending any packet.
                probe.connect(('192.0.2.1', 9))
                host = probe.getsockname()[0]
            except OSError:
                pass
            finally:
                probe.close()
        with self.lock:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(('0.0.0.0', self.port))
                sock.listen(16)
                self.port = sock.getsockname()[1]
                self.socket = sock
                self.token = secrets.token_urlsafe(32)
                self.deadline = time.monotonic()+600
                self.failures.clear()
                self.server = uvicorn.Server(uvicorn.Config(self.mobile_app(), access_log=False, log_level='error', lifespan='off'))
                self.thread = threading.Thread(target=self.server.run, kwargs={'sockets': [sock]}, daemon=True, name='dayframe-mobile')
                self.thread.start()
                self.timer = threading.Timer(600, self.close)
                self.timer.daemon = True
                self.timer.start()
                host = '['+host+']' if ':' in host else host
                return {'url': f'http://{host}:{self.port}/#{self.token}', 'code': secrets.token_hex(3).upper(), 'expires_at': datetime.fromtimestamp(time.time()+600, timezone.utc).isoformat().replace('+00:00', 'Z'), 'port': self.port}
            except Exception:
                sock.close()
                self.token = None
                raise

    def status(self):
        with self.lock:
            return {'active': self.active(), 'pending': [{k: p[k] for k in ['upload_id', 'record_date', 'filename']} for p in self.pending.values()]}

    def approve(self, upload_id):
        with self.lock:
            item = self.pending.get(upload_id)
            if not item:
                raise KeyError('pending upload not found')
            path = self.archive.safe_path(f'recovery/mobile/{upload_id}.stage')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != item['sha256']:
                raise ValueError('staged photo checksum mismatch')
            result = self.archive.import_photo(item['record_date'], raw, source='mobile', allow_duplicate=True)
            path.unlink()
            self.pending.pop(upload_id)
            return result

    def reject(self, upload_id):
        with self.lock:
            if upload_id not in self.pending:
                raise KeyError('pending upload not found')
            self.archive.safe_path(f'recovery/mobile/{upload_id}.stage').unlink(missing_ok=True)
            self.pending.pop(upload_id)

    def close(self):
        with self.lock:
            self.token = None
            self.deadline = 0
            timer, thread, server, sock = self.timer, self.thread, self.server, self.socket
            self.timer = self.thread = self.server = self.socket = None
            if timer:
                timer.cancel()
            if server:
                server.should_exit = True
        if thread and thread is not threading.current_thread():
            thread.join(timeout=5)
        if sock:
            sock.close()
        # Pending uploads survive manual close until explicit desktop review;
        # they are never served by the closed listener.
