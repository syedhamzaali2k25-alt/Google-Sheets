"""Generates human-readable documentation for a spreadsheet from its
SpreadsheetStructure (Step 2), using rule-based templates — no AI call yet
in generate_documentation().

build_documentation() layers an optional AI polishing pass on top: if
ANTHROPIC_API_KEY is set, the rule-based draft is sent to Claude to be
rewritten into more natural prose. It falls back to the rule-based draft
whenever the key is unset or the API call fails for any reason.
"""

import logging
import os
import re
from collections import defaultdict
from typing import Literal

import anthropic
from pydantic import BaseModel

from analysis.structure import ColumnInfo, ColumnType, FormulaRef, SheetInfo, SpreadsheetStructure

logger = logging.getLogger(__name__)


class SheetDocumentation(BaseModel):
    sheet_name: str
    summary: str


class SheetRelationship(BaseModel):
    column_name: str
    sheets: list[str]
    description: str


class SpreadsheetDocumentation(BaseModel):
    title: str
    sheet_summaries: list[SheetDocumentation]
    relationships: list[SheetRelationship]
    workbook_summary: str
    source: Literal["rule_based", "ai_enhanced"]


# ---------------------------------------------------------------------------
# Rule-based generation
# ---------------------------------------------------------------------------

_CELL_REF_RE = re.compile(r"\$?([A-Za-z]{1,3})\$?(\d+)")
_SIMPLE_BINARY_RE = re.compile(r"^=\s*(\$?[A-Za-z]{1,3}\$?\d+)\s*([*+/-])\s*(\$?[A-Za-z]{1,3}\$?\d+)\s*$")
_OPERATOR_WORDS = {"*": "×", "/": "÷", "+": "+", "-": "−"}


def _column_index_from_letters(letters: str) -> int:
    index = 0
    for ch in letters.upper():
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return index - 1


def _join_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _header_for_ref(ref: str, columns_by_index: dict[int, str]) -> str:
    match = _CELL_REF_RE.match(ref)
    if not match:
        return ref
    return columns_by_index.get(_column_index_from_letters(match.group(1)), ref)


def _describe_formula(formula: str, columns_by_index: dict[int, str]) -> tuple[str, bool] | None:
    """Returns (description, is_simple_binary) for a formula, or None if it
    references no recognizable columns."""
    simple = _SIMPLE_BINARY_RE.match(formula)
    if simple:
        left, op, right = simple.groups()
        left_name = _header_for_ref(left, columns_by_index)
        right_name = _header_for_ref(right, columns_by_index)
        return f"{left_name} {_OPERATOR_WORDS.get(op, op)} {right_name}", True

    names: list[str] = []
    for col_letters, _row in _CELL_REF_RE.findall(formula):
        name = columns_by_index.get(_column_index_from_letters(col_letters))
        if name and name not in names:
            names.append(name)
    return (_join_list(names), False) if names else None


def _column_index_of_cell(cell_ref: str) -> int:
    match = re.match(r"[A-Za-z]+", cell_ref)
    return _column_index_from_letters(match.group()) if match else -1


def _describe_sheet(sheet: SheetInfo, columns: list[ColumnInfo], sheet_formulas: list[FormulaRef]) -> str:
    sentences: list[str] = []

    named_columns = [c.header for c in columns if c.header and c.inferred_type != ColumnType.EMPTY]
    if named_columns:
        sentences.append(f"The '{sheet.name}' sheet appears to track records with {_join_list(named_columns)}.")
    else:
        sentences.append(f"The '{sheet.name}' sheet contains tabular data with no clearly labeled columns.")

    sentences.append(
        f"It spans {sheet.row_count} row{'s' if sheet.row_count != 1 else ''} and "
        f"{sheet.column_count} column{'s' if sheet.column_count != 1 else ''}"
        f"{', and is hidden' if sheet.hidden else ''}."
    )

    key_columns = named_columns[:5]
    if key_columns:
        sentences.append(f"Key columns include {_join_list(key_columns)}.")

    columns_by_index = {c.index: c.header for c in columns if c.header}
    for col in columns:
        if col.inferred_type != ColumnType.FORMULA:
            continue
        col_formulas = [f for f in sheet_formulas if _column_index_of_cell(f.cell) == col.index]
        if not col_formulas:
            continue

        label = col.header or "This column"
        described = _describe_formula(col_formulas[0].formula, columns_by_index)
        if described is None:
            sentences.append(f"{label} is calculated with a formula.")
        else:
            description, is_simple_binary = described
            if is_simple_binary:
                sentences.append(f"{label} is calculated from {description}.")
            else:
                sentences.append(f"{label} is calculated using a formula involving {description}.")

    return " ".join(sentences)


def _detect_relationships(structure: SpreadsheetStructure) -> list[SheetRelationship]:
    sheets_by_header: dict[str, set[str]] = defaultdict(set)
    display_name_by_header: dict[str, str] = {}

    for sheet_columns in structure.columns_by_sheet:
        for col in sheet_columns.columns:
            header = (col.header or "").strip()
            if not header:
                continue
            key = header.lower()
            sheets_by_header[key].add(sheet_columns.sheet_name)
            display_name_by_header.setdefault(key, header)

    relationships = [
        SheetRelationship(
            column_name=display_name_by_header[key],
            sheets=sorted(sheets),
            description=(
                f"'{display_name_by_header[key]}' appears in {_join_list(sorted(sheets))}, "
                f"suggesting these sheets can be linked on that column."
            ),
        )
        for key, sheets in sheets_by_header.items()
        if len(sheets) >= 2
    ]
    return sorted(relationships, key=lambda r: r.column_name.lower())


def _summarize_workbook(structure: SpreadsheetStructure, relationships: list[SheetRelationship]) -> str:
    sheet_names = [s.name for s in structure.sheets]
    title_part = f"This workbook ('{structure.title}')" if structure.title else "This workbook"

    if not sheet_names:
        return f"{title_part} has no sheets."

    if len(sheet_names) == 1:
        sentences = [f"{title_part} contains a single sheet, '{sheet_names[0]}'."]
    else:
        sentences = [f"{title_part} contains {len(sheet_names)} sheets: {_join_list(sheet_names)}."]

    if relationships:
        linking_columns = _join_list([r.column_name for r in relationships])
        sentences.append(f"The sheets appear linked via {linking_columns}.")

    sentences.append(
        f"In total it holds {structure.stats.total_rows} rows, uses "
        f"{len(structure.formulas)} formula(s), and is about "
        f"{round(structure.stats.percent_empty_cells)}% empty."
    )
    return " ".join(sentences)


def generate_documentation(structure: SpreadsheetStructure) -> SpreadsheetDocumentation:
    """Pure, deterministic, rule-based documentation — no network calls."""
    columns_by_sheet = {sc.sheet_name: sc.columns for sc in structure.columns_by_sheet}

    sheet_summaries = [
        SheetDocumentation(
            sheet_name=sheet.name,
            summary=_describe_sheet(
                sheet,
                columns_by_sheet.get(sheet.name, []),
                [f for f in structure.formulas if f.sheet_name == sheet.name],
            ),
        )
        for sheet in structure.sheets
    ]

    relationships = _detect_relationships(structure)

    return SpreadsheetDocumentation(
        title=structure.title,
        sheet_summaries=sheet_summaries,
        relationships=relationships,
        workbook_summary=_summarize_workbook(structure, relationships),
        source="rule_based",
    )


# ---------------------------------------------------------------------------
# Optional AI enhancement
# ---------------------------------------------------------------------------

_AI_MODEL = "claude-opus-5"
_AI_MAX_TOKENS = 8192

_AI_SYSTEM_PROMPT = (
    "You are a technical writer documenting a Google Sheets workbook. You will be given a "
    "rule-based draft of that documentation plus the normalized spreadsheet structure it was "
    "generated from. Rewrite the draft into clearer, more natural prose while preserving every "
    "fact it states — row counts, column names, formula relationships, cross-sheet links. Do "
    "not invent facts that aren't supported by the structure data, and do not drop any sheet or "
    "relationship the draft covers. Keep the same shape: one summary per sheet, the list of "
    "cross-sheet relationships, and one workbook-level summary."
)


def enhance_documentation_with_ai(
    draft: SpreadsheetDocumentation, structure: SpreadsheetStructure
) -> SpreadsheetDocumentation:
    """Asks Claude to polish the rule-based draft into more natural prose.

    Returns the draft unchanged if ANTHROPIC_API_KEY isn't set, or if the API
    call fails for any reason — AI enhancement is a best-effort layer on top
    of the always-available rule-based documentation, never a hard
    dependency of the /documentation endpoint.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return draft

    try:
        client = anthropic.Anthropic()
        response = client.messages.parse(
            model=_AI_MODEL,
            max_tokens=_AI_MAX_TOKENS,
            system=_AI_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Rule-based draft:\n{draft.model_dump_json(indent=2)}\n\n"
                        f"Underlying spreadsheet structure:\n{structure.model_dump_json(indent=2)}"
                    ),
                }
            ],
            output_format=SpreadsheetDocumentation,
        )
        polished = response.parsed_output
    except anthropic.AuthenticationError:
        logger.warning("AI documentation enhancement skipped: invalid Anthropic API key.")
        return draft
    except anthropic.PermissionDeniedError:
        logger.warning("AI documentation enhancement skipped: API key lacks permission.")
        return draft
    except anthropic.RateLimitError:
        logger.warning("AI documentation enhancement skipped: rate limited.")
        return draft
    except anthropic.APIStatusError as exc:
        logger.warning("AI documentation enhancement skipped: API error (%s).", exc.status_code)
        return draft
    except anthropic.APIConnectionError:
        logger.warning("AI documentation enhancement skipped: could not reach the Anthropic API.")
        return draft
    except Exception:
        logger.exception("AI documentation enhancement skipped: unexpected error.")
        return draft

    polished.source = "ai_enhanced"
    return polished


def build_documentation(structure: SpreadsheetStructure) -> SpreadsheetDocumentation:
    """Rule-based draft, optionally polished by Claude — see module docstring."""
    draft = generate_documentation(structure)
    return enhance_documentation_with_ai(draft, structure)
