"""Computes a 0-100 health score across five weighted categories for a
spreadsheet.

Takes the SpreadsheetStructure produced by analysis.structure (Step 2) plus
the raw Sheets API response it was built from (Step 1) — several checks
(duplicate rows, blank fields, formula error results, PII-looking values)
need actual cell content, which the normalized structure intentionally
leaves out to stay compact.
"""

import re
from collections import Counter, defaultdict
from enum import Enum
from typing import Any

from pydantic import BaseModel

from analysis.structure import (
    ColumnInfo,
    ColumnType,
    FormulaRef,
    SheetInfo,
    SpreadsheetStructure,
    cell_is_non_empty,
    cell_ref,
    column_letters,
)


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Category(str, Enum):
    DATA_QUALITY = "data_quality"
    FORMULA_QUALITY = "formula_quality"
    STRUCTURE = "structure"
    MAINTAINABILITY = "maintainability"
    SECURITY = "security"


_SEVERITY_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
_SEVERITY_PENALTY = {Severity.HIGH: 25.0, Severity.MEDIUM: 12.0, Severity.LOW: 5.0}


class Finding(BaseModel):
    category: Category
    severity: Severity
    description: str
    cell_range: str
    recommendation: str
    # True only for the "fully duplicated rows" check below. Gates the
    # dashboard's "Highlight in Sheet" write-back feature — the frontend
    # must never infer this by matching on `description` text, and the
    # highlight endpoint (backend/analysis/highlight.py) never touches a
    # finding's cell_range unless this is set.
    highlightable: bool = False


class CategoryWeights(BaseModel):
    data_quality: float = 0.2
    formula_quality: float = 0.2
    structure: float = 0.2
    maintainability: float = 0.2
    security: float = 0.2

    def as_dict(self) -> dict[Category, float]:
        return {
            Category.DATA_QUALITY: self.data_quality,
            Category.FORMULA_QUALITY: self.formula_quality,
            Category.STRUCTURE: self.structure,
            Category.MAINTAINABILITY: self.maintainability,
            Category.SECURITY: self.security,
        }

    def normalized(self) -> dict[Category, float]:
        weights = self.as_dict()
        total = sum(weights.values())
        if total <= 0:
            raise ValueError("Category weights must sum to a positive number.")
        return {category: value / total for category, value in weights.items()}


class CategoryScores(BaseModel):
    data_quality: float
    formula_quality: float
    structure: float
    maintainability: float
    security: float


class HealthReport(BaseModel):
    overall_score: float
    category_scores: CategoryScores
    weights: CategoryWeights
    findings: list[Finding]


Cell = dict[str, Any] | None
Row = list[Cell]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _cell_text(cell: Cell) -> str | None:
    if not cell:
        return None
    formatted = cell.get("formattedValue")
    if formatted:
        return str(formatted)
    value = cell.get("value")
    return value if isinstance(value, str) else None


def _cell_at(row: Row, index: int) -> Cell:
    return row[index] if index < len(row) else None


# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------


def _check_duplicate_rows(sheet_name: str, data_rows: list[Row]) -> list[Finding]:
    if len(data_rows) < 2:
        return []

    width = max((len(row) for row in data_rows), default=0)
    signature_to_rows: dict[tuple, list[int]] = defaultdict(list)
    for row_index, row in enumerate(data_rows):
        # repr() keeps the signature hashable even when a cell's value is an
        # unhashable dict (e.g. a formula error like {"error": "..."}).
        signature = tuple(
            (repr(cell.get("value")), cell.get("formattedValue")) if cell else None
            for cell in (_cell_at(row, i) for i in range(width))
        )
        if any(part is not None for part in signature):
            signature_to_rows[signature].append(row_index)

    findings = []
    for row_indices in signature_to_rows.values():
        if len(row_indices) < 2:
            continue
        sheet_rows = [idx + 2 for idx in row_indices]
        ratio = len(row_indices) / len(data_rows)
        severity = Severity.HIGH if ratio > 0.2 else Severity.MEDIUM if ratio > 0.05 else Severity.LOW
        findings.append(
            Finding(
                category=Category.DATA_QUALITY,
                severity=severity,
                description=(
                    f"Sheet '{sheet_name}' rows {', '.join(map(str, sheet_rows))} are fully "
                    f"duplicated ({len(row_indices)} identical rows)."
                ),
                cell_range=f"{sheet_name}!" + ",".join(f"A{r}:Z{r}" for r in sheet_rows),
                recommendation="Remove or consolidate the duplicate rows.",
                highlightable=True,
            )
        )
    return findings


_OPTIONAL_HEADER_HINTS = ("comment", "note", "optional", "remark", "description")


def _check_blank_required_fields(
    sheet_name: str, data_rows: list[Row], columns: list[ColumnInfo]
) -> list[Finding]:
    if not data_rows:
        return []

    findings = []
    for col in columns:
        if col.inferred_type == ColumnType.EMPTY:
            continue  # an entirely unused column is a Structure finding, not this
        header_lower = (col.header or "").lower()
        if any(hint in header_lower for hint in _OPTIONAL_HEADER_HINTS):
            continue

        blanks = sum(1 for row in data_rows if not cell_is_non_empty(_cell_at(row, col.index)))
        if blanks == 0 or blanks == len(data_rows):
            continue
        ratio = blanks / len(data_rows)
        if ratio < 0.05:
            continue

        severity = Severity.HIGH if ratio > 0.3 else Severity.MEDIUM if ratio > 0.1 else Severity.LOW
        letter = column_letters(col.index)
        findings.append(
            Finding(
                category=Category.DATA_QUALITY,
                severity=severity,
                description=(
                    f"Column {letter} ('{col.header or 'unnamed'}') in sheet '{sheet_name}' is "
                    f"blank in {round(ratio * 100)}% of rows."
                ),
                cell_range=f"{sheet_name}!{letter}2:{letter}{len(data_rows) + 1}",
                recommendation="Fill in the missing values or confirm the field is genuinely optional.",
            )
        )
    return findings


_FORMAT_HINT_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"(?<!\d)(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"),
}


def _check_invalid_formats(
    sheet_name: str, data_rows: list[Row], columns: list[ColumnInfo]
) -> list[Finding]:
    findings = []
    for col in columns:
        header_lower = (col.header or "").lower()
        kind = next((k for k in _FORMAT_HINT_PATTERNS if k in header_lower), None)
        if kind is None:
            continue

        pattern = _FORMAT_HINT_PATTERNS[kind]
        bad_rows = [
            row_index + 2
            for row_index, row in enumerate(data_rows)
            if (text := _cell_text(_cell_at(row, col.index))) and not pattern.search(text)
        ]
        if not bad_rows:
            continue

        letter = column_letters(col.index)
        findings.append(
            Finding(
                category=Category.DATA_QUALITY,
                severity=Severity.MEDIUM,
                description=(
                    f"Column {letter} ('{col.header}') in sheet '{sheet_name}' looks like a "
                    f"{kind} field but {len(bad_rows)} value(s) don't match the expected format."
                ),
                cell_range=f"{sheet_name}!" + ",".join(f"{letter}{r}" for r in bad_rows),
                recommendation=f"Correct the flagged {kind} values.",
            )
        )
    return findings


def _check_inconsistent_types(sheet_name: str, columns: list[ColumnInfo]) -> list[Finding]:
    findings = []
    for col in columns:
        if col.inferred_type != ColumnType.MIXED:
            continue
        letter = column_letters(col.index)
        findings.append(
            Finding(
                category=Category.DATA_QUALITY,
                severity=Severity.MEDIUM,
                description=(
                    f"Column {letter} ('{col.header or 'unnamed'}') in sheet '{sheet_name}' "
                    f"mixes different value types."
                ),
                cell_range=f"{sheet_name}!{letter}:{letter}",
                recommendation="Standardize the column on a single data type.",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Formula Quality
# ---------------------------------------------------------------------------

_ERROR_TOKENS = {"#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NAME?", "#NULL!", "#NUM!"}


def _check_formula_errors(sheet_name: str, rows: list[Row]) -> list[Finding]:
    findings = []
    for row_index, row in enumerate(rows):
        for col_index, cell in enumerate(row):
            if not cell or not cell.get("formula"):
                continue
            value = cell.get("value")
            formatted = cell.get("formattedValue") or ""
            has_error = (isinstance(value, dict) and "error" in value) or formatted in _ERROR_TOKENS
            if not has_error:
                continue
            error_label = formatted or (value.get("error") if isinstance(value, dict) else "an error")
            ref = cell_ref(row_index, col_index)
            findings.append(
                Finding(
                    category=Category.FORMULA_QUALITY,
                    severity=Severity.HIGH,
                    description=f"Cell {ref} in sheet '{sheet_name}' evaluates to {error_label}.",
                    cell_range=f"{sheet_name}!{ref}",
                    recommendation="Fix the formula's inputs or references to clear the error.",
                )
            )
    return findings


def _normalize_formula(formula: str, row_number: int) -> str:
    """Replaces this cell's own row number with a placeholder so formulas
    like "=D2*E2" and "=D7*E7" normalize to the same pattern."""
    return re.sub(rf"(?<!\d){row_number}(?!\d)", "#", formula)


def _check_inconsistent_formulas(sheet_name: str, formulas: list[FormulaRef]) -> list[Finding]:
    by_column: dict[str, list[FormulaRef]] = defaultdict(list)
    for ref in formulas:
        match = re.match(r"[A-Za-z]+", ref.cell)
        if match:
            by_column[match.group()].append(ref)

    findings = []
    for letter, refs in by_column.items():
        if len(refs) < 2:
            continue

        normalized_map: dict[str, list[str]] = defaultdict(list)
        for ref in refs:
            row_match = re.search(r"\d+", ref.cell)
            row_number = int(row_match.group()) if row_match else 0
            normalized_map[_normalize_formula(ref.formula, row_number)].append(ref.cell)

        if len(normalized_map) <= 1:
            continue

        majority_pattern = max(normalized_map, key=lambda p: len(normalized_map[p]))
        outliers = [cell for pattern, cells in normalized_map.items() if pattern != majority_pattern for cell in cells]
        ratio = len(outliers) / len(refs)
        severity = Severity.HIGH if ratio > 0.3 else Severity.MEDIUM
        findings.append(
            Finding(
                category=Category.FORMULA_QUALITY,
                severity=severity,
                description=(
                    f"Column {letter} in sheet '{sheet_name}' has inconsistent formulas in "
                    f"{', '.join(sorted(outliers))} compared to the rest of the column."
                ),
                cell_range=f"{sheet_name}!" + ",".join(sorted(outliers)),
                recommendation="Make the formula pattern consistent across the column, then re-fill down.",
            )
        )
    return findings


def _check_suspicious_references(sheet_name: str, formulas: list[FormulaRef]) -> list[Finding]:
    return [
        Finding(
            category=Category.FORMULA_QUALITY,
            severity=Severity.HIGH,
            description=f"Formula in {sheet_name}!{ref.cell} references a deleted cell or range (#REF!).",
            cell_range=f"{sheet_name}!{ref.cell}",
            recommendation="Update the formula to point at a valid range.",
        )
        for ref in formulas
        if "#REF!" in ref.formula
    ]


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


def _check_empty_columns(sheet_name: str, columns: list[ColumnInfo]) -> list[Finding]:
    findings = []
    for col in columns:
        if col.inferred_type != ColumnType.EMPTY:
            continue
        letter = column_letters(col.index)
        findings.append(
            Finding(
                category=Category.STRUCTURE,
                severity=Severity.LOW,
                description=f"Column {letter} ('{col.header or 'unnamed'}') in sheet '{sheet_name}' has no data.",
                cell_range=f"{sheet_name}!{letter}:{letter}",
                recommendation="Remove the unused column or populate it.",
            )
        )
    return findings


def _check_merged_cells(structure: SpreadsheetStructure) -> list[Finding]:
    return [
        Finding(
            category=Category.STRUCTURE,
            severity=Severity.LOW,
            description=f"Merged range {merge.range_a1} in sheet '{merge.sheet_name}' can break sorting and filtering.",
            cell_range=f"{merge.sheet_name}!{merge.range_a1}",
            recommendation="Avoid merged cells inside data ranges; use cell formatting instead.",
        )
        for merge in structure.merged_cells
    ]


def _check_hidden_sheets(structure: SpreadsheetStructure) -> list[Finding]:
    return [
        Finding(
            category=Category.STRUCTURE,
            severity=Severity.LOW,
            description=f"Sheet '{sheet.name}' is hidden.",
            cell_range=f"{sheet.name}!A1",
            recommendation="Unhide the sheet, or document why it's intentionally hidden.",
        )
        for sheet in structure.sheets
        if sheet.hidden
    ]


def _check_irregular_shape(sheet_info: SheetInfo, columns: list[ColumnInfo]) -> list[Finding]:
    if sheet_info.column_count <= 0 or not columns:
        return []
    used_columns = sum(1 for c in columns if c.inferred_type != ColumnType.EMPTY)
    ratio = used_columns / sheet_info.column_count
    if ratio >= 0.5:
        return []
    letter_range = f"{column_letters(0)}:{column_letters(sheet_info.column_count - 1)}"
    return [
        Finding(
            category=Category.STRUCTURE,
            severity=Severity.LOW,
            description=(
                f"Sheet '{sheet_info.name}' declares {sheet_info.column_count} columns but only "
                f"{used_columns} have data — an irregular table shape."
            ),
            cell_range=f"{sheet_info.name}!{letter_range}",
            recommendation="Trim the sheet's column count to match the actual data.",
        )
    ]


# ---------------------------------------------------------------------------
# Maintainability
# ---------------------------------------------------------------------------

_COMPLEXITY_LENGTH_THRESHOLD = 60
_COMPLEXITY_NESTING_THRESHOLD = 3


def _formula_nesting_depth(formula: str) -> int:
    depth = max_depth = 0
    for ch in formula:
        if ch == "(":
            depth += 1
            max_depth = max(max_depth, depth)
        elif ch == ")":
            depth = max(0, depth - 1)
    return max_depth


def _check_complex_formulas(sheet_name: str, formulas: list[FormulaRef]) -> list[Finding]:
    findings = []
    for ref in formulas:
        nesting = _formula_nesting_depth(ref.formula)
        if len(ref.formula) < _COMPLEXITY_LENGTH_THRESHOLD and nesting < _COMPLEXITY_NESTING_THRESHOLD:
            continue
        findings.append(
            Finding(
                category=Category.MAINTAINABILITY,
                severity=Severity.MEDIUM,
                description=(
                    f"Formula in {sheet_name}!{ref.cell} is long or deeply nested "
                    f"({len(ref.formula)} chars, nesting depth {nesting}), which is hard to audit."
                ),
                cell_range=f"{sheet_name}!{ref.cell}",
                recommendation="Break the formula into helper columns or named ranges.",
            )
        )
    return findings


_GENERIC_HEADER_RE = re.compile(r"^(column|col)\s*\d*$", re.IGNORECASE)


def _check_unclear_headers(sheet_name: str, columns: list[ColumnInfo]) -> list[Finding]:
    findings = []
    for col in columns:
        header = (col.header or "").strip()
        letter = column_letters(col.index)
        if not header:
            severity = Severity.HIGH
            description = f"Column {letter} in sheet '{sheet_name}' has no header."
        elif len(header) <= 2 or _GENERIC_HEADER_RE.match(header):
            severity = Severity.LOW
            description = f"Column {letter} ('{header}') in sheet '{sheet_name}' has an unclear, generic header."
        else:
            continue
        findings.append(
            Finding(
                category=Category.MAINTAINABILITY,
                severity=severity,
                description=description,
                cell_range=f"{sheet_name}!{letter}1",
                recommendation="Give the column a clear, descriptive header.",
            )
        )
    return findings


def _check_hardcoded_in_formula_columns(
    sheet_name: str, data_rows: list[Row], columns: list[ColumnInfo]
) -> list[Finding]:
    findings = []
    for col in columns:
        if col.inferred_type != ColumnType.MIXED:
            continue

        has_formula = False
        literal_rows = []
        for row_index, row in enumerate(data_rows):
            cell = _cell_at(row, col.index)
            if not cell:
                continue
            if cell.get("formula"):
                has_formula = True
            elif cell_is_non_empty(cell):
                literal_rows.append(row_index + 2)

        if has_formula and literal_rows:
            letter = column_letters(col.index)
            findings.append(
                Finding(
                    category=Category.MAINTAINABILITY,
                    severity=Severity.MEDIUM,
                    description=(
                        f"Column {letter} ('{col.header or 'unnamed'}') in sheet '{sheet_name}' mixes "
                        f"formulas with hard-coded values in row(s) {', '.join(map(str, literal_rows))}."
                    ),
                    cell_range=f"{sheet_name}!" + ",".join(f"{letter}{r}" for r in literal_rows),
                    recommendation="Replace the hard-coded values with the column's formula for consistency.",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

_SECURITY_PATTERNS: list[tuple[str, re.Pattern[str], Severity]] = [
    ("email address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), Severity.MEDIUM),
    (
        "phone number",
        re.compile(r"(?<!\d)(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"),
        Severity.MEDIUM,
    ),
    ("Social Security Number", re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"), Severity.HIGH),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), Severity.HIGH),
    (
        "credential or secret",
        re.compile(r"(?i)\b(api[_-]?key|secret|token|password|access[_-]?key)\b\s*[:=]\s*\S+"),
        Severity.HIGH,
    ),
]


def _check_sensitive_patterns(sheet_name: str, rows: list[Row]) -> list[Finding]:
    hits: dict[str, list[str]] = defaultdict(list)
    for row_index, row in enumerate(rows):
        for col_index, cell in enumerate(row):
            text = _cell_text(cell)
            if not text:
                continue
            for label, pattern, _severity in _SECURITY_PATTERNS:
                if pattern.search(text):
                    hits[label].append(cell_ref(row_index, col_index))

    findings = []
    for label, _pattern, severity in _SECURITY_PATTERNS:
        cells = hits.get(label)
        if not cells:
            continue
        findings.append(
            Finding(
                category=Category.SECURITY,
                severity=severity,
                description=(
                    f"Sheet '{sheet_name}' contains what looks like {len(cells)} {label} value(s) "
                    f"in {', '.join(cells)}."
                ),
                cell_range=f"{sheet_name}!" + ",".join(cells),
                recommendation="Remove or redact the sensitive data and restrict sharing on this sheet.",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _score_categories(findings: list[Finding]) -> dict[Category, float]:
    scores = dict.fromkeys(Category, 100.0)
    for finding in findings:
        scores[finding.category] = max(0.0, scores[finding.category] - _SEVERITY_PENALTY[finding.severity])
    return {category: round(score, 2) for category, score in scores.items()}


def compute_health_report(
    structure: SpreadsheetStructure,
    raw: dict[str, Any],
    weights: CategoryWeights | None = None,
) -> HealthReport:
    weights = weights or CategoryWeights()

    rows_by_sheet: dict[str, list[Row]] = {
        sheet.get("title") or "": sheet.get("rows") or [] for sheet in raw.get("sheets", [])
    }
    columns_by_sheet: dict[str, list[ColumnInfo]] = {
        sc.sheet_name: sc.columns for sc in structure.columns_by_sheet
    }

    findings: list[Finding] = []

    for sheet in structure.sheets:
        rows = rows_by_sheet.get(sheet.name, [])
        data_rows = rows[1:] if rows else []
        columns = columns_by_sheet.get(sheet.name, [])
        sheet_formulas = [f for f in structure.formulas if f.sheet_name == sheet.name]

        findings += _check_duplicate_rows(sheet.name, data_rows)
        findings += _check_blank_required_fields(sheet.name, data_rows, columns)
        findings += _check_invalid_formats(sheet.name, data_rows, columns)
        findings += _check_inconsistent_types(sheet.name, columns)

        findings += _check_formula_errors(sheet.name, rows)
        findings += _check_inconsistent_formulas(sheet.name, sheet_formulas)
        findings += _check_suspicious_references(sheet.name, sheet_formulas)

        findings += _check_empty_columns(sheet.name, columns)
        findings += _check_irregular_shape(sheet, columns)

        findings += _check_complex_formulas(sheet.name, sheet_formulas)
        findings += _check_unclear_headers(sheet.name, columns)
        findings += _check_hardcoded_in_formula_columns(sheet.name, data_rows, columns)

        findings += _check_sensitive_patterns(sheet.name, rows)

    findings += _check_merged_cells(structure)
    findings += _check_hidden_sheets(structure)

    findings.sort(key=lambda f: (_SEVERITY_ORDER[f.severity], f.category.value, f.cell_range))

    category_scores = _score_categories(findings)
    normalized_weights = weights.normalized()
    overall_score = round(
        sum(category_scores[category] * normalized_weights[category] for category in Category), 2
    )

    return HealthReport(
        overall_score=overall_score,
        category_scores=CategoryScores(
            data_quality=category_scores[Category.DATA_QUALITY],
            formula_quality=category_scores[Category.FORMULA_QUALITY],
            structure=category_scores[Category.STRUCTURE],
            maintainability=category_scores[Category.MAINTAINABILITY],
            security=category_scores[Category.SECURITY],
        ),
        weights=weights,
        findings=findings,
    )
