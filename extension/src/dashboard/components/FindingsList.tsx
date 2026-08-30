import { useState } from "react";
import type { Finding } from "@shared/types";
import { clearHighlights, highlightDuplicates } from "../api";
import { CATEGORY_ACCENT, CATEGORY_LABELS, SEVERITY_ORDER, SEVERITY_TAG } from "../severity";
import { Card, SectionLabel } from "./ReportPrimitives";

type HighlightState =
  | { status: "idle" }
  | { status: "confirm" }
  | { status: "applying" }
  | { status: "applied"; rangesHighlighted: number; cellsAffected: number }
  | { status: "removing" }
  | { status: "error"; message: string };

function describeError(reason: unknown, fallback: string): string {
  if (reason instanceof Error && reason.message) return reason.message;
  return fallback;
}

function findingKey(finding: Finding, index: number): string {
  return `${finding.cell_range}-${index}`;
}

function HighlightAction({
  finding,
  state,
  onRequestConfirm,
  onCancel,
  onConfirm,
  onRemove,
  spreadsheetId,
}: {
  finding: Finding;
  state: HighlightState;
  onRequestConfirm: () => void;
  onCancel: () => void;
  onConfirm: () => void;
  onRemove: () => void;
  spreadsheetId: string;
}) {
  const sheetUrl = `https://docs.google.com/spreadsheets/d/${encodeURIComponent(spreadsheetId)}/edit`;

  if (state.status === "confirm") {
    return (
      <div className="mt-3 rounded-[4px] border border-[#E7E9EE] bg-[#F5F6F8] p-3">
        <p className="text-xs text-[#2B3245]">
          This will tint the following range(s) in your Google Sheet:{" "}
          <span className="font-mono break-all text-[#5B6478]">{finding.cell_range}</span>. Only the
          background color of those cells changes — no values or formulas are touched.
        </p>
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-[3px] bg-[#C0281C] px-2.5 py-1 text-xs font-bold text-white hover:bg-[#A52116]"
          >
            Confirm
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-[3px] border border-[#E7E9EE] bg-white px-2.5 py-1 text-xs font-bold text-[#5B6478] hover:bg-[#F5F6F8]"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  if (state.status === "applying" || state.status === "removing") {
    return (
      <div className="mt-3 flex items-center gap-2 text-xs font-bold text-[#5B6478]">
        <span className="h-3 w-3 animate-spin rounded-full border-2 border-[#E7E9EE] border-t-[#5B6478]" />
        {state.status === "applying" ? "Highlighting…" : "Removing highlight…"}
      </div>
    );
  }

  if (state.status === "applied") {
    return (
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <span className="rounded-[3px] bg-[#E4F5EA] px-2 py-1 text-xs font-bold text-[#0F7A3D]">
          Highlighted {state.rangesHighlighted} range{state.rangesHighlighted === 1 ? "" : "s"}
        </span>
        <a
          href={sheetUrl}
          target="_blank"
          rel="noreferrer"
          className="text-xs font-bold text-[#4F7CFF] hover:underline"
        >
          View in Sheet
        </a>
        <button
          type="button"
          onClick={onRemove}
          className="rounded-[3px] border border-[#E7E9EE] bg-white px-2.5 py-1 text-xs font-bold text-[#5B6478] hover:bg-[#F5F6F8]"
        >
          Remove highlight
        </button>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="mt-3 space-y-1.5">
        <p className="rounded-[4px] border border-[#F3C6C0] bg-[#FDE9E7] px-2.5 py-1.5 text-xs text-[#C0281C]">
          {state.message}
        </p>
        <button
          type="button"
          onClick={onRequestConfirm}
          className="rounded-[3px] border border-[#E7E9EE] bg-white px-2.5 py-1 text-xs font-bold text-[#5B6478] hover:bg-[#F5F6F8]"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onRequestConfirm}
      className="mt-3 rounded-[3px] border border-[#C0281C] bg-white px-2.5 py-1 text-xs font-bold text-[#C0281C] hover:bg-[#FDE9E7]"
    >
      Highlight in Sheet
    </button>
  );
}

export function FindingsList({
  findings,
  accessToken,
  spreadsheetId,
}: {
  findings: Finding[];
  accessToken: string;
  spreadsheetId: string;
}) {
  const [highlightStates, setHighlightStates] = useState<Record<string, HighlightState>>({});

  const counts = SEVERITY_ORDER.map((severity) => ({
    severity,
    count: findings.filter((finding) => finding.severity === severity).length,
  })).filter((entry) => entry.count > 0);

  function setState(key: string, state: HighlightState) {
    setHighlightStates((prev) => ({ ...prev, [key]: state }));
  }

  async function handleConfirm(key: string) {
    setState(key, { status: "applying" });
    try {
      const result = await highlightDuplicates(accessToken, spreadsheetId);
      if (result.success) {
        setState(key, {
          status: "applied",
          rangesHighlighted: result.ranges_highlighted,
          cellsAffected: result.cells_affected,
        });
      } else {
        setState(key, { status: "error", message: result.error ?? "Could not highlight the sheet." });
      }
    } catch (err) {
      setState(key, { status: "error", message: describeError(err, "Could not highlight the sheet.") });
    }
  }

  async function handleRemove(key: string) {
    setState(key, { status: "removing" });
    try {
      const result = await clearHighlights(accessToken, spreadsheetId);
      if (result.success) {
        setState(key, { status: "idle" });
      } else {
        setState(key, { status: "error", message: result.error ?? "Could not remove the highlight." });
      }
    } catch (err) {
      setState(key, { status: "error", message: describeError(err, "Could not remove the highlight.") });
    }
  }

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <SectionLabel>Findings</SectionLabel>
        {counts.length > 0 && (
          <div className="flex items-center gap-1.5">
            {counts.map(({ severity, count }) => (
              <span
                key={severity}
                className={`rounded-[3px] px-2 py-0.5 text-[10px] font-extrabold tracking-wide text-white ${SEVERITY_TAG[severity].bg}`}
              >
                {SEVERITY_TAG[severity].label} · {count}
              </span>
            ))}
          </div>
        )}
      </div>

      <Card className="p-5">
        {findings.length === 0 ? (
          <p className="text-sm text-[#8A93A6]">No issues found — this sheet looks healthy.</p>
        ) : (
          <div className="divide-y divide-[#E7E9EE]">
            {findings.map((finding, index) => {
              const key = findingKey(finding, index);
              const state = highlightStates[key] ?? { status: "idle" };
              return (
                <div key={key} className="flex gap-4 py-4 first:pt-0 last:pb-0">
                  <span className="w-8 shrink-0 font-mono text-xl leading-none font-bold text-[#D7DBE3] tabular-nums">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs font-extrabold tracking-wide uppercase ${CATEGORY_ACCENT[finding.category]}`}
                        >
                          {CATEGORY_LABELS[finding.category]}
                        </span>
                        <span
                          className={`rounded-[3px] px-1.5 py-0.5 text-[10px] font-extrabold tracking-wide text-white ${SEVERITY_TAG[finding.severity].bg}`}
                        >
                          {SEVERITY_TAG[finding.severity].label}
                        </span>
                      </div>
                      <span className="max-w-[45%] break-all font-mono text-xs text-[#8A93A6]">
                        {finding.cell_range}
                      </span>
                    </div>
                    <p className="text-sm break-words text-[#2B3245]">{finding.description}</p>
                    <p className="mt-1 text-xs break-words text-[#8A93A6]">
                      <span className="font-bold text-[#5B6478]">Recommended: </span>
                      {finding.recommendation}
                    </p>

                    {finding.highlightable && (
                      <HighlightAction
                        finding={finding}
                        state={state}
                        spreadsheetId={spreadsheetId}
                        onRequestConfirm={() => setState(key, { status: "confirm" })}
                        onCancel={() => setState(key, { status: "idle" })}
                        onConfirm={() => handleConfirm(key)}
                        onRemove={() => handleRemove(key)}
                      />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </section>
  );
}
