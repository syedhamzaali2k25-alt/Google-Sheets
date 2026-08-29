# google-sheet-insights

A Chrome extension that analyzes a Google Sheet — a health score, plain-English
documentation, and edit history — and exports it all as a PDF report. React +
TypeScript extension (Manifest V3, built with Vite) backed by a Python FastAPI
service.

## Structure

```
extension/   Chrome extension (Manifest V3), React + TypeScript, built with Vite
backend/     Python FastAPI backend
shared/      Types/constants used by both the extension and the backend
```

## Prerequisites

- Node.js 20+ and npm
- Python 3.11+
- (Optional) PostgreSQL — see [Persistence](#persistence-users--report-history) below. SQLite works with zero setup.

## Environment variables

All backend configuration is via environment variables (or a `backend/.env`
loaded by your shell — there's no `.env.example` checked in, since every
variable below has a workable default for local development). None are
required to get the backend running; set what you need.

| Variable | Required? | Default | Purpose |
| --- | --- | --- | --- |
| `EXTENSION_ORIGIN` | No | any `chrome-extension://*` origin allowed | Lock CORS down to one extension id (`chrome-extension://<id>`) instead of any unpacked extension. |
| `ANTHROPIC_API_KEY` | No | unset (rule-based documentation only) | Enables AI-polished prose for `POST /sheets/{id}/documentation`. Falls back silently to rule-based text if unset or if the call fails. |
| `DATABASE_URL` | No | `sqlite:///./dev.db` | Where health reports are persisted. Point this at Postgres in any real deployment, e.g. `postgresql+psycopg://user:password@host:5432/dbname`. |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | No | `60` | Token-bucket refill rate per client IP. |
| `RATE_LIMIT_BURST` | No | `20` | Token-bucket capacity per client IP (also the max burst before a `429`). |

There is **no Google OAuth client secret to configure on the backend** — the
extension authenticates via `chrome.identity.getAuthToken`, which uses a
"Chrome Extension" type OAuth client that is a public client (id only, no
secret). The client id lives in `extension/manifest.config.ts`, not in an
environment variable — see [Google OAuth setup](#google-oauth-setup) below
for how to obtain and register one.

## Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head            # creates the users/reports tables (SQLite by default)
uvicorn app.main:app --reload --port 8000
```

Verify it's up:

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"google-sheet-insights-backend"}
```

`/health` is exempt from rate limiting; every other endpoint allows a burst of
`RATE_LIMIT_BURST` requests and refills at `RATE_LIMIT_REQUESTS_PER_MINUTE`
per minute per client IP, returning `429` with a `Retry-After` header once
exhausted (see [Rate limiting & caching](#rate-limiting--caching)).

CORS is enabled for `chrome-extension://*` origins by default (fine for local
development, where the unpacked extension's id varies by machine). To lock it
down to one extension id, set `EXTENSION_ORIGIN` before starting the server:

```bash
EXTENSION_ORIGIN=chrome-extension://<your-extension-id> uvicorn app.main:app --reload --port 8000
```

Optionally set `ANTHROPIC_API_KEY` to enable AI-polished documentation from
`POST /sheets/{spreadsheet_id}/documentation` (see the API section below) —
everything else works with no key set.

### Persistence (users & report history)

Every `POST /sheets/{id}/health` call best-effort records a `Report` row
(spreadsheet id/title, overall score, per-category scores, timestamp) against
a `User` looked up/created by the email in the caller's Google token — the
schema needed for a future "score history over time" Pro feature, even though
nothing reads that history back yet (see [What's stubbed](#whats-stubbed--mocked)).
This never blocks or fails the health-score response itself: if the database
is unreachable, or the token lacks the `userinfo.email` scope, the report is
silently skipped and only logged.

Schema lives in `backend/app/models.py`, managed with Alembic:

```bash
cd backend
alembic upgrade head                 # apply migrations (run once after cloning, and after pulling new ones)
alembic revision --autogenerate -m "description"   # after changing app/models.py — always review the generated file before committing
```

Defaults to a local SQLite file (`backend/dev.db`, gitignored) so there's
nothing to install for local dev. To use Postgres instead, set `DATABASE_URL`
before running either `alembic upgrade head` or `uvicorn`:

```bash
export DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/sheet_insights
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Rate limiting & caching

- **Rate limiting** (`app/rate_limit.py`) — an in-process token-bucket per
  client IP, applied as ASGI middleware ahead of every route except `/health`.
  Single-process only; a multi-worker deployment would need a shared store
  (e.g. Redis) for one limit to hold across all workers.
- **Caching** (`app/cache.py`) — re-analyzing the same unchanged spreadsheet
  doesn't re-hit the Google Sheets API: the raw sheet fetch is cached keyed by
  spreadsheet id *and* a one-way fingerprint of the caller's access token
  (never the resource id alone, so a cache hit can never leak one user's data
  to another), invalidated the moment Google Drive's `modifiedTime` for that
  file changes — not a blind TTL. Change-activity lookups use a shorter
  pure-TTL cache (2 minutes) since Drive Activity has no equivalent revision
  marker. Also single-process/in-memory for now.

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
  analyze in the free tier" would render as-is), a skeleton placeholder
  (`components/DashboardSkeleton.tsx`) shows while the three calls are in
  flight instead of a bare spinner, and there's a "no spreadsheet selected"
  state if the dashboard is opened without the query param.

  Both the popup and the dashboard are wrapped in a top-level React error
  boundary (`src/lib/ErrorBoundary.tsx`) so an unexpected rendering crash
  shows a "Something went wrong" fallback with a reload/retry button instead
  of a blank page; each dashboard tab also has its own inner error boundary,
  so a crash in one tab's rendering doesn't take down the other two or the
  header's Share Report button.
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
   (`oauth2.client_id`), replacing the existing value (a client id
   registered for development — a "Chrome Extension" OAuth client has no
   secret, so there's nothing else to configure), and rebuild the extension.

The extension requests four read-only scopes: `spreadsheets.readonly`,
`drive.metadata.readonly`, `drive.activity.readonly`, and `userinfo.email`
(the last one lets the backend attribute a health report to a user for the
persistence layer — see [Persistence](#persistence-users--report-history) —
without granting access to any other profile data). See
`shared/constants.json` → `googleOAuthScopes`.

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
None of it needs network access or real Google credentials, and none of it
touches Postgres — persistence tests use an in-memory SQLite database.

`tests/test_integration_e2e.py` is the top-level check that the whole thing
actually works together: it drives one mock spreadsheet through the real
FastAPI app (`raw` → `health` → `documentation` → `changes` → `export`),
the same sequence the dashboard performs, and asserts on the final PDF's
extracted text — plus that the raw-sheet cache collapsed what would
otherwise be four separate Google Sheets API calls into one.

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

## What's stubbed / mocked

Not exhaustive, but the gaps most likely to matter before a real pilot user
tries this:

- **Report history isn't surfaced anywhere.** `/health` records a `Report`
  row per call (score, category scores, timestamp), but there is no endpoint
  or UI reading it back — no "score over time" chart, no list of past
  reports. The schema (`app/models.py`) and storage (`app/repository.py`)
  exist; the "Pro" feature built on top of them does not.
- **No real user accounts/login.** A `User` row is an email address, looked
  up (and silently created) by whatever Google account granted the token —
  there's no signup flow, session, or way for a user to see their own
  account.
- **Contributor identity is Drive's opaque `people/...` id, not a name or
  email.** Resolving it needs the Google People API, which isn't wired up;
  the dashboard and PDF show the raw id.
- **Change history is file-level only**, not per-sheet or per-cell — a
  known and explained limitation of the Drive Activity API
  (`data_granularity: "file_level"`, plus a `limited_data_warning` in the
  API response), not something the extension hides.
- **AI-enhanced documentation is best-effort and optional.** With no
  `ANTHROPIC_API_KEY`, or if the Claude call fails for any reason,
  everything still works via the rule-based writer — there's no user-facing
  indication beyond the `source` field that this happened.
- **Caching and rate limiting are single-process/in-memory.** Fine for one
  backend instance; a multi-worker or multi-instance deployment would need
  a shared store (Redis, most likely) for either to actually hold across
  workers — see [Rate limiting & caching](#rate-limiting--caching).
- **No production deployment config.** No Dockerfile, no Postgres
  connection pooling/managed-instance setup, no HTTPS termination, no
  extension packaging/publishing to the Chrome Web Store — this is a local
  dev + unpacked-extension setup end to end.
- **No automated end-to-end test against a *real* Google account.** The
  integration test (and everything else in the test suite) runs against
  fixture JSON, not a live Sheets/Drive API call — there's no CI job that
  exercises real OAuth or real Google data.
