"""Combines the health report, documentation, and change history into a
single PDF, built with ReportLab (pure Python — no native system libraries
to install, unlike HTML-to-PDF renderers such as WeasyPrint, which need
Pango/Cairo/GDK-Pixbuf present on the machine).
"""

from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from analysis.change_history import ChangeHistoryReport
from analysis.documentation import SpreadsheetDocumentation
from analysis.health_score import HealthReport

_CATEGORY_LABELS = {
    "data_quality": "Data Quality",
    "formula_quality": "Formula Quality",
    "structure": "Structure",
    "maintainability": "Maintainability",
    "security": "Security",
}

_HEADER_BG = colors.HexColor("#1e293b")
_BORDER = colors.HexColor("#cbd5e1")
_MUTED_TEXT = colors.HexColor("#64748b")
_ROW_ALT_BG = colors.HexColor("#f8fafc")


def _tier_hex(score: float) -> str:
    if score >= 80:
        return "#16a34a"
    if score >= 50:
        return "#d97706"
    return "#dc2626"


def _tier_label(score: float) -> str:
    if score >= 80:
        return "Healthy"
    if score >= 50:
        return "Needs attention"
    return "At risk"


def _stylesheet():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", fontSize=24, leading=30, alignment=TA_CENTER, spaceAfter=10))
    styles.add(
        ParagraphStyle(
            name="CoverSubtitle", fontSize=13, leading=18, alignment=TA_CENTER, textColor=_MUTED_TEXT
        )
    )
    styles.add(ParagraphStyle(name="ScoreNumber", fontSize=54, leading=60, alignment=TA_CENTER, spaceBefore=20))
    styles.add(ParagraphStyle(name="ScoreTier", fontSize=14, alignment=TA_CENTER, spaceAfter=6))
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            fontSize=17,
            leading=21,
            spaceBefore=4,
            spaceAfter=10,
            textColor=colors.HexColor("#0f172a"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SheetHeading", fontSize=12, leading=16, spaceBefore=10, spaceAfter=3, textColor=_HEADER_BG
        )
    )
    styles.add(ParagraphStyle(name="Body", fontSize=10, leading=14))
    styles.add(ParagraphStyle(name="Small", fontSize=8.5, leading=12, alignment=TA_CENTER, textColor=_MUTED_TEXT))
    styles.add(ParagraphStyle(name="TableCell", fontSize=8.5, leading=11))
    return styles


def _table_style(header_bg=_HEADER_BG, zebra=True) -> TableStyle:
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if zebra:
        commands.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ROW_ALT_BG]))
    return TableStyle(commands)


def _build_cover(spreadsheet_id: str, health: HealthReport, documentation: SpreadsheetDocumentation, styles):
    generated_at = datetime.now(timezone.utc).strftime("%B %d, %Y")
    score = health.overall_score
    hex_color = _tier_hex(score)

    return [
        Spacer(1, 1.3 * inch),
        Paragraph("Google Sheet Insights Report", styles["CoverTitle"]),
        Paragraph(documentation.title or "Untitled workbook", styles["CoverSubtitle"]),
        Spacer(1, 0.5 * inch),
        Paragraph(
            f"<font color='{hex_color}'>{score:.0f}</font>"
            f"<font size=16 color='#94a3b8'> / 100</font>",
            styles["ScoreNumber"],
        ),
        Paragraph(
            _tier_label(score),
            ParagraphStyle(name="ScoreTierColored", parent=styles["ScoreTier"], textColor=colors.HexColor(hex_color)),
        ),
        Spacer(1, 0.7 * inch),
        Paragraph(f"Spreadsheet ID: {spreadsheet_id}", styles["Small"]),
        Paragraph(f"Generated {generated_at}", styles["Small"]),
    ]


def _build_findings_section(health: HealthReport, styles):
    elements = [Paragraph("Health & Findings", styles["SectionHeading"])]

    category_rows = [["Category", "Score"]]
    for key, label in _CATEGORY_LABELS.items():
        score = getattr(health.category_scores, key)
        category_rows.append([label, f"{score:.0f} / 100"])
    category_table = Table(category_rows, colWidths=[3.5 * inch, 1.5 * inch], hAlign="LEFT")
    category_table.setStyle(_table_style())
    elements.append(category_table)
    elements.append(Spacer(1, 14))

    if not health.findings:
        elements.append(Paragraph("No issues found — this sheet looks healthy.", styles["Body"]))
        return elements

    elements.append(Paragraph(f"{len(health.findings)} finding(s), highest severity first:", styles["Body"]))
    elements.append(Spacer(1, 6))

    finding_rows = [["Severity", "Category", "Description", "Cell Range", "Recommendation"]]
    for finding in health.findings:
        finding_rows.append(
            [
                Paragraph(finding.severity.value.upper(), styles["TableCell"]),
                Paragraph(_CATEGORY_LABELS.get(finding.category.value, finding.category.value), styles["TableCell"]),
                Paragraph(finding.description, styles["TableCell"]),
                Paragraph(finding.cell_range, styles["TableCell"]),
                Paragraph(finding.recommendation, styles["TableCell"]),
            ]
        )
    findings_table = Table(
        finding_rows,
        colWidths=[0.55 * inch, 1.15 * inch, 1.7 * inch, 0.85 * inch, 1.75 * inch],
        repeatRows=1,
    )
    findings_table.setStyle(_table_style())
    elements.append(findings_table)
    return elements


def _build_documentation_section(documentation: SpreadsheetDocumentation, styles):
    elements = [Paragraph("Documentation", styles["SectionHeading"])]
    elements.append(Paragraph(documentation.workbook_summary, styles["Body"]))
    elements.append(Spacer(1, 10))

    for sheet in documentation.sheet_summaries:
        elements.append(Paragraph(sheet.sheet_name, styles["SheetHeading"]))
        elements.append(Paragraph(sheet.summary, styles["Body"]))

    if documentation.relationships:
        elements.append(Paragraph("Relationships", styles["SheetHeading"]))
        for relationship in documentation.relationships:
            elements.append(Paragraph(f"• {relationship.description}", styles["Body"]))

    source_note = "AI-enhanced" if documentation.source == "ai_enhanced" else "Rule-based"
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Documentation source: {source_note}", styles["Small"]))
    return elements


def _build_changes_section(changes: ChangeHistoryReport, styles):
    elements = [Paragraph("Change Activity", styles["SectionHeading"])]

    window = (
        f"{changes.window_start.strftime('%b %d, %Y')} – {changes.window_end.strftime('%b %d, %Y')}"
    )
    elements.append(Paragraph(f"Window: {window} · Total edits: {changes.total_edits}", styles["Body"]))
    elements.append(Spacer(1, 8))

    if changes.limited_data_warning:
        elements.append(Paragraph(f"<i>{changes.limited_data_warning}</i>", styles["Small"]))
        elements.append(Spacer(1, 10))

    if changes.contributors:
        contributor_rows = [["Contributor", "Edits", "Other actions", "Last active"]]
        for contributor in changes.contributors:
            last_active = contributor.last_active_at.strftime("%b %d, %Y") if contributor.last_active_at else "—"
            contributor_rows.append(
                [
                    contributor.display_name or contributor.identifier,
                    str(contributor.edit_count),
                    str(contributor.total_actions - contributor.edit_count),
                    last_active,
                ]
            )
        contributor_table = Table(
            contributor_rows, colWidths=[2.2 * inch, 0.9 * inch, 1.2 * inch, 1.5 * inch], hAlign="LEFT"
        )
        contributor_table.setStyle(_table_style())
        elements.append(contributor_table)
        elements.append(Spacer(1, 14))
    else:
        elements.append(Paragraph("No contributor activity in this window.", styles["Body"]))
        elements.append(Spacer(1, 14))

    if changes.unusual_activity:
        elements.append(Paragraph("Unusual Activity", styles["SheetHeading"]))
        for flag in changes.unusual_activity:
            when = flag.timestamp.strftime("%b %d, %Y %H:%M UTC")
            elements.append(
                Paragraph(f"[{flag.severity.upper()}] {when} — {flag.description}", styles["Body"])
            )

    return elements


def generate_pdf_report(
    spreadsheet_id: str,
    health: HealthReport,
    documentation: SpreadsheetDocumentation,
    changes: ChangeHistoryReport,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        title=f"{documentation.title or spreadsheet_id} — Insights Report",
    )
    styles = _stylesheet()

    elements = []
    elements += _build_cover(spreadsheet_id, health, documentation, styles)
    elements.append(PageBreak())
    elements += _build_findings_section(health, styles)
    elements.append(PageBreak())
    elements += _build_documentation_section(documentation, styles)
    elements.append(PageBreak())
    elements += _build_changes_section(changes, styles)

    doc.build(elements)
    return buffer.getvalue()
