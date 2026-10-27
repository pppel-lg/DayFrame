# DayFrame Windows desktop design

Source: the user's `prompt(1).md` and eight supplied desktop reference images, 2026-10-27. The user requests implementation, testing, building and GitHub delivery without repeated confirmation.

## Intent and constraints

Convert the existing Docker application into a real Windows 10/11 x64 application using Tauri v2, React, FastAPI and a PyInstaller sidecar. Preserve Docker support, all eight pages, immutable originals, archive format v1, JSON authority, rebuildable SQLite, verified backups, offline locations, plaintext future letters, exports and opt-in phone uploads. Never test against personal archives. Version desktop release independently as 1.1.0; never replace v1.0.0 assets.

## Architecture

Tauri starts the bundled sidecar with piped stdin/stdout and a per-launch secret. The sidecar binds an OS-assigned IPv4 loopback socket, initializes an exclusive archive lease, and reports readiness only after application startup. Tauri independently checks health before navigating to a one-time bootstrap URL. The backend serves the real React bundle and API from the same origin, retaining Host, Origin and HttpOnly SameSite cookie checks; desktop endpoints additionally require the bootstrap cookie. No wildcard CORS or public admin listener. Closing stdin requests graceful shutdown; a Windows Job Object guarantees descendant cleanup on a crash. Tauri single-instance support prevents repeat launches.

Persistent default directories: `%LOCALAPPDATA%/DayFrame/{Archive,Backups,Logs,Settings}`. Path configuration is outside the installation and PyInstaller extraction directories. Directory changes validate permissions, do not move or overwrite archives, and take effect on restart. The archive lease prevents two applications opening the same archive. FFmpeg and its distribution notices ship with the sidecar.

## Visual specification

The supplied images are the accepted reference, so no replacement concept is needed. Warm paper background #f8f7f2, white panels #ffffff, sage primary #71836a, dark text #252822, muted text #81857b, borders #e8e9e2. Use local Chinese sans for controls and a local Chinese serif for large headings. Narrow fixed white sidebar with sprout mark, eight navigation items, selected pale sage row, quiet storage footer. Main area: large left-aligned page title, supporting copy and a small quotation with leaf detail; consistent 12px panel radii and 20px gaps.

Today uses equally weighted camera and journal panels above seven recent dates. Calendar has a month grid plus selected-day detail. Timeline uses chronological rows. Memories groups same-day history and two-date comparison. Letters has an inline composer next to locked and readable lists. Annual report shows real totals, heatmap, mood distribution, tag/city summaries and photo highlights. Settings uses two columns for storage, maintenance, pairing and privacy. Preserve all existing controls beyond the reference and genuine empty states; do not seed fake user records.

## Decisions

Reuse the existing React/FastAPI business code instead of rewriting it. A same-origin sidecar avoids weakening browser security for Tauri custom origins. Bundle WebView2 offline installer in NSIS. Use current-user installation, native window decorations, high DPI handling and a 1000×600 minimum window with initial working-area clamping. This lower minimum height lets a 1080p display at 150% scaling keep the title bar and taskbar accessible; content scrolls. No app auto-start or LAN firewall changes without an explicit user action.

## Verification and delivery

Run existing backend tests and production frontend build before and after changes. Add tests for desktop authentication, loopback binding, launch/close/restart, path validation and packaged resources. Use disposable archives for real HTTP and Playwright acceptance, synthetic camera, backup/restore, HTML/CSV and MP4 export. Build and silently install the actual NSIS package on Windows CI, launch the installed app, check React/API and process cleanup, then upload an artifact and SHA256SUMS. Publish a new release only after all required jobs pass. State actual local/CI results, hardware-camera and clean-second-PC gaps, unsigned status and any permission blocker honestly.
