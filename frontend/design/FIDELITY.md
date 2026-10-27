# Dayframe visual verification

Reference: `concept.png`, generated with the built-in Image Gen tool before UI implementation. It contains a full primary desktop screen and calendar/settings continuation. The concept is a design reference, never rendered as the working UI.

Browser verification: Python Playwright Chromium, because the Browser plugin was unavailable. Parent integration QA used a 1505×1045 desktop viewport and 390px mobile viewport. Inspected with `view_image`: the reference, desktop empty and saved states, and mobile Today. Browser screenshots are temporary artifacts under `artifacts/browser/` and are not shipped as application assets.

## Comparison ledger

| Area | Reference / rendered comparison | Resolution |
| --- | --- | --- |
| Information hierarchy | Fixed narrow white sidebar, large daily heading, camera left, story form right | Same hierarchy; desktop camera capped at 440px to preserve the recent strip in the first viewport. |
| Palette | Warm paper, white surfaces, muted sage primary area, fine borders | Shared CSS tokens; no image tint, remote media, or gradients added. |
| Typography | Readable Chinese controls with distinct display heading | Bundled OFL Noto Sans SC locally after Linux browser fallback produced serif controls. Serif display headings follow the written design specification. |
| Navigation | Today, calendar, timeline, memories, locations, letters, report, settings | All eight labels retained and wired to real application surfaces. |
| Camera | Centered camera icon and two clear actions; preview and output mirror controls separated | Camera permission states, real capture, independent mirror settings, and a preview-only reference overlay implemented. |
| Metadata | Mood, diary, city, tags, save | Same field order. Custom mood disclosure and a 5000-character diary limit intentionally extend the concept to the production requirements. |
| Recent days | Seven genuine empty/photo slots and date labels | Seven dates derived from local today; no seeded personal photos or statistics. Mobile wraps into four then three slots. |
| Mobile | Primary action and form must remain accessible | Sidebar collapses behind an accessible navigation button; camera and story stack with no horizontal overflow. |

Above-the-fold copy was checked against the concept: brand, eight navigation labels, title, camera headline/supporting copy, camera/import actions, form headings, city/tags labels, mirror controls, save action and recent-days heading are retained. Intentional additions are the custom mood disclosure, optional-field hints, honest local storage text, and a preservation note explaining import/mirror behavior. Dynamic date, state, missing-original warnings and unfinished-save messages come from real state.

Core browser paths passed: synthetic camera capture and persisted diary/mood/city/tags; import bytes preserved; additional photos retain the existing primary; primary replacement requires confirmation; reload persistence; all eight routes; locked future letters; backup; restore to a new directory; 390px responsive layouts. Page and server errors were empty in the acceptance report.

Hardware camera quality, real phone Wi-Fi/firewall behavior and host operating-system startup remain environment-dependent verification. The UI accurately describes session reminders and the host startup helper; it does not offer a fake OS startup switch.
