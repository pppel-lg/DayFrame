# Desktop reference implementation

The eight user-supplied images are the accepted design. They are not replaced by generated concepts or copied into the app as raster UI.

## Shared system

- Paper `#f8f7f2`, white panels `#ffffff`, sage `#71836a`, ink `#252822`, muted `#81857b`, borders `#e8e9e2`.
- Locally bundled Noto Sans SC for controls; locally bundled Noto Serif SC 600/700 for display headings. Both are SIL Open Font License 1.1. Fontsource packages resolve to version 5.3.1.
- Fixed 200px white sidebar, sprout mark, pale sage selection, quiet storage footer; paper canvas with 12px panel radii and 20px gaps.
- Today has equal camera and journal columns; the calendar has a month grid and selected-day detail; timeline records form chronological rows; letters use an inline composer beside locked and readable groups.
- The annual report uses API statistics plus all daily entries in the selected year (at most 366) for the heatmap, mood distribution, tags, cities and photo highlights. The app never seeds illustrative records.
- Settings has independent columns. Desktop directory selection, queued path settings and restart are available only when the Tauri bridge exists. Docker retains its directory guidance and never invokes native commands.

## Reference review

| Comparison            | Evidence and implementation                                                                                                                                  |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Palette and framing   | Warm paper, white panels, restrained sage controls; no replacement dark camera hero.                                                                         |
| Typography            | Large dark Chinese serif titles, serif panel headings, local sans controls.                                                                                  |
| Navigation            | Narrow white rail, sprout wordmark, all eight routes, pale sage active row and storage footer.                                                               |
| Today                 | Equal panel widths, separate photo/import buttons, all camera and mirror controls, seven dated recent records.                                               |
| Calendar and timeline | Month selection updates the adjacent day detail; timeline rows retain filters, pagination and day editing.                                                   |
| Letters               | Inline composer, future/readable groups, clear plaintext-storage disclosure. Locked letter bodies are never fabricated or shown.                             |
| Report                | Real totals, photo-count heatmap, real mood proportions, tag/city counts and actual photo mosaic. Empty archives show zero totals and explicit empty states. |
| Settings              | Paths, reminders, camera/calendar preferences, maintenance, backup/restore, calendar exports, opt-in pairing and privacy remain reachable.                   |

Intentional differences from the illustrative images: dates and counts come from the actual archive; no example photos or records are inserted; existing custom moods, year view, metadata rules and maintenance controls remain; settings may scroll to retain these controls. Letters are plaintext and make no encryption claim. The report includes a working HTML export and the browser print stylesheet for PDF printing. OS window chrome belongs to Tauri.

## Acceptance evidence

Browser plugin was unavailable, so acceptance used the installed Playwright Python Chromium runtime against a separate loopback server and disposable temporary archives. No personal archive was accessed.

- Production TypeScript/Vite build passes.
- All eight desktop routes render; all eight fit the 1000×720 minimum window width.
- Synthetic camera → capture → mood/journal/city/tags → save succeeds against the real API.
- Calendar selection/day dialog/year view, timeline filter/clear, future-letter creation, real HTML report job, original/export download attributes, and print CSS pass.
- Today, calendar, timeline, letters, report and settings fit a 390px viewport without document-level horizontal overflow. The annual heatmap scrolls inside its panel.
- No JavaScript page errors occurred in the acceptance runs.
- Desktop browse → path PUT → pending restart → native restart passes with a mocked bridge and desktop API. Actual native lifecycle and installer verification belong to the desktop integration smoke test.

Local screenshots and temporary acceptance scripts are kept outside the repository at `C:/Users/HP/AppData/Local/Temp/dayframe-ui-reference-20261027/`. Main screenshots: `today-empty.png`, `calendar-saved.png`, `timeline-saved.png`, `letters-saved.png`, `report-saved.png`, `settings-native.png`, and `*-mobile.png`.
