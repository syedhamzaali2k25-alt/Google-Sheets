import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from analysis.change_history import (
    ChangeHistoryAccessError,
    ChangeHistoryReport,
    fetch_change_activity,
    summarize_change_history,
)
from analysis.documentation import SpreadsheetDocumentation, build_documentation
from analysis.export import generate_pdf_report
from analysis.health_score import CategoryWeights, HealthReport, compute_health_report
from analysis.structure import SpreadsheetStructure, build_spreadsheet_structure
from app.auth import TokenVerificationError, verify_access_token
from app.google_sheets import SheetsAccessError, fetch_spreadsheet_raw

bearer_scheme = HTTPBearer()

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


class HealthReportRequest(BaseModel):
    access_token: str
    weights: CategoryWeights | None = None


class ExportRequest(BaseModel):
    access_token: str
    days: int = 30


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


@app.post("/sheets/{spreadsheet_id}/health", response_model=HealthReport)
def get_spreadsheet_health(spreadsheet_id: str, payload: HealthReportRequest) -> HealthReport:
    try:
        raw = fetch_spreadsheet_raw(payload.access_token, spreadsheet_id)
    except SheetsAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    structure = build_spreadsheet_structure(raw)
    try:
        return compute_health_report(structure, raw, weights=payload.weights)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/sheets/{spreadsheet_id}/documentation", response_model=SpreadsheetDocumentation)
def get_spreadsheet_documentation(spreadsheet_id: str, payload: AccessTokenRequest) -> SpreadsheetDocumentation:
    try:
        raw = fetch_spreadsheet_raw(payload.access_token, spreadsheet_id)
    except SheetsAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    structure = build_spreadsheet_structure(raw)
    return build_documentation(structure)


@app.get("/sheets/{spreadsheet_id}/changes", response_model=ChangeHistoryReport)
def get_spreadsheet_changes(
    spreadsheet_id: str,
    days: int = 30,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> ChangeHistoryReport:
    if not 1 <= days <= 365:
        raise HTTPException(status_code=400, detail="`days` must be between 1 and 365.")

    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(days=days)

    try:
        activity_response = fetch_change_activity(
            credentials.credentials, spreadsheet_id, since=window_start, until=window_end
        )
    except ChangeHistoryAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return summarize_change_history(activity_response, spreadsheet_id, window_start, window_end)


@app.post("/sheets/{spreadsheet_id}/export")
def export_spreadsheet_report(spreadsheet_id: str, payload: ExportRequest) -> Response:
    if not 1 <= payload.days <= 365:
        raise HTTPException(status_code=400, detail="`days` must be between 1 and 365.")

    try:
        raw = fetch_spreadsheet_raw(payload.access_token, spreadsheet_id)
    except SheetsAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    structure = build_spreadsheet_structure(raw)
    health = compute_health_report(structure, raw)
    documentation = build_documentation(structure)

    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(days=payload.days)
    try:
        activity_response = fetch_change_activity(
            payload.access_token, spreadsheet_id, since=window_start, until=window_end
        )
    except ChangeHistoryAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    changes = summarize_change_history(activity_response, spreadsheet_id, window_start, window_end)

    pdf_bytes = generate_pdf_report(spreadsheet_id, health, documentation, changes)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{spreadsheet_id}-insights-report.pdf"'},
    )
