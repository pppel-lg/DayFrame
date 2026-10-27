# Dayframe v1 HTTP contract

All admin endpoints use same-origin cookies, reject cross-origin mutation requests, and return errors as {detail: string} or {detail: {code,message}}. Single-user loopback deployment. Local dates are YYYY-MM-DD; UTC instants ISO8601. UI derives today from browser local date and submits it in queries. API prefix /api.

Entry: {schema_version:1,entry_id,record_date,status:'recorded'|'skipped',primary_photo_id:string|null,mood:string,note:string,tags:string[],location:{label:string,city:string,region:string,country:string,latitude:number|null,longitude:number|null,precision:'none'|'city'|'exact',source:'manual'},photos:Photo[],created_at_utc,updated_at_utc}. Photo: {photo_id,relative_path,sha256,byte_size,mime_type,captured_at_utc:string|null,captured_timezone:string|null,captured_offset_minutes:number|null,imported_at_utc,source,is_original:true,trashed_at_utc:string|null}. API augments photo with missing:boolean and URL /api/photos/{photo_id}?thumbnail=true.

- GET /health => {status:'ok',version:'1.0.0'}
- GET /api/status => {archive: archive.json,settings: Settings,health:{issues:[]},photo_count:number,entry_count:number,archive_path:string,backup_path:string}
- GET /api/entries?start=YYYY-MM-DD&end=YYYY-MM-DD&mood=&tag=&q=&offset=0&limit=40 => {entries:Entry[],total:number}
- GET /api/entries/{date} => Entry (404 empty)
- PUT /api/entries/{date} JSON {mood,note,tags,location,status?,primary_photo_id?} => Entry; skipped cannot hide existing photos, reject unless confirmed=true; recorded requires primary.
- POST /api/entries/{date}/photos multipart file, source='import'|'camera', captured_at_utc?,captured_timezone?,captured_offset_minutes?, make_primary='false', allow_duplicate='false' (additional photo keeps existing primary) => Entry; same-date duplicate => 409. Cross-date identical content requires explicit allow_duplicate=true after a 409 confirmation prompt. Accepted actual file content: JPEG, PNG, WebP, HEIC/HEIF; maximum 50 MiB and 40 million decoded pixels. Originals are byte-preserved.
- POST /api/entries/{date}/primary JSON {photo_id,confirmed:true} => Entry
- POST /api/entries/{date}/trash JSON {photo_id,confirmed:true} => Entry; move to recycle bin, keep metadata; last photo leaves skipped.
- POST /api/entries/{date}/untrash JSON {photo_id} => Entry
- GET /api/photos/{id}?thumbnail=true => image; /api/photos/{id}?download=true => original attachment
- GET /api/stats?start=&end=&today=YYYY-MM-DD => {recorded_days,eligible_days,recording_rate:number(0..1),skipped_days,missing_days,photo_count,current_streak,total_days,monthly:[{month,count}],moods:[{mood,count}]}
- GET /api/memories?date= => {entries:Entry[]} exact month-day earlier years
- GET /api/locations?year= => {locations:[{label,count,dates:string[],latitude,longitude}]}
- GET /api/letters?today= => {letters:[{letter_id,title,unlock_date,created_at_utc,content?:string,locked:boolean}]}; POST /api/letters JSON {title,content,unlock_date,created_on_date} => letter; future content hidden by API.
- GET /api/settings => Settings; PUT /api/settings JSON partial => Settings. Settings: {reminder_enabled:boolean,reminder_time:'09:00',mirror_preview:boolean,mirror_output:boolean,week_starts_monday:boolean}.
- POST /api/jobs JSON {kind:'verify'|'backup'|'rebuild'|'export_calendar'|'report'|'video',year?:number,start?:date,end?:date,fps?:number,include_notes?:boolean} => {job_id}; GET /api/jobs/{id} => {job_id,kind,status:'queued'|'running'|'success'|'failed'|'cancelled',progress:0..100,result?:any,error?:string}; POST /api/jobs/{id}/cancel => job. result for export/report/video {url, ...}. Backup result includes name. Verify result {issues:[],...}.
- GET /api/backups => {backups:[{name,created_at_utc,file_count}]}; POST /api/restore JSON {name,target_name,confirmed:true} => {path, ...}; creates sibling under /backups/restored/{target_name}, never switches current archive silently.
- GET /api/exports/{path} => generated artifact download, safe relative path.
- POST /api/pairing JSON {base_url?:string} => {url,code,expires_at,port}; DELETE /api/pairing closes independent LAN listener; GET /api/pairing => {active:boolean,pending:[{upload_id,record_date,filename}]}.
- POST /api/pairing/approve JSON {upload_id,confirmed:true} => Entry; DELETE /api/pairing/pending/{id} rejects staged bytes.

Mobile service on separate port 8766 by explicit start only. / serves isolated upload UI, token in URL fragment submitted in Authorization header, /upload multipart file+record_date; no archive browse routes. Credentials expire after 10 minutes; shutdown closes port. Browser QR drawn locally.
