# google-sheet-insights

Scaffolding for a Chrome extension that will surface insights inside Google
Sheets, backed by a FastAPI service. No business logic yet — this repo just
wires up a working popup, content script, and API that talk to each other.

## Structure

```
extension/   Chrome extension (Manifest V3), React + TypeScript, built with Vite
backend/     Python FastAPI backend
shared/      Types/constants used by both the extension and the backend
```

## Prerequisites

- Node.js 20+ and npm
- Python 3.11+

## Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Verify it's up:

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"google-sheet-insights-backend"}
```

CORS is enabled for `chrome-extension://*` origins by default (fine for local
development, where the unpacked extension's id varies by machine). To lock it
down to one extension id, set `EXTENSION_ORIGIN` before starting the server:

```bash
EXTENSION_ORIGIN=chrome-extension://<your-extension-id> uvicorn app.main:app --reload --port 8000
```

Optionally set `ANTHROPIC_API_KEY` to enable AI-polished documentation from
`POST /sheets/{spreadsheet_id}/documentation` (see the API section below) —
everything else works with no key set.

## Extension

```bash
cd extension
npm install
npm run dev
```

`npm run dev` starts Vite in watch mode. To load the extension in Chrome:

1. Run `npm run build` (or leave `npm run dev` running — it rebuilds into `dist/` on save).
2. Open `chrome://extensions`.
3. Enable "Developer mode".
4. Click "Load unpacked" and select `extension/dist`.

The extension has:

- **Popup** (`src/popup`) — pings the backend's `/health` endpoint on open,
  a "Connect Google Account" button that runs the OAuth flow and verifies
  the resulting token with the backend, and an "Analyze Sheet" button that
  reads the active tab's URL (via the `activeTab` permission) for a Google
  Sheets id and opens the dashboard in a new tab.
- **Dashboard** (`src/dashboard`) — a full-tab page (`chrome.tabs.create()`,
  not the cramped popup window) styled with Tailwind CSS. It reads
  `?spreadsheetId=...` from its own URL, gets a Google access token
  (reusing the popup's cached token where possible), then calls the health,
  documentation, and change-history endpoints **in parallel**
  (`Promise.allSettled`, so one endpoint failing doesn't block the other
  two) and renders three tabs:
  - **Dashboard** — the overall health score as a ring gauge, the five
    category scores as bars, and findings grouped by severity
    (high/medium/low), each with its cell range and recommended action.
  - **Documentation** — the workbook summary, one card per sheet, detected
    cross-sheet relationships, and a badge showing whether it's rule-based
    or AI-enhanced.
  - **Change Analytics** — total edits, a bar chart of activity per day,
    top contributors, unusual-activity flags, and the API's
    `limited_data_warning` surfaced verbatim when the Drive Activity API
    could only provide file-level data.

  A "Share Report" button in the header (once the three panels have
  loaded) calls `POST /sheets/{spreadsheet_id}/export`, which combines all
  three into a single PDF, and downloads it via a blob URL — no extra
  Google permissions needed, since it reuses the token already in memory.

  Every tab shows its own error state independently if its endpoint call
  failed (a backend error's `detail` message is shown directly — e.g. a
  future row-count limit returning "This sheet has too many rows to
  analyze in the free tier" would render as-is), and there's a top-level
  loading state while the three calls are in flight and a "no spreadsheet
  selected" state if the dashboard is opened without the query param.
- **Content script** (`src/content/content-script.ts`) — injected into
  `docs.google.com/spreadsheets/*` and `sheets.google.com/*`, currently just
  logs that it loaded.

Run the backend first (or update `shared/constants.json` if it's hosted
elsewhere) so the popup's status check has something to reach.

The dashboard is a second build entry, not referenced anywhere in the
manifest (it's only ever opened via `chrome.tabs.create()`), so it's added
directly to `vite.config.ts`'s `build.rollupOptions.input` rather than being
auto-discovered by `@crxjs/vite-plugin` the way the popup is.

### Google OAuth setup

The popup's "Connect Google Account" button uses `chrome.identity.getAuthToken`,
which requires an OAuth client registered with Google:

1. Load the unpacked extension once (see above) so Chrome assigns it an id —
   copy the id from `chrome://extensions`.
2. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials),
   create an OAuth 2.0 Client ID of type **Chrome Extension**, using that
   extension id.
3. Enable the **Google Sheets API**, **Google Drive API**, and **Google
   Drive Activity API** for the project.
4. Copy the generated client id into `extension/manifest.config.ts`
   (`oauth2.client_id`), replacing the `YOUR_GOOGLE_OAUTH_CLIENT_ID...`
   placeholder, and rebuild the extension.

The extension requests three read-only scopes: `spreadsheets.readonly`,
`drive.metadata.readonly`, and `drive.activity.readonly` (see
`shared/constants.json` → `googleOAuthScopes`).

## Shared

`shared/` holds a JSON file of constants and a TypeScript file of types used
across the extension and backend — see `shared/README.md`.

## API

- `GET /health` — liveness check.
- `POST /auth/verify` — body `{"access_token": "..."}`; confirms the token
  with Google's tokeninfo endpoint and returns its granted scope/expiry, or
  `401` if it's invalid or expired.
- `POST /sheets/{spreadsheet_id}/raw` — body `{"access_token": "..."}`; uses
  the token to fetch every sheet's raw cell values and formulas via the
  Google Sheets API. Returns `401` for an invalid/expired token, `403` if the
  account can't access that spreadsheet, `404` if it doesn't exist.
- `POST /sheets/{spreadsheet_id}/structure` — same request/error shape as
  `/raw`, but returns a normalized `SpreadsheetStructure` (see
  `backend/analysis/structure.py`): sheet list (name, dimensions,
  hidden/visible), per-sheet column headers with an inferred type
  (`text`/`number`/`date`/`currency`/`formula`/`mixed`/`empty`), every
  formula's cell reference, named ranges, merged cells, and basic stats
  (total rows, non-empty cells, % empty).
- `POST /sheets/{spreadsheet_id}/health` — body `{"access_token": "...",
  "weights": {...}}` (`weights` optional); builds the `SpreadsheetStructure`
  above and runs it through `backend/analysis/health_score.py` to produce a
  `HealthReport`: an overall 0-100 score, a 0-100 score per category (`data
  quality`, `formula quality`, `structure`, `maintainability`, `security` —
  weighted equally by default, override any of the five in `weights`), and a
  list of findings (each with category, severity, description, affected cell
  range, and a recommendation), sorted highest-severity first. Same
  401/403/404 error handling as `/raw`; a `weights` object whose values sum
  to zero returns `400`.
- `POST /sheets/{spreadsheet_id}/documentation` — body `{"access_token":
  "..."}`; runs the `SpreadsheetStructure` through
  `backend/analysis/documentation.py` to produce a `SpreadsheetDocumentation`:
  a one-paragraph summary per sheet (what it contains, row count, key
  columns, formulas in plain language — e.g. "Total is calculated from Units
  × Unit Price"), detected cross-sheet relationships (a column name shared by
  two or more sheets), and a workbook-level "what this appears to do"
  summary. Same 401/403/404 error handling as `/raw`.

  This is rule-based by default (`source: "rule_based"`, no network calls).
  If `ANTHROPIC_API_KEY` is set in the backend's environment, the draft is
  sent to Claude to be rewritten into more natural prose covering the same
  facts (`source: "ai_enhanced"`); if the key is unset or the call fails for
  any reason, the endpoint silently falls back to the rule-based version —
  it never errors because of the AI step.
- `GET /sheets/{spreadsheet_id}/changes?days=30` — the access token goes in
  an `Authorization: Bearer <token>` header instead of the body (this is the
  one `GET` endpoint, and tokens don't belong in query strings/logs). Calls
  the **Google Drive Activity API** (`backend/analysis/change_history.py`)
  for the last `days` days (1-365, default 30) and returns a
  `ChangeHistoryReport`: total edit count, contributors with their edit
  counts (identified by Drive's opaque `people/...` id — resolving that to a
  name/email needs the People API, which isn't wired up here), and
  "unusual activity" flags (the file being deleted, sharing/permission
  changes, and bursts of 5+ edits by one person within 10 minutes).

  The Drive Activity API only reports **file-level** activity for a Sheets
  file — it has no concept of which sheet or cell range was touched. So
  `touched_ranges` is always empty and `data_granularity` is always
  `"file_level"` with a `limited_data_warning` explaining why, rather than
  the endpoint pretending to have range-level detail it doesn't have. Same
  401/403/404 error handling as the other endpoints; an out-of-range `days`
  returns `400`.
- `POST /sheets/{spreadsheet_id}/export` — body `{"access_token": "...",
  "days": 30}` (`days` optional, same 1-365 range as `/changes`). Builds the
  health report, documentation, and change history internally (one token
  covers all three, since the extension requests all three scopes together),
  then renders them into a single PDF with `backend/analysis/export.py`
  (ReportLab — pure Python, no native libraries to install, unlike an
  HTML-to-PDF renderer like WeasyPrint) and returns the PDF bytes directly
  with `Content-Type: application/pdf` and a `Content-Disposition` download
  header — there's no separate file-storage step or download-URL endpoint
  to manage. The PDF has a cover page (workbook name, spreadsheet id,
  generated date, overall score), a findings section (category scores plus
  every finding, highest severity first), a documentation section (workbook
  summary, per-sheet summaries, relationships), and a change activity
  section (contributors, unusual activity, the same limited-data warning as
  `/changes`). Same 401/403/404/400 error handling as the other endpoints.

### Testing the backend

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Unit tests run against a fixture spreadsheet at
`backend/tests/fixtures/sales_sheet_raw.json` — a mock "Sales" sheet with 9
data rows, a formula column, a duplicate row, a formula error (`#DIV/0!`), an
empty column, a column with no header, and a fake email address, plus a
hidden "Notes" sheet with a merged cell — exercising every health-score
category and every structure check — plus a mock Drive Activity API
response at `backend/tests/fixtures/drive_activity_sample.json` covering
two contributors, a burst of edits, a permission change, and a delete. The
PDF export tests build a real report from those same fixtures and check
its content with `pypdf` (extracted text, not just "produced valid bytes").
None of it needs network access or real Google credentials.

## Running both together

1. Start the backend (`uvicorn app.main:app --reload --port 8000`).
2. Build or run the extension (`npm run dev` / `npm run build`) and load
   `extension/dist` as an unpacked extension.
3. Open the extension's popup — it should show "Backend: online".
4. Click "Connect Google Account" (requires the OAuth setup above) — on
   success the popup shows "Verified with backend."
5. Open a Google Sheet and check the browser console for the content
   script's log line.
6. With that Google Sheet's tab active, click the popup's "Analyze Sheet"
   button — it opens the dashboard in a new tab, which authenticates, loads
   the health/documentation/change-history data in parallel, and shows the
   Dashboard / Documentation / Change Analytics tabs.
7. Click "Share Report" in the dashboard's header to download the combined
   PDF.
