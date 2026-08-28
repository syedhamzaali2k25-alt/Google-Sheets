/**
 * Types shared between the extension and the backend.
 * The backend's Pydantic models (backend/app/main.py) should mirror these shapes.
 */

export interface HealthCheckResponse {
  status: "ok";
  service: "google-sheet-insights-backend";
}

export interface AccessTokenRequest {
  access_token: string;
}

export interface AuthVerifyResponse {
  valid: true;
  scope?: string;
  expiresIn?: number;
  audience?: string;
}

export interface SheetCell {
  value: string | number | boolean | { error: string } | null;
  formattedValue: string | null;
  formula: string | null;
  numberFormatType: string | null;
}

export interface SheetRange {
  sheetId: number | null;
  startRowIndex: number;
  endRowIndex: number | null;
  startColumnIndex: number;
  endColumnIndex: number | null;
}

export interface SheetRaw {
  sheetId: number;
  title: string;
  hidden: boolean;
  rowCount: number | null;
  columnCount: number | null;
  rows: (SheetCell | null)[][];
  merges: SheetRange[];
}

export interface NamedRangeRaw extends SheetRange {
  name: string;
}

export interface SpreadsheetRawResponse {
  spreadsheetId: string;
  title: string;
  sheets: SheetRaw[];
  namedRanges: NamedRangeRaw[];
}

// --- Health report (backend/analysis/health_score.py) -----------------

export type Severity = "low" | "medium" | "high";

export type FindingCategory =
  | "data_quality"
  | "formula_quality"
  | "structure"
  | "maintainability"
  | "security";

export interface Finding {
  category: FindingCategory;
  severity: Severity;
  description: string;
  cell_range: string;
  recommendation: string;
}

export interface CategoryScores {
  data_quality: number;
  formula_quality: number;
  structure: number;
  maintainability: number;
  security: number;
}

export interface CategoryWeights {
  data_quality: number;
  formula_quality: number;
  structure: number;
  maintainability: number;
  security: number;
}

export interface HealthReport {
  overall_score: number;
  category_scores: CategoryScores;
  weights: CategoryWeights;
  findings: Finding[];
}

// --- Documentation (backend/analysis/documentation.py) -----------------

export interface SheetDocumentation {
  sheet_name: string;
  summary: string;
}

export interface SheetRelationship {
  column_name: string;
  sheets: string[];
  description: string;
}

export interface SpreadsheetDocumentation {
  title: string;
  sheet_summaries: SheetDocumentation[];
  relationships: SheetRelationship[];
  workbook_summary: string;
  source: "rule_based" | "ai_enhanced";
}

// --- Change history (backend/analysis/change_history.py) ---------------

export type ActivityAction =
  | "create"
  | "edit"
  | "move"
  | "rename"
  | "delete"
  | "restore"
  | "permission_change"
  | "comment"
  | "other";

export interface ActivityEvent {
  timestamp: string;
  actors: string[];
  action: ActivityAction;
}

export interface Contributor {
  identifier: string;
  display_name: string | null;
  edit_count: number;
  total_actions: number;
  last_active_at: string | null;
}

export interface TouchedRange {
  sheet_name: string | null;
  range_a1: string | null;
  edit_count: number;
}

export interface UnusualActivityFlag {
  timestamp: string;
  actor: string | null;
  description: string;
  severity: Severity;
}

export interface ChangeHistoryReport {
  spreadsheet_id: string;
  window_start: string;
  window_end: string;
  data_granularity: "file_level" | "range_level";
  limited_data_warning: string | null;
  total_edits: number;
  contributors: Contributor[];
  touched_ranges: TouchedRange[];
  unusual_activity: UnusualActivityFlag[];
  events: ActivityEvent[];
}
