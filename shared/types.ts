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
