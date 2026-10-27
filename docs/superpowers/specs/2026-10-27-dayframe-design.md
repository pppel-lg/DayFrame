# Dayframe 1.0 design

User request: implement in this folder, package with Docker, upload to pppel-lg/DayFrame, and proceed without questions. Dayframe.md is the product baseline, not an instruction to stop at its embedded M0-only sample prompt.

## Architecture decision
Docker deployment takes precedence over the suggested native desktop shell. Use React/TypeScript/Vite and a Python FastAPI single-user local service. SQLite is derived; original bytes and versioned JSON sidecars are authoritative. Deployment binds to loopback by default; mount /data and /backups separately. No cloud photo processing, remote fonts, analytics, or fabricated archive records.

The alternatives considered were Tauri (native integration but unsuitable as the Docker runtime) and a browser-only application (cannot provide robust filesystem/SQLite backup guarantees). The container service fits the explicit deployment request. Windows login launch is a user-run helper, not a container changing the host's startup settings.

## Required surfaces
Today (camera, device/mirror/overlay, import, mood, diary, tags, city), month calendar and yearly heatmap, filtered paged timeline, day detail and primary-photo management, memories and comparison, offline locations, future letters, annual HTML report, and archive/settings/backup/restore/export controls. Mobile pairing is opt-in, expires, and exposes only staging uploads; desktop approval commits uploads.

## Storage and safety
archive.json; photos/YYYY/MM/date_uuid.ext; entries/YYYY/MM/date.json; letters/uuid.json; index/dayframe.sqlite3; derived thumbnails/cache/exports; trash and recovery. Enforce relative paths, prevent symlink escape, atomically replace metadata, preserve originals, keep metadata on missing photos, validate content and size, reject higher archive versions. Startup reprojects sidecars. Backups use SQLite backup API plus SHA256 manifest and a staging directory; restore goes to an empty destination, never merges. CSV/HTML export escapes content.

## Delivery
M0-M3 form the v1.0 day-use baseline. Implement M4-M6 where feasible and accurately document remaining native-device/environment verification. Docker image builds and smoke tests run in GitHub Actions, then publish to GHCR and attach a portable image archive to a versioned release. No false success claims when local Docker/camera/mobile hardware is unavailable.

## Design system
Quiet warm-white paper (#f8f7f3), white surfaces, charcoal text, muted sage (#587465), fine borders, restrained serif display headings and system sans Chinese text. Fixed narrow navigation, spacious main content, real empty states rather than sample selfies. Primary photo composition on Today, small archive summary and recent-day strip. All controls remain semantic HTML; mobile sidebar collapses.
