import { useState } from "react";
import { exportReport } from "../api";

type ExportState = { status: "idle" } | { status: "exporting" } | { status: "error"; message: string };

function describeError(reason: unknown, fallback: string): string {
  if (reason instanceof Error && reason.message) return reason.message;
  return fallback;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function ShareReportButton({
  accessToken,
  spreadsheetId,
  days,
}: {
  accessToken: string;
  spreadsheetId: string;
  days: number;
}) {
  const [state, setState] = useState<ExportState>({ status: "idle" });

  async function handleClick() {
    setState({ status: "exporting" });
    try {
      const blob = await exportReport(accessToken, spreadsheetId, days);
      downloadBlob(blob, `${spreadsheetId}-insights-report.pdf`);
      setState({ status: "idle" });
    } catch (err) {
      setState({ status: "error", message: describeError(err, "Could not generate the report.") });
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={handleClick}
        disabled={state.status === "exporting"}
        className="flex shrink-0 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-default disabled:text-slate-400"
      >
        {state.status === "exporting" ? "Preparing PDF…" : "Share Report"}
      </button>
      {state.status === "error" && <p className="max-w-xs text-right text-xs text-red-600">{state.message}</p>}
    </div>
  );
}
