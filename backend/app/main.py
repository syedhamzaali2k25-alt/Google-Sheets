import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# A packed (non-dev) Chrome extension has a fixed origin of the form
# chrome-extension://<extension-id>. During local development the unpacked
# extension's id changes per machine/load, so we fall back to allowing any
# chrome-extension:// origin unless a specific one is provided.
EXTENSION_ORIGIN = os.getenv("EXTENSION_ORIGIN")

app = FastAPI(title="Google Sheet Insights Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[EXTENSION_ORIGIN] if EXTENSION_ORIGIN else [],
    allow_origin_regex=r"chrome-extension://.*" if not EXTENSION_ORIGIN else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "google-sheet-insights-backend"}
