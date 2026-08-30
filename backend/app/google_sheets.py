from typing import Any

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.cache import RevisionCache, token_fingerprint

# Keyed by "<token fingerprint>:<spreadsheet id>" (see app/cache.py for why
# the token fingerprint has to be part of the key). TTL is generous because
# freshness is actually enforced by the Drive modifiedTime revision check,
# not by this timer — the timer just bounds memory for tokens that are
# never seen again (e.g. revoked, or the user disconnects).
_RAW_CACHE_TTL_SECONDS = 30 * 60
_raw_cache: RevisionCache[dict[str, Any]] = RevisionCache(_RAW_CACHE_TTL_SECONDS)


class SheetsAccessError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _extract_effective_value(effective_value: dict[str, Any] | None) -> Any:
    if not effective_value:
        return None
    if "errorValue" in effective_value:
        return {"error": effective_value["errorValue"].get("message", "Unknown error")}
    for key in ("stringValue", "numberValue", "boolValue"):
        if key in effective_value:
            return effective_value[key]
    return None


def _extract_cell(cell: dict[str, Any]) -> dict[str, Any] | None:
    if not cell:
        return None
    formula = (cell.get("userEnteredValue") or {}).get("formulaValue")
    number_format_type = (cell.get("userEnteredFormat") or {}).get("numberFormat", {}).get("type")
    return {
        "value": _extract_effective_value(cell.get("effectiveValue")),
        "formattedValue": cell.get("formattedValue"),
        "formula": formula,
        "numberFormatType": number_format_type,
    }


def _extract_range(range_: dict[str, Any]) -> dict[str, Any]:
    return {
        "sheetId": range_.get("sheetId"),
        "startRowIndex": range_.get("startRowIndex", 0),
        "endRowIndex": range_.get("endRowIndex"),
        "startColumnIndex": range_.get("startColumnIndex", 0),
        "endColumnIndex": range_.get("endColumnIndex"),
    }


def fetch_spreadsheet_raw(access_token: str, spreadsheet_id: str) -> dict[str, Any]:
    """Fetch every sheet's raw cell values and formulas for a spreadsheet.

    Runs synchronously (googleapiclient is not async) — call it from a sync
    FastAPI route so Starlette runs it in a worker thread.
    """
    credentials = Credentials(token=access_token)
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

    try:
        spreadsheet = (
            service.spreadsheets()
            .get(spreadsheetId=spreadsheet_id, includeGridData=True)
            .execute()
        )
    except HttpError as exc:
        raise _map_http_error(exc) from exc
    except RefreshError as exc:
        # A bare access token (no refresh_token) that Google rejects with 401
        # makes google-auth try to refresh it, which fails with this instead
        # of surfacing the original HttpError.
        raise SheetsAccessError(
            401, "Google access token is invalid or expired."
        ) from exc

    sheets = []
    for sheet in spreadsheet.get("sheets", []):
        properties = sheet.get("properties", {})
        grid_properties = properties.get("gridProperties", {})

        rows: list[list[dict[str, Any] | None]] = []
        for grid_data in sheet.get("data", []):
            for row_data in grid_data.get("rowData", []):
                rows.append([_extract_cell(cell) for cell in row_data.get("values", [])])

        sheets.append(
            {
                "sheetId": properties.get("sheetId"),
                "title": properties.get("title"),
                "hidden": properties.get("hidden", False),
                "rowCount": grid_properties.get("rowCount"),
                "columnCount": grid_properties.get("columnCount"),
                "rows": rows,
                "merges": [_extract_range(merge) for merge in sheet.get("merges", [])],
            }
        )

    named_ranges = [
        {"name": nr.get("name"), **_extract_range(nr.get("range", {}))}
        for nr in spreadsheet.get("namedRanges", [])
    ]

    return {
        "spreadsheetId": spreadsheet.get("spreadsheetId"),
        "title": spreadsheet.get("properties", {}).get("title"),
        "sheets": sheets,
        "namedRanges": named_ranges,
    }


def fetch_spreadsheet_revision(access_token: str, spreadsheet_id: str) -> str | None:
    """Looks up a spreadsheet's Drive modifiedTime — a cheap metadata call,
    much lighter than re-fetching the full grid — for use as a cache
    revision marker. Returns None (rather than raising) on any failure, so
    a caller can treat that as "can't verify freshness, skip the cache"
    instead of failing the whole request over what is just an optimization.
    """
    credentials = Credentials(token=access_token)
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    try:
        result = service.files().get(fileId=spreadsheet_id, fields="modifiedTime").execute()
    except (HttpError, RefreshError):
        return None
    return result.get("modifiedTime")


def fetch_spreadsheet_raw_cached(access_token: str, spreadsheet_id: str) -> dict[str, Any]:
    """Like fetch_spreadsheet_raw, but skips the expensive Sheets API grid
    fetch when the spreadsheet's Drive modifiedTime hasn't changed since it
    was last fetched with this same token.

    The revision check runs on every call, cache hit or not, using the
    *caller's own* access token — that's what makes this safe to share a
    cache key across requests: Google itself still enforces per-user
    authorization on that lightweight call before anything cached is
    returned, and the cache key is additionally scoped to a fingerprint of
    the token regardless (see app/cache.py).
    """
    revision = fetch_spreadsheet_revision(access_token, spreadsheet_id)
    cache_key = f"{token_fingerprint(access_token)}:{spreadsheet_id}"

    if revision is not None:
        cached = _raw_cache.get(cache_key, revision)
        if cached is not None:
            return cached

    raw = fetch_spreadsheet_raw(access_token, spreadsheet_id)
    if revision is not None:
        _raw_cache.set(cache_key, raw, revision)
    return raw


def apply_batch_update(
    access_token: str, spreadsheet_id: str, requests: list[dict[str, Any]]
) -> dict[str, Any]:
    """Applies a batchUpdate of the given requests to a spreadsheet.

    This is the only write path this backend has, used exclusively by the
    "Highlight duplicates in Sheet" feature's repeatCell requests (see
    analysis/highlight.py) — never for arbitrary requests. Same error
    handling as fetch_spreadsheet_raw. The incoming-request rate limit that
    already protects every endpoint (app.rate_limit.RateLimitMiddleware)
    covers the highlight endpoints too, so there's no separate outbound
    backoff layer to add here.
    """
    if not requests:
        return {}

    credentials = Credentials(token=access_token)
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

    try:
        return (
            service.spreadsheets()
            .batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests})
            .execute()
        )
    except HttpError as exc:
        raise _map_http_error(exc) from exc
    except RefreshError as exc:
        raise SheetsAccessError(401, "Google access token is invalid or expired.") from exc


def _map_http_error(exc: HttpError) -> SheetsAccessError:
    status_code = exc.resp.status if exc.resp else 500

    if status_code == 401:
        return SheetsAccessError(401, "Google access token is invalid or expired.")
    if status_code == 403:
        return SheetsAccessError(403, "You don't have access to this spreadsheet.")
    if status_code == 404:
        return SheetsAccessError(404, "Spreadsheet not found.")
    return SheetsAccessError(502, "Google Sheets API request failed.")
