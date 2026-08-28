import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from analysis.structure import SpreadsheetStructure, build_spreadsheet_structure
from app.auth import TokenVerificationError, verify_access_token
from app.google_sheets import SheetsAccessError, fetch_spreadsheet_raw

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


class AccessTokenRequest(BaseModel):
    access_token: str


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "google-sheet-insights-backend"}


@app.post("/auth/verify")
async def verify_auth(payload: AccessTokenRequest) -> dict:
    try:
        token_info = await verify_access_token(payload.access_token)
    except TokenVerificationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return {
        "valid": True,
        "scope": token_info.get("scope"),
        "expiresIn": token_info.get("expires_in"),
        "audience": token_info.get("aud"),
    }


@app.post("/sheets/{spreadsheet_id}/raw")
def get_spreadsheet_raw(spreadsheet_id: str, payload: AccessTokenRequest) -> dict:
    try:
        return fetch_spreadsheet_raw(payload.access_token, spreadsheet_id)
    except SheetsAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.post("/sheets/{spreadsheet_id}/structure", response_model=SpreadsheetStructure)
def get_spreadsheet_structure(spreadsheet_id: str, payload: AccessTokenRequest) -> SpreadsheetStructure:
    try:
        raw = fetch_spreadsheet_raw(payload.access_token, spreadsheet_id)
    except SheetsAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return build_spreadsheet_structure(raw)
