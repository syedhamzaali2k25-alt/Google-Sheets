const SPREADSHEET_ID_RE = /\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/;

/** Extracts the spreadsheet id from a Google Sheets URL, or null if it's not one. */
export function extractSpreadsheetId(url: string | undefined | null): string | null {
  if (!url) return null;
  return url.match(SPREADSHEET_ID_RE)?.[1] ?? null;
}
