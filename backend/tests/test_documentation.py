import json
from pathlib import Path

import pytest

from analysis.documentation import (
    SpreadsheetDocumentation,
    build_documentation,
    enhance_documentation_with_ai,
    generate_documentation,
)
from analysis.structure import build_spreadsheet_structure

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sales_sheet_raw.json"


def _text_cell(value):
    return {"value": value, "formattedValue": value, "formula": None, "numberFormatType": None}


@pytest.fixture
def sales_structure():
    raw = json.loads(FIXTURE_PATH.read_text())
    return build_spreadsheet_structure(raw)


@pytest.fixture
def sales_doc(sales_structure):
    return generate_documentation(sales_structure)


# A small, purpose-built two-sheet workbook sharing a "Customer ID" column,
# used only to exercise cross-sheet relationship detection in isolation from
# the larger Step 2/3 Sales fixture.
RELATED_SHEETS_RAW = {
    "spreadsheetId": "crm-id",
    "title": "Mini CRM",
    "namedRanges": [],
    "sheets": [
        {
            "sheetId": 0,
            "title": "Orders",
            "hidden": False,
            "rowCount": 3,
            "columnCount": 2,
            "merges": [],
            "rows": [
                [_text_cell("Customer ID"), _text_cell("Amount")],
                [_text_cell("C1"), _text_cell("100")],
                [_text_cell("C2"), _text_cell("200")],
            ],
        },
        {
            "sheetId": 1,
            "title": "Customers",
            "hidden": False,
            "rowCount": 3,
            "columnCount": 2,
            "merges": [],
            "rows": [
                [_text_cell("Customer ID"), _text_cell("Name")],
                [_text_cell("C1"), _text_cell("Acme")],
                [_text_cell("C2"), _text_cell("Globex")],
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# Rule-based generation
# ---------------------------------------------------------------------------


def test_source_is_rule_based_without_ai(sales_doc):
    assert sales_doc.source == "rule_based"


def test_sheet_summary_mentions_row_count_and_columns(sales_doc):
    sales_summary = next(s for s in sales_doc.sheet_summaries if s.sheet_name == "Sales").summary
    assert "10 row" in sales_summary
    assert "Date" in sales_summary
    assert "Product" in sales_summary


def test_sheet_summary_describes_formula_in_plain_language(sales_doc):
    sales_summary = next(s for s in sales_doc.sheet_summaries if s.sheet_name == "Sales").summary
    # "Total" is a formula column computed as Units * Unit Price.
    assert "Total is calculated from Units × Unit Price" in sales_summary


def test_hidden_sheet_is_mentioned(sales_doc):
    notes_summary = next(s for s in sales_doc.sheet_summaries if s.sheet_name == "Notes").summary
    assert "hidden" in notes_summary.lower()


def test_every_sheet_gets_a_summary(sales_structure, sales_doc):
    documented_names = {s.sheet_name for s in sales_doc.sheet_summaries}
    assert documented_names == {sheet.name for sheet in sales_structure.sheets}


def test_workbook_summary_combines_all_sheets(sales_doc):
    assert "Sales" in sales_doc.workbook_summary
    assert "Notes" in sales_doc.workbook_summary
    assert "2 sheets" in sales_doc.workbook_summary


def test_no_relationships_when_no_shared_columns(sales_doc):
    # Sales and Notes share no column headers.
    assert sales_doc.relationships == []


def test_relationship_detected_across_sheets():
    structure = build_spreadsheet_structure(RELATED_SHEETS_RAW)
    doc = generate_documentation(structure)

    assert len(doc.relationships) == 1
    relationship = doc.relationships[0]
    assert relationship.column_name == "Customer ID"
    assert relationship.sheets == ["Customers", "Orders"]
    assert "Customer ID" in doc.workbook_summary


def test_empty_workbook_does_not_crash():
    structure = build_spreadsheet_structure({"spreadsheetId": "empty", "title": "Empty", "sheets": []})
    doc = generate_documentation(structure)
    assert doc.sheet_summaries == []
    assert doc.relationships == []
    assert "no sheets" in doc.workbook_summary.lower()


# ---------------------------------------------------------------------------
# Optional AI enhancement
# ---------------------------------------------------------------------------


def test_ai_enhancement_skipped_without_api_key(monkeypatch, sales_structure, sales_doc):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def _fail_if_constructed(*args, **kwargs):
        raise AssertionError("Anthropic client should not be constructed without an API key")

    monkeypatch.setattr("analysis.documentation.anthropic.Anthropic", _fail_if_constructed)

    result = enhance_documentation_with_ai(sales_doc, sales_structure)
    assert result is sales_doc
    assert result.source == "rule_based"


def test_ai_enhancement_falls_back_when_api_call_fails(monkeypatch, sales_structure, sales_doc):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class _BoomClient:
        class messages:
            @staticmethod
            def parse(**kwargs):
                raise RuntimeError("simulated API failure")

    monkeypatch.setattr("analysis.documentation.anthropic.Anthropic", lambda: _BoomClient())

    result = enhance_documentation_with_ai(sales_doc, sales_structure)
    assert result == sales_doc
    assert result.source == "rule_based"


def test_ai_enhancement_used_when_api_call_succeeds(monkeypatch, sales_structure, sales_doc):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    polished = SpreadsheetDocumentation(
        title=sales_doc.title,
        sheet_summaries=sales_doc.sheet_summaries,
        relationships=sales_doc.relationships,
        workbook_summary="A polished, human-friendly summary of this workbook.",
        source="rule_based",  # the function must override this to "ai_enhanced"
    )

    class _FakeResponse:
        parsed_output = polished

    class _FakeClient:
        class messages:
            @staticmethod
            def parse(**kwargs):
                assert kwargs["output_format"] is SpreadsheetDocumentation
                return _FakeResponse()

    monkeypatch.setattr("analysis.documentation.anthropic.Anthropic", lambda: _FakeClient())

    result = enhance_documentation_with_ai(sales_doc, sales_structure)
    assert result.source == "ai_enhanced"
    assert result.workbook_summary == "A polished, human-friendly summary of this workbook."


def test_build_documentation_falls_back_end_to_end(monkeypatch, sales_structure):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = build_documentation(sales_structure)
    assert result.source == "rule_based"
