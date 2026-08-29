import constants from "@shared/constants.json";
import type { ChangeHistoryReport, HealthReport, SpreadsheetDocumentation } from "@shared/types";

export class ApiError extends Error {}

function resolvePath(template: string, spreadsheetId: string): string {
  return template.replace("{spreadsheetId}", encodeURIComponent(spreadsheetId));
}

async function parseJsonOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail ?? `Request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

async function postForToken<T>(pathTemplate: string, accessToken: string, spreadsheetId: string): Promise<T> {
  const response = await fetch(`${constants.backendBaseUrl}${resolvePath(pathTemplate, spreadsheetId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access_token: accessToken }),
  });
  return parseJsonOrThrow<T>(response);
}

export function fetchHealth(accessToken: string, spreadsheetId: string): Promise<HealthReport> {
  return postForToken<HealthReport>(constants.sheetsHealthPathTemplate, accessToken, spreadsheetId);
}

export function fetchDocumentation(accessToken: string, spreadsheetId: string): Promise<SpreadsheetDocumentation> {
  return postForToken<SpreadsheetDocumentation>(
    constants.sheetsDocumentationPathTemplate,
    accessToken,
    spreadsheetId,
  );
}

export async function fetchChanges(
  accessToken: string,
  spreadsheetId: string,
  days: number,
): Promise<ChangeHistoryReport> {
  const path = resolvePath(constants.sheetsChangesPathTemplate, spreadsheetId);
  const response = await fetch(`${constants.backendBaseUrl}${path}?days=${days}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  return parseJsonOrThrow<ChangeHistoryReport>(response);
}

export async function exportReport(accessToken: string, spreadsheetId: string, days: number): Promise<Blob> {
  const path = resolvePath(constants.sheetsExportPathTemplate, spreadsheetId);
  const response = await fetch(`${constants.backendBaseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access_token: accessToken, days }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail ?? `Request failed (${response.status}).`);
  }
  return response.blob();
}
