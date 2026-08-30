import json
from pathlib import Path

import pytest

from analysis.health_score import (
    Category,
    CategoryWeights,
    Severity,
    compute_health_report,
)
from analysis.structure import build_spreadsheet_structure

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sales_sheet_raw.json"


@pytest.fixture
def raw() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


@pytest.fixture
def report(raw):
    structure = build_spreadsheet_structure(raw)
    return compute_health_report(structure, raw)


def _findings_in(report, category: Category) -> list:
    return [f for f in report.findings if f.category == category]


# ---------------------------------------------------------------------------
# One failing case per category (per the fixture's known defects)
# ---------------------------------------------------------------------------


def test_data_quality_flags_duplicate_row(report):
    findings = _findings_in(report, Category.DATA_QUALITY)
    assert any(
        f.severity == Severity.HIGH
        and "duplicat" in f.description.lower()
        and "2" in f.description
        and f.highlightable
        for f in findings
    ), findings


def test_only_duplicate_row_findings_are_highlightable(report):
    for finding in report.findings:
        is_duplicate_row_finding = "duplicat" in finding.description.lower()
        assert finding.highlightable == is_duplicate_row_finding, finding


def test_formula_quality_flags_div_zero_error(report):
    findings = _findings_in(report, Category.FORMULA_QUALITY)
    assert any(
        f.severity == Severity.HIGH and f.cell_range == "Sales!F5" and "#DIV/0!" in f.description
        for f in findings
    ), findings


def test_structure_flags_empty_column_and_hidden_sheet(report):
    findings = _findings_in(report, Category.STRUCTURE)
    assert any(f.cell_range == "Sales!G:G" for f in findings), findings  # Comments column
    assert any("hidden" in f.description.lower() and "Notes" in f.description for f in findings), findings
    assert any(f.cell_range == "Notes!A1:C1" for f in findings), findings  # merged cell


def test_maintainability_flags_missing_header(report):
    findings = _findings_in(report, Category.MAINTAINABILITY)
    assert any(
        f.severity == Severity.HIGH and f.cell_range == "Sales!I1" and "no header" in f.description.lower()
        for f in findings
    ), findings


def test_security_flags_fake_email(report):
    findings = _findings_in(report, Category.SECURITY)
    assert any(
        f.cell_range == "Sales!I9" and "email" in f.description.lower() for f in findings
    ), findings


# ---------------------------------------------------------------------------
# Scoring mechanics
# ---------------------------------------------------------------------------


def test_category_scores_reflect_findings(report):
    # duplicate row (high, -25) + Flag column mixed types (medium, -12)
    assert report.category_scores.data_quality == pytest.approx(63.0)
    # one #DIV/0! error (high, -25)
    assert report.category_scores.formula_quality == pytest.approx(75.0)
    # hidden sheet + merge + irregular shape + 3 empty columns, all low (-5 each)
    assert report.category_scores.structure == pytest.approx(70.0)
    # three missing-header columns, all high (-25 each), clamped at 0
    assert report.category_scores.maintainability == pytest.approx(25.0)
    # one fake email, medium (-12)
    assert report.category_scores.security == pytest.approx(88.0)


def test_overall_score_is_equally_weighted_average(report):
    expected = (63.0 + 75.0 + 70.0 + 25.0 + 88.0) / 5
    assert report.overall_score == pytest.approx(expected, abs=0.01)
    assert report.weights == CategoryWeights()


def test_findings_sorted_highest_severity_first(report):
    severity_rank = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
    ranks = [severity_rank[f.severity] for f in report.findings]
    assert ranks == sorted(ranks)
    assert report.findings[0].severity == Severity.HIGH


def test_every_finding_has_actionable_fields(report):
    for finding in report.findings:
        assert finding.description
        assert finding.recommendation
        assert "!" in finding.cell_range


# ---------------------------------------------------------------------------
# Configurable weights
# ---------------------------------------------------------------------------


def test_custom_weights_change_overall_score(raw):
    structure = build_spreadsheet_structure(raw)

    # Weight maintainability (the worst-scoring category) at 100%.
    heavy_maintainability = CategoryWeights(
        data_quality=0, formula_quality=0, structure=0, maintainability=1, security=0
    )
    report = compute_health_report(structure, raw, weights=heavy_maintainability)
    assert report.overall_score == pytest.approx(report.category_scores.maintainability)


def test_weights_are_normalized_when_they_dont_sum_to_one(raw):
    structure = build_spreadsheet_structure(raw)

    # Equivalent to equal weighting, just not pre-normalized.
    unnormalized = CategoryWeights(
        data_quality=1, formula_quality=1, structure=1, maintainability=1, security=1
    )
    default_report = compute_health_report(structure, raw)
    scaled_report = compute_health_report(structure, raw, weights=unnormalized)
    assert scaled_report.overall_score == pytest.approx(default_report.overall_score)


def test_zero_weights_raise_value_error(raw):
    structure = build_spreadsheet_structure(raw)
    zero_weights = CategoryWeights(
        data_quality=0, formula_quality=0, structure=0, maintainability=0, security=0
    )
    with pytest.raises(ValueError):
        compute_health_report(structure, raw, weights=zero_weights)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_clean_spreadsheet_scores_100():
    raw = {
        "spreadsheetId": "clean",
        "title": "Clean",
        "sheets": [
            {
                "sheetId": 0,
                "title": "Data",
                "hidden": False,
                "rowCount": 2,
                "columnCount": 1,
                "merges": [],
                "rows": [
                    [{"value": "Name", "formattedValue": "Name", "formula": None, "numberFormatType": None}],
                    [{"value": "Alice", "formattedValue": "Alice", "formula": None, "numberFormatType": None}],
                ],
            }
        ],
        "namedRanges": [],
    }
    structure = build_spreadsheet_structure(raw)
    report = compute_health_report(structure, raw)
    assert report.overall_score == 100.0
    assert report.findings == []
