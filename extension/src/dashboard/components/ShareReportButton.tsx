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
        className="flex shrink-0 items-center gap-2 rounded-[4px] border border-white/20 bg-white/5 px-3 py-1.5 text-xs font-bold tracking-wide text-white uppercase hover:bg-white/10 disabled:cursor-default disabled:text-white/40"
      >
        {state.status === "exporting" && (
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
        )}
        {state.status === "exporting" ? "Preparing PDF…" : "Share Report"}
      </button>
      {state.status === "error" && <p className="max-w-xs text-right text-xs text-[#FF9B8A]">{state.message}</p>}
    </div>
  );
}
