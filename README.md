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
  shows whether it's reachable.
- **Content script** (`src/content/content-script.ts`) — injected into
  `docs.google.com/spreadsheets/*` and `sheets.google.com/*`, currently just
  logs that it loaded.

Run the backend first (or update `shared/constants.json` if it's hosted
elsewhere) so the popup's status check has something to reach.

## Shared

`shared/` holds a JSON file of constants and a TypeScript file of types used
across the extension and backend — see `shared/README.md`.

## Running both together

1. Start the backend (`uvicorn app.main:app --reload --port 8000`).
2. Build or run the extension (`npm run dev` / `npm run build`) and load
   `extension/dist` as an unpacked extension.
3. Open the extension's popup — it should show "Backend: online".
4. Open a Google Sheet and check the browser console for the content
   script's log line.
