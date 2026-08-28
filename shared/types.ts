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
}

export interface SheetRaw {
  sheetId: number;
  title: string;
  rowCount: number | null;
  columnCount: number | null;
  rows: (SheetCell | null)[][];
}

export interface SpreadsheetRawResponse {
  spreadsheetId: string;
  title: string;
  sheets: SheetRaw[];
}
