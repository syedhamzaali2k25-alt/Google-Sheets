import { useState } from "react";
import { exportReport } from "../api";
import { FOCUS_RING_CLASSES } from "../../lib/theme";

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

function DownloadIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true" className="shrink-0">
      <path
        d="M8 2v7.5M8 9.5 5 6.5M8 9.5l3-3M3 12.5h10"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
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
    <div className="flex flex-col items-end gap-1.5">
      <button
        type="button"
        onClick={handleClick}
        disabled={state.status === "exporting"}
        className={`flex shrink-0 items-center gap-2 rounded-control border border-white/15 bg-white/[0.06] px-3.5 py-2 text-xs font-bold tracking-wide text-white uppercase shadow-card transition-colors hover:border-white/25 hover:bg-white/[0.12] active:bg-white/[0.16] disabled:cursor-default disabled:text-white/40 ${FOCUS_RING_CLASSES}`}
      >
        {state.status === "exporting" ? (
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
        ) : (
          <DownloadIcon />
        )}
        {state.status === "exporting" ? "Preparing PDF…" : "Share Report"}
      </button>
      {state.status === "error" && (
        <p className="max-w-xs text-right text-xs text-critical-on-navy">{state.message}</p>
      )}
    </div>
  );
}
