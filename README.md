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

- **Popup** (`src/popup`) — pings the backend's `/health` endpoint on open and
  shows whether it's reachable, plus a "Connect Google Account" button that
  runs the OAuth flow and verifies the resulting token with the backend.
- **Content script** (`src/content/content-script.ts`) — injected into
  `docs.google.com/spreadsheets/*` and `sheets.google.com/*`, currently just
  logs that it loaded.

Run the backend first (or update `shared/constants.json` if it's hosted
elsewhere) so the popup's status check has something to reach.

### Google OAuth setup

The popup's "Connect Google Account" button uses `chrome.identity.getAuthToken`,
which requires an OAuth client registered with Google:

1. Load the unpacked extension once (see above) so Chrome assigns it an id —
   copy the id from `chrome://extensions`.
2. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials),
   create an OAuth 2.0 Client ID of type **Chrome Extension**, using that
   extension id.
3. Enable the **Google Sheets API** and **Google Drive API** for the project.
4. Copy the generated client id into `extension/manifest.config.ts`
   (`oauth2.client_id`), replacing the `YOUR_GOOGLE_OAUTH_CLIENT_ID...`
   placeholder, and rebuild the extension.

The extension requests two read-only scopes:
`spreadsheets.readonly` and `drive.metadata.readonly` (see
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
category and every structure check without any network access or real
Google credentials.

## Running both together

1. Start the backend (`uvicorn app.main:app --reload --port 8000`).
2. Build or run the extension (`npm run dev` / `npm run build`) and load
   `extension/dist` as an unpacked extension.
3. Open the extension's popup — it should show "Backend: online".
4. Click "Connect Google Account" (requires the OAuth setup above) — on
   success the popup shows "Verified with backend."
5. Open a Google Sheet and check the browser console for the content
   script's log line.
