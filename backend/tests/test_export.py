import json
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader

from analysis.change_history import summarize_change_history
from analysis.documentation import generate_documentation
from analysis.export import generate_pdf_report
from analysis.health_score import compute_health_report
from analysis.structure import build_spreadsheet_structure

SALES_FIXTURE = Path(__file__).parent / "fixtures" / "sales_sheet_raw.json"
ACTIVITY_FIXTURE = Path(__file__).parent / "fixtures" / "drive_activity_sample.json"


def _normalize(text: str) -> str:
    """Collapses whitespace/newlines so assertions don't depend on exactly
    where ReportLab happened to wrap a paragraph onto a new line."""
    return re.sub(r"\s+", " ", text)


@pytest.fixture
def report_bytes() -> bytes:
    sales_raw = json.loads(SALES_FIXTURE.read_text())
    activity_raw = json.loads(ACTIVITY_FIXTURE.read_text())

    structure = build_spreadsheet_structure(sales_raw)
    health = compute_health_report(structure, sales_raw)
    documentation = generate_documentation(structure)
    changes = summarize_change_history(
        activity_raw,
        "mock-spreadsheet-id",
        datetime(2024, 5, 1, tzinfo=timezone.utc),
        datetime(2024, 5, 6, tzinfo=timezone.utc),
    )

    return generate_pdf_report("mock-spreadsheet-id", health, documentation, changes)


@pytest.fixture
def report_text(report_bytes) -> str:
    reader = PdfReader(BytesIO(report_bytes))
    return _normalize("\n".join(page.extract_text() for page in reader.pages))


@pytest.fixture
def cover_text(report_bytes) -> str:
    reader = PdfReader(BytesIO(report_bytes))
    return _normalize(reader.pages[0].extract_text())


def test_report_is_a_valid_pdf(report_bytes):
    assert report_bytes[:5] == b"%PDF-"
    assert len(report_bytes) > 1000


def test_report_has_one_page_per_section_plus_cover(report_bytes):
    reader = PdfReader(BytesIO(report_bytes))
    # cover, findings (may spill onto a 2nd page), documentation, changes
    assert len(reader.pages) >= 4


def test_cover_page_shows_title_score_and_id(cover_text):
    assert "Google Sheet Insights Report" in cover_text
    assert "Q1 Sales Tracker" in cover_text
    assert "64" in cover_text
    assert "mock-spreadsheet-id" in cover_text


def test_findings_section_lists_findings(report_text):
    assert "Health & Findings" in report_text
    assert "13 finding" in report_text
    assert "Sales!F5" in report_text
    assert "#DIV/0!" in report_text


def test_documentation_section_has_sheet_summaries(report_text):
    assert "Documentation" in report_text
    assert "Sales" in report_text
    assert "Total is calculated from Units" in report_text


def test_changes_section_has_contributors_and_warning(report_text):
    assert "Change Activity" in report_text
    assert "Total edits: 6" in report_text
    assert "people/200" in report_text
    assert "file-level activity" in report_text


def test_changes_section_lists_unusual_activity(report_text):
    lowered = report_text.lower()
    assert "unusual activity" in lowered
    assert "bulk edit" in lowered
    assert "deleted" in lowered


def test_empty_report_does_not_crash():
    empty_structure = build_spreadsheet_structure({"spreadsheetId": "empty", "title": "Empty", "sheets": []})
    health = compute_health_report(empty_structure, {"spreadsheetId": "empty", "title": "Empty", "sheets": []})
    documentation = generate_documentation(empty_structure)
    changes = summarize_change_history(
        {"activities": []},
        "empty",
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 31, tzinfo=timezone.utc),
    )

    pdf_bytes = generate_pdf_report("empty", health, documentation, changes)
    assert pdf_bytes[:5] == b"%PDF-"
