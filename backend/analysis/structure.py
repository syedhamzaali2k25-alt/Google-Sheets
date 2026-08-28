"""Extracts a normalized structure from the raw Sheets API response produced
by app.google_sheets.fetch_spreadsheet_raw (the same shape returned by
POST /sheets/{spreadsheet_id}/raw).
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel


class ColumnType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    CURRENCY = "currency"
    FORMULA = "formula"
    MIXED = "mixed"
    EMPTY = "empty"


class SheetInfo(BaseModel):
    name: str
    row_count: int
    column_count: int
    hidden: bool


class ColumnInfo(BaseModel):
    index: int
    header: str | None
    inferred_type: ColumnType


class SheetColumns(BaseModel):
    sheet_name: str
    columns: list[ColumnInfo]


class FormulaRef(BaseModel):
    sheet_name: str
    cell: str
    formula: str


class NamedRange(BaseModel):
    name: str
    sheet_name: str | None
    range_a1: str | None


class MergedRange(BaseModel):
    sheet_name: str
    range_a1: str


class SpreadsheetStats(BaseModel):
    total_rows: int
    total_non_empty_cells: int
    percent_empty_cells: float


class SpreadsheetStructure(BaseModel):
    spreadsheet_id: str
    title: str
    sheets: list[SheetInfo]
    columns_by_sheet: list[SheetColumns]
    formulas: list[FormulaRef]
    named_ranges: list[NamedRange]
    merged_cells: list[MergedRange]
    stats: SpreadsheetStats


_CURRENCY_FORMAT_TYPES = {"CURRENCY"}
_DATE_FORMAT_TYPES = {"DATE", "DATE_TIME"}
_NUMBER_FORMAT_TYPES = {"NUMBER", "PERCENT", "SCIENTIFIC", "TIME"}


def column_letters(index: int) -> str:
    """0-based column index -> spreadsheet column letters (0 -> "A")."""
    index += 1
    letters = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def cell_ref(row_index: int, col_index: int) -> str:
    return f"{column_letters(col_index)}{row_index + 1}"


def _range_to_a1(range_: dict[str, Any]) -> str | None:
    start_row = range_.get("startRowIndex") or 0
    start_col = range_.get("startColumnIndex") or 0
    end_row = range_.get("endRowIndex")
    end_col = range_.get("endColumnIndex")
    if end_row is None or end_col is None:
        return None

    start = cell_ref(start_row, start_col)
    end = cell_ref(end_row - 1, end_col - 1)
    return start if start == end else f"{start}:{end}"


def cell_is_non_empty(cell: dict[str, Any] | None) -> bool:
    if not cell:
        return False
    if cell.get("formula"):
        return True
    if cell.get("value") is not None:
        return True
    return bool(cell.get("formattedValue"))


def _classify_cell(cell: dict[str, Any] | None) -> str | None:
    """Returns a ColumnType value for one cell, or None if the cell is empty."""
    if not cell_is_non_empty(cell):
        return None
    if cell.get("formula"):
        return ColumnType.FORMULA.value

    number_format_type = cell.get("numberFormatType")
    if number_format_type in _CURRENCY_FORMAT_TYPES:
        return ColumnType.CURRENCY.value
    if number_format_type in _DATE_FORMAT_TYPES:
        return ColumnType.DATE.value
    if number_format_type in _NUMBER_FORMAT_TYPES:
        return ColumnType.NUMBER.value

    value = cell.get("value")
    if isinstance(value, bool):
        return ColumnType.TEXT.value
    if isinstance(value, (int, float)):
        return ColumnType.NUMBER.value
    return ColumnType.TEXT.value


def _infer_column_type(data_rows: list[list[dict[str, Any] | None]], col_index: int) -> ColumnType:
    types_seen: set[str] = set()
    for row in data_rows:
        cell = row[col_index] if col_index < len(row) else None
        classified = _classify_cell(cell)
        if classified is not None:
            types_seen.add(classified)

    if not types_seen:
        return ColumnType.EMPTY
    if len(types_seen) == 1:
        return ColumnType(next(iter(types_seen)))
    return ColumnType.MIXED


def _cell_display(cell: dict[str, Any] | None) -> str | None:
    if not cell:
        return None
    if cell.get("formattedValue"):
        return cell["formattedValue"]
    value = cell.get("value")
    return None if value is None else str(value)


def build_spreadsheet_structure(raw: dict[str, Any]) -> SpreadsheetStructure:
    sheets_info: list[SheetInfo] = []
    columns_by_sheet: list[SheetColumns] = []
    formulas: list[FormulaRef] = []
    merged_cells: list[MergedRange] = []
    sheet_id_to_name: dict[Any, str] = {}
    total_non_empty_cells = 0

    for sheet in raw.get("sheets", []):
        name = sheet.get("title") or ""
        row_count = sheet.get("rowCount") or 0
        column_count = sheet.get("columnCount") or 0
        rows: list[list[dict[str, Any] | None]] = sheet.get("rows") or []

        sheet_id_to_name[sheet.get("sheetId")] = name
        sheets_info.append(
            SheetInfo(
                name=name,
                row_count=row_count,
                column_count=column_count,
                hidden=bool(sheet.get("hidden", False)),
            )
        )

        for row_index, row in enumerate(rows):
            for col_index, cell in enumerate(row):
                if cell_is_non_empty(cell):
                    total_non_empty_cells += 1
                if cell and cell.get("formula"):
                    formulas.append(
                        FormulaRef(
                            sheet_name=name,
                            cell=cell_ref(row_index, col_index),
                            formula=cell["formula"],
                        )
                    )

        # Column headers/types are inferred over the data actually present,
        # not the sheet's declared (often padded) grid dimensions.
        header_row = rows[0] if rows else []
        data_rows = rows[1:]
        data_width = max((len(row) for row in rows), default=0)

        columns = [
            ColumnInfo(
                index=col_index,
                header=_cell_display(header_row[col_index] if col_index < len(header_row) else None),
                inferred_type=_infer_column_type(data_rows, col_index),
            )
            for col_index in range(data_width)
        ]
        columns_by_sheet.append(SheetColumns(sheet_name=name, columns=columns))

        for merge in sheet.get("merges", []):
            range_a1 = _range_to_a1(merge)
            if range_a1:
                merged_cells.append(MergedRange(sheet_name=name, range_a1=range_a1))

    named_ranges = [
        NamedRange(
            name=nr.get("name") or "",
            sheet_name=sheet_id_to_name.get(nr.get("sheetId")),
            range_a1=_range_to_a1(nr),
        )
        for nr in raw.get("namedRanges", [])
    ]

    total_rows = sum(s.row_count for s in sheets_info)
    total_cells = sum(s.row_count * s.column_count for s in sheets_info)
    percent_empty_cells = (
        round((1 - total_non_empty_cells / total_cells) * 100, 2) if total_cells else 0.0
    )

    return SpreadsheetStructure(
        spreadsheet_id=raw.get("spreadsheetId") or "",
        title=raw.get("title") or "",
        sheets=sheets_info,
        columns_by_sheet=columns_by_sheet,
        formulas=formulas,
        named_ranges=named_ranges,
        merged_cells=merged_cells,
        stats=SpreadsheetStats(
            total_rows=total_rows,
            total_non_empty_cells=total_non_empty_cells,
            percent_empty_cells=percent_empty_cells,
        ),
    )
