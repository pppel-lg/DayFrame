# DayFrame Windows Desktop Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans and dispatch independent subsystems with superpowers:dispatching-parallel-agents. Track verified steps below.

**Goal:** Deliver a reference-matched, independently runnable Windows desktop application and a real installer/release.

**Architecture:** Tauri manages a PyInstaller FastAPI sidecar; React and the API share its random loopback origin. Persistent archives and settings live outside the installation. Existing archive and Docker contracts remain compatible.

**Tech Stack:** Tauri v2, Rust, Python 3.12, FastAPI, PyInstaller, FFmpeg, React 19, TypeScript, Vite, NSIS.

**Spec:** `docs/superpowers/specs/2026-10-27-windows-desktop-design.md` and user-provided `prompt(1).md`.

## Global Constraints

- Windows 10/11 x64; desktop 1.1.0; no overwrite of v1.0.0 assets.
- Core functionality is offline. Preserve archive format v1 and original bytes.
- No CORS bypass, no public administration listener, no fake encryption claims.
- Never use personal archives for tests or commit private photos or credentials.
- All new runtime behavior receives meaningful tests; visual edits use browser acceptance.

## Review Focus

- Chinese/space paths and unwritable/overlapping backup directories must fail clearly before switching archives.
- Port 8765 occupied must not prevent a random-port desktop launch.
- Close/crash/repeat launch must release the archive and terminate all descendants.
- Requests from other origins and unauthenticated desktop clients must not expose archive content.
- Installation/update/uninstall must preserve independent user data and require no development runtimes.

### Task 1: Desktop backend and persistence

Files: `backend/dayframe/desktop.py`, `desktop_entry.py`, `main.py`, `exports.py`; `backend/tests/test_desktop.py`.

Interface: stdin receives one JSON line `{token, data_home?}`; stdout emits `DAYFRAME_READY {"port": number}` after Uvicorn startup. `DAYFRAME_DATA_HOME` overrides home only for isolated tests. `/desktop/launch?token=...` establishes cookie and redirects to `/`. `/api/desktop` returns `{desktop:true,paths:{archive,backups},pending_restart:boolean}`; `PUT /api/desktop/paths` validates/persists `{archive,backups}` and returns pending restart. These routes do not exist in ordinary Docker mode. `FRONTEND_DIST` and `DAYFRAME_FFMPEG` explicitly select bundled resources. A blank line or EOF on stdin requests shutdown.

- [x] Write and observe failing tests for config, cookie bootstrap, guarded API and subprocess startup/EOF shutdown.
- [x] Implement loopback port-0 server and atomic path settings with existing archive lease and graceful shutdown.
- [x] Verify focused tests and full backend suite, including FFmpeg path handling.

### Task 2: Reference-based React interface

Files: `frontend/src/{App,ui,Today,Archive,Memories,Letters,Settings}.tsx`, styles, local assets and frontend package metadata.

Interface: preserve existing API and props; optional desktop API above. Native `choose_directory` returns `string|null`; `restart_desktop` restarts the managed application. Detect Tauri using `window.__TAURI_INTERNALS__` and call its invoke or `@tauri-apps/api/core`. Ordinary Docker UI never invokes native commands.

- [x] Inspect the supplied reference images and existing business components.
- [x] Implement shared typography/palette/shell and eight layouts without removing functions.
- [x] Verify production build and real browser workflows at desktop and small widths; visually inspect screenshots beside references.

### Task 3: Native lifecycle, packaging and installed smoke

Files: root `package.json`, `src-tauri/**`, `desktop/ui/index.html`, `scripts/build-sidecar.py`, `requirements-desktop.txt`, `scripts/windows-smoke.py`.

Interface: consumes Task 1 launch protocol; bundles `dayframe-server-x86_64-pc-windows-msvc.exe`, frontend and FFmpeg. Native commands from Task 2 validate the active same-origin webview. Test-only `DAYFRAME_DATA_HOME`/`DAYFRAME_SMOKE_STATUS` isolate data and emit nonsecret lifecycle diagnostics for installed-app smoke.

- [x] Define native window, single instance, readiness/health check, graceful stdin shutdown and Windows process-tree job ownership.
- [x] Build a PyInstaller sidecar with frontend, codec runtime and licenses; verify the packaged binary using a disposable archive.
- [x] Configure current-user NSIS installation and offline WebView2; run installed smoke including reopen, occupied port and process cleanup.

### Task 4: CI, documentation and release

Files: `.github/workflows/windows-release.yml`, README, Windows install/build/architecture/migration docs, verification record.

- [x] Preserve original Docker workflow and add independent PR/push/manual Windows build and smoke.
- [x] Upload real nonempty installer, SHA256SUMS and verification logs; release only after successful checks, using 1.1.0.
- [x] Verify branch changes and tests, commit/push if authentication permits, monitor CI and repair build failures.
- [x] Report actual installer bytes/hash/download link or the exact remaining blocker.

Completion evidence (2026-10-28 Asia/Taipei): release v1.1.0, source 3f4c2d4625851d03560d0656033e5aad5c7ed8d5, successful workflow https://github.com/pppel-lg/DayFrame/actions/runs/40547896070, merged PR1. Physical-device and OS-dialog gaps are recorded in docs/VERIFICATION.md.
