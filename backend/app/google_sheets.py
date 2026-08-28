from typing import Any

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


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
    return {
        "value": _extract_effective_value(cell.get("effectiveValue")),
        "formattedValue": cell.get("formattedValue"),
        "formula": formula,
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
                "rowCount": grid_properties.get("rowCount"),
                "columnCount": grid_properties.get("columnCount"),
                "rows": rows,
            }
        )

    return {
        "spreadsheetId": spreadsheet.get("spreadsheetId"),
        "title": spreadsheet.get("properties", {}).get("title"),
        "sheets": sheets,
    }


def _map_http_error(exc: HttpError) -> SheetsAccessError:
    status_code = exc.resp.status if exc.resp else 500

    if status_code == 401:
        return SheetsAccessError(401, "Google access token is invalid or expired.")
    if status_code == 403:
        return SheetsAccessError(403, "You don't have access to this spreadsheet.")
    if status_code == 404:
        return SheetsAccessError(404, "Spreadsheet not found.")
    return SheetsAccessError(502, "Google Sheets API request failed.")
