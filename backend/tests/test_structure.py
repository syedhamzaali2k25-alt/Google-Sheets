import json
from pathlib import Path

import pytest

from analysis.structure import ColumnType, build_spreadsheet_structure

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sales_sheet_raw.json"


@pytest.fixture
def sales_raw() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


@pytest.fixture
def structure(sales_raw):
    return build_spreadsheet_structure(sales_raw)


def test_top_level_fields(structure):
    assert structure.spreadsheet_id == "mock-spreadsheet-id"
    assert structure.title == "Q1 Sales Tracker"


def test_sheets_list(structure):
    by_name = {s.name: s for s in structure.sheets}
    assert set(by_name) == {"Sales", "Notes"}

    assert by_name["Sales"].hidden is False
    assert by_name["Sales"].row_count == 10
    assert by_name["Sales"].column_count == 8

    assert by_name["Notes"].hidden is True
    assert by_name["Notes"].row_count == 2
    assert by_name["Notes"].column_count == 3


def test_column_headers_and_types(structure):
    sales_columns = next(c for c in structure.columns_by_sheet if c.sheet_name == "Sales")
    types_by_header = {col.header: col.inferred_type for col in sales_columns.columns}

    assert types_by_header == {
        "Date": ColumnType.DATE,
        "Product": ColumnType.TEXT,
        "Region": ColumnType.TEXT,
        "Units": ColumnType.NUMBER,
        "Unit Price": ColumnType.CURRENCY,
        "Total": ColumnType.FORMULA,
        "Comments": ColumnType.EMPTY,
        "Flag": ColumnType.MIXED,
    }


def test_formulas_extracted(structure):
    sales_formulas = [f for f in structure.formulas if f.sheet_name == "Sales"]
    assert len(sales_formulas) == 9

    by_cell = {f.cell: f.formula for f in sales_formulas}
    assert by_cell["F2"] == "=D2*E2"
    assert by_cell["F10"] == "=D10*E10"
    # No formulas anywhere outside the Total column.
    assert all(f.cell.startswith("F") for f in sales_formulas)


def test_named_ranges(structure):
    assert len(structure.named_ranges) == 1
    named_range = structure.named_ranges[0]
    assert named_range.name == "SalesData"
    assert named_range.sheet_name == "Sales"
    assert named_range.range_a1 == "A1:H10"


def test_merged_cells(structure):
    assert structure.merged_cells == [
        type(structure.merged_cells[0])(sheet_name="Notes", range_a1="A1:C1")
    ]


def test_stats(structure):
    # rowCount(Sales)=10 + rowCount(Notes)=2
    assert structure.stats.total_rows == 12

    # Sales: header (8) + 9 data rows * 7 non-empty cells each (Comments is
    # always empty) = 71. Notes: 1 non-empty cell per row * 2 rows = 2.
    assert structure.stats.total_non_empty_cells == 73

    # total_cells = 10*8 (Sales) + 2*3 (Notes) = 86
    assert structure.stats.percent_empty_cells == pytest.approx(15.12, abs=0.01)


def test_duplicate_row_does_not_break_analysis(structure):
    """The fixture intentionally repeats one Sales row (row 2 == row 7 minus
    the formula's cell reference); analysis should treat it like any other
    row rather than deduplicating or erroring."""
    sales_formulas = [f for f in structure.formulas if f.sheet_name == "Sales"]
    assert {"F2", "F7"}.issubset({f.cell for f in sales_formulas})


def test_empty_raw_spreadsheet_does_not_crash():
    structure = build_spreadsheet_structure(
        {"spreadsheetId": "empty", "title": "Empty", "sheets": []}
    )
    assert structure.sheets == []
    assert structure.stats.total_rows == 0
    assert structure.stats.percent_empty_cells == 0.0
