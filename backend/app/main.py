import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from analysis.change_history import (
    ChangeHistoryAccessError,
    ChangeHistoryReport,
    fetch_change_activity_cached,
    summarize_change_history,
)
from analysis.documentation import SpreadsheetDocumentation, build_documentation
from analysis.export import generate_pdf_report
from analysis.health_score import CategoryWeights, HealthReport, compute_health_report
from analysis.highlight import build_clear_requests, build_highlight_requests, count_affected_cells
from analysis.structure import SpreadsheetStructure, build_spreadsheet_structure
from app.auth import TokenVerificationError, get_user_email_sync, verify_access_token
from app.db import get_db
from app.google_sheets import SheetsAccessError, apply_batch_update, fetch_spreadsheet_raw_cached
from app.rate_limit import DEFAULT_BURST, DEFAULT_REQUESTS_PER_MINUTE, RateLimiter, RateLimitMiddleware
from app.repository import (
    delete_applied_highlight,
    get_applied_highlight,
    get_or_create_user,
    save_report,
    upsert_applied_highlight,
)

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer()

# A packed (non-dev) Chrome extension has a fixed origin of the form
# chrome-extension://<extension-id>. During local development the unpacked
# extension's id changes per machine/load, so we fall back to allowing any
# chrome-extension:// origin unless a specific one is provided.
EXTENSION_ORIGIN = os.getenv("EXTENSION_ORIGIN")

app = FastAPI(title="Google Sheet Insights Backend")

# Named so tests can reset it between runs — this limiter is a singleton
# for the process's lifetime, shared by every request the app instance
# handles (see RateLimiter.reset()'s docstring).
rate_limiter = RateLimiter(DEFAULT_REQUESTS_PER_MINUTE, DEFAULT_BURST)

# Starlette applies middleware outside-in in the *reverse* of add_middleware
# call order — the last one added ends up outermost. RateLimitMiddleware
# must be added before CORSMiddleware so CORS stays outermost and still
# attaches its headers to a 429 the rate limiter short-circuits, rather
# than the browser reporting a confusing CORS failure instead of the real
# "too many requests" response.
app.add_middleware(RateLimitMiddleware, limiter=rate_limiter)
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


class HighlightResponse(BaseModel):
    success: bool
    ranges_highlighted: int = 0
    cells_affected: int = 0
    error: str | None = None


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
        return fetch_spreadsheet_raw_cached(payload.access_token, spreadsheet_id)
    except SheetsAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.post("/sheets/{spreadsheet_id}/structure", response_model=SpreadsheetStructure)
def get_spreadsheet_structure(spreadsheet_id: str, payload: AccessTokenRequest) -> SpreadsheetStructure:
    try:
        raw = fetch_spreadsheet_raw_cached(payload.access_token, spreadsheet_id)
    except SheetsAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return build_spreadsheet_structure(raw)


@app.post("/sheets/{spreadsheet_id}/health", response_model=HealthReport)
def get_spreadsheet_health(
    spreadsheet_id: str, payload: HealthReportRequest, db: Session = Depends(get_db)
) -> HealthReport:
    try:
        raw = fetch_spreadsheet_raw_cached(payload.access_token, spreadsheet_id)
    except SheetsAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    structure = build_spreadsheet_structure(raw)
    try:
        health = compute_health_report(structure, raw, weights=payload.weights)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _persist_report_best_effort(db, payload.access_token, spreadsheet_id, raw.get("title") or "", health)
    return health


def _persist_report_best_effort(
    db: Session, access_token: str, spreadsheet_id: str, spreadsheet_title: str, health: HealthReport
) -> None:
    """Records this health report so scores can be tracked over time.
    Never lets a persistence failure (DB down, email scope not granted,
    etc.) fail the request that already has a perfectly good report to
    return — this is a side effect, not the point of the endpoint.
    """
    try:
        email = get_user_email_sync(access_token)
        if not email:
            return
        user = get_or_create_user(db, email)
        save_report(db, user, spreadsheet_id, spreadsheet_title, health)
    except Exception:
        logger.exception("Failed to persist health report for spreadsheet %s.", spreadsheet_id)


@app.post("/sheets/{spreadsheet_id}/documentation", response_model=SpreadsheetDocumentation)
def get_spreadsheet_documentation(spreadsheet_id: str, payload: AccessTokenRequest) -> SpreadsheetDocumentation:
    try:
        raw = fetch_spreadsheet_raw_cached(payload.access_token, spreadsheet_id)
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
        activity_response = fetch_change_activity_cached(
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
        raw = fetch_spreadsheet_raw_cached(payload.access_token, spreadsheet_id)
    except SheetsAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    structure = build_spreadsheet_structure(raw)
    health = compute_health_report(structure, raw)
    documentation = build_documentation(structure)

    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(days=payload.days)
    try:
        activity_response = fetch_change_activity_cached(
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


@app.post("/sheets/{spreadsheet_id}/highlight-duplicates", response_model=HighlightResponse)
def highlight_duplicate_rows(
    spreadsheet_id: str, payload: AccessTokenRequest, db: Session = Depends(get_db)
) -> HighlightResponse:
    """Writes a light red tint onto every "fully duplicated rows" finding's
    cell range in the user's actual Google Sheet. Entirely re-computed from
    the token + spreadsheet_id on every call — the client never gets to
    name a range; only ranges this request itself just derived from a
    highlightable Finding are ever touched, and only background color is
    ever written.
    """
    try:
        raw = fetch_spreadsheet_raw_cached(payload.access_token, spreadsheet_id)
    except SheetsAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    structure = build_spreadsheet_structure(raw)
    try:
        health = compute_health_report(structure, raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    email = get_user_email_sync(payload.access_token)
    if not email:
        return HighlightResponse(
            success=False,
            error="Could not verify your Google account, so this backend can't safely track "
            "(and later clear) highlights for this spreadsheet.",
        )
    user = get_or_create_user(db, email)

    # Clear whatever was highlighted last time first — those rows may no
    # longer be duplicates after edits since the last call. Delete the
    # record immediately after a successful clear (rather than waiting
    # until the very end) so a failure applying the *new* highlights below
    # never leaves the database claiming ranges are highlighted when they
    # were in fact just cleared.
    existing = get_applied_highlight(db, user, spreadsheet_id)
    if existing is not None:
        try:
            apply_batch_update(payload.access_token, spreadsheet_id, build_clear_requests(existing.ranges))
        except SheetsAccessError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
        delete_applied_highlight(db, user, spreadsheet_id)

    requests = build_highlight_requests(structure, health.findings)
    if not requests:
        return HighlightResponse(success=True, ranges_highlighted=0, cells_affected=0)

    try:
        apply_batch_update(payload.access_token, spreadsheet_id, requests)
    except SheetsAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    grid_ranges = [request["repeatCell"]["range"] for request in requests]
    upsert_applied_highlight(db, user, spreadsheet_id, grid_ranges)

    return HighlightResponse(
        success=True,
        ranges_highlighted=len(grid_ranges),
        cells_affected=count_affected_cells(grid_ranges),
    )


@app.post("/sheets/{spreadsheet_id}/clear-highlights", response_model=HighlightResponse)
def clear_duplicate_highlights(
    spreadsheet_id: str, payload: AccessTokenRequest, db: Session = Depends(get_db)
) -> HighlightResponse:
    """Clears whatever this backend last recorded as highlighted for this
    spreadsheet, without applying anything new."""
    email = get_user_email_sync(payload.access_token)
    if not email:
        return HighlightResponse(
            success=False, error="Could not verify your Google account for this spreadsheet."
        )
    user = get_or_create_user(db, email)

    existing = get_applied_highlight(db, user, spreadsheet_id)
    if existing is None or not existing.ranges:
        return HighlightResponse(success=True, ranges_highlighted=0, cells_affected=0)

    try:
        apply_batch_update(payload.access_token, spreadsheet_id, build_clear_requests(existing.ranges))
    except SheetsAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    delete_applied_highlight(db, user, spreadsheet_id)
    return HighlightResponse(success=True, ranges_highlighted=0, cells_affected=0)
