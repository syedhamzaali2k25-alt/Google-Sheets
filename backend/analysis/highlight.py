"""Builds and clears the "Highlight duplicates in Sheet" formatting
requests used by POST /sheets/{id}/highlight-duplicates and
.../clear-highlights.

Scoped deliberately narrow: the only thing ever built here is a repeatCell
request that sets (or clears) a cell's background color on a range taken
directly from a Finding the backend itself just computed as highlightable
(see Finding.highlightable in analysis.health_score) — never a range
supplied by the client, and never any other formatting property, cell
value, or formula. This is not a general auto-fix system.
"""

from __future__ import annotations

import re
from typing import Any

from analysis.health_score import Finding
from analysis.structure import SpreadsheetStructure, column_index_from_letters

# The same critical-tier tint used throughout the dashboard/report (see
# extension/src/lib/theme.ts TIER_TINT.critical and
# extension/src/dashboard/severity.ts) — #FDE9E7 — reused here rather than
# inventing a new color, so a highlighted duplicate row visually matches the
# "critical" language used everywhere else in the report.
HIGHLIGHT_COLOR: dict[str, float] = {
    "red": 0xFD / 255,
    "green": 0xE9 / 255,
    "blue": 0xE7 / 255,
}

# "No fill" in practice: plain white, a sheet's default cell background —
# the Sheets API's CellFormat has no distinct "unset"/transparent value to
# restore to, so resetting to white is the standard way third-party tools
# clear a background tint they applied themselves.
CLEAR_COLOR: dict[str, float] = {"red": 1.0, "green": 1.0, "blue": 1.0}

_BACKGROUND_COLOR_FIELD = "userEnteredFormat.backgroundColor"

_RANGE_PART_RE = re.compile(r"^([A-Za-z]+)(\d+):([A-Za-z]+)(\d+)$")


def _parse_cell_range(cell_range: str, sheet_id_by_name: dict[str, int]) -> list[dict[str, Any]]:
    """Parses a "Sheet1!A45:Z45,A46:Z46" style cell_range — the same format
    every analysis.health_score finding uses — into Sheets API GridRange
    objects.

    Skips (rather than raising on) any part that isn't a simple
    "COL row:COL row" range or whose sheet name can't be resolved to a
    sheetId: a malformed or unexpected range should just be left out of the
    batch, not break the whole highlight request.
    """
    if "!" not in cell_range:
        return []
    sheet_name, _, ranges_part = cell_range.partition("!")
    sheet_id = sheet_id_by_name.get(sheet_name)
    if sheet_id is None:
        return []

    grid_ranges = []
    for part in ranges_part.split(","):
        match = _RANGE_PART_RE.match(part.strip())
        if not match:
            continue
        start_col, start_row, end_col, end_row = match.groups()
        grid_ranges.append(
            {
                "sheetId": sheet_id,
                "startRowIndex": int(start_row) - 1,
                "endRowIndex": int(end_row),
                "startColumnIndex": column_index_from_letters(start_col),
                "endColumnIndex": column_index_from_letters(end_col) + 1,
            }
        )
    return grid_ranges


def _repeat_cell_request(grid_range: dict[str, Any], color: dict[str, float]) -> dict[str, Any]:
    return {
        "repeatCell": {
            "range": grid_range,
            "cell": {"userEnteredFormat": {"backgroundColor": color}},
            "fields": _BACKGROUND_COLOR_FIELD,
        }
    }


def build_highlight_requests(structure: SpreadsheetStructure, findings: list[Finding]) -> list[dict[str, Any]]:
    """Turns every highlightable finding's cell_range into repeatCell
    batchUpdate requests that tint it with the critical-tier background
    color. A non-highlightable finding is skipped entirely — this is the
    one, single gate that decides what ever gets written to the sheet.
    """
    sheet_id_by_name = {sheet.name: sheet.sheet_id for sheet in structure.sheets if sheet.sheet_id is not None}

    requests: list[dict[str, Any]] = []
    for finding in findings:
        if not finding.highlightable:
            continue
        for grid_range in _parse_cell_range(finding.cell_range, sheet_id_by_name):
            requests.append(_repeat_cell_request(grid_range, HIGHLIGHT_COLOR))
    return requests


def build_clear_requests(ranges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resets a previously-recorded list of GridRange dicts (as stored in
    the applied_highlights table) back to no fill."""
    return [_repeat_cell_request(grid_range, CLEAR_COLOR) for grid_range in ranges]


def count_affected_cells(ranges: list[dict[str, Any]]) -> int:
    """Total number of cells covered by a list of GridRange dicts, for the
    highlight-duplicates endpoint's cells_affected response field."""
    total = 0
    for grid_range in ranges:
        rows = grid_range.get("endRowIndex", 0) - grid_range.get("startRowIndex", 0)
        cols = grid_range.get("endColumnIndex", 0) - grid_range.get("startColumnIndex", 0)
        total += max(0, rows) * max(0, cols)
    return total
