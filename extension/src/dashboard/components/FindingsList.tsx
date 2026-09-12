import { useState } from "react";
import type { Finding } from "@shared/types";
import { FOCUS_RING_CLASSES } from "../../lib/theme";
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
      <div className="mt-3 rounded-control border border-border bg-page p-3 shadow-popover">
        <p className="text-xs leading-relaxed text-body">
          This will tint the following range(s) in your Google Sheet:{" "}
          <span className="font-mono break-all text-subtle">{finding.cell_range}</span>. Only the background
          color of those cells changes — no values or formulas are touched.
        </p>
        <div className="mt-2.5 flex gap-2">
          <button
            type="button"
            onClick={onConfirm}
            className={`rounded-control bg-critical-500 px-3 py-1.5 text-xs font-bold text-white transition-colors hover:bg-critical-600 active:bg-critical-600 ${FOCUS_RING_CLASSES}`}
          >
            Confirm
          </button>
          <button
            type="button"
            onClick={onCancel}
            className={`rounded-control border border-border bg-surface px-3 py-1.5 text-xs font-bold text-subtle transition-colors hover:bg-page ${FOCUS_RING_CLASSES}`}
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  if (state.status === "applying" || state.status === "removing") {
    return (
      <div className="mt-3 flex items-center gap-2 text-xs font-bold text-subtle">
        <span className="h-3 w-3 animate-spin rounded-full border-2 border-border border-t-subtle" />
        {state.status === "applying" ? "Highlighting…" : "Removing highlight…"}
      </div>
    );
  }

  if (state.status === "applied") {
    return (
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <span className="rounded-tag bg-good-tint px-2 py-1 text-xs font-bold text-good-500">
          Highlighted {state.rangesHighlighted} range{state.rangesHighlighted === 1 ? "" : "s"}
        </span>
        <a
          href={sheetUrl}
          target="_blank"
          rel="noreferrer"
          className={`rounded-control text-xs font-bold text-accent-500 transition-colors hover:text-accent-600 hover:underline ${FOCUS_RING_CLASSES}`}
        >
          View in Sheet
        </a>
        <button
          type="button"
          onClick={onRemove}
          className={`rounded-control border border-border bg-surface px-3 py-1.5 text-xs font-bold text-subtle transition-colors hover:bg-page ${FOCUS_RING_CLASSES}`}
        >
          Remove highlight
        </button>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="mt-3 space-y-1.5">
        <p className="rounded-control border border-critical-tint-border bg-critical-tint px-3 py-1.5 text-xs text-critical-500">
          {state.message}
        </p>
        <button
          type="button"
          onClick={onRequestConfirm}
          className={`rounded-control border border-border bg-surface px-3 py-1.5 text-xs font-bold text-subtle transition-colors hover:bg-page ${FOCUS_RING_CLASSES}`}
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
      className={`mt-3 rounded-control border border-critical-500/30 bg-critical-tint/40 px-3 py-1.5 text-xs font-bold text-critical-500 transition-colors hover:border-critical-500 hover:bg-critical-tint ${FOCUS_RING_CLASSES}`}
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
                className={`rounded-tag px-2 py-0.5 text-[10px] font-extrabold tracking-wide text-white ${SEVERITY_TAG[severity].bg}`}
              >
                {SEVERITY_TAG[severity].label} · {count}
              </span>
            ))}
          </div>
        )}
      </div>

      <Card className="p-5">
        {findings.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-good-tint text-good-500">
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M4 10.5 8 14.5 16 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <p className="text-sm font-bold text-ink">No issues found</p>
            <p className="text-xs text-muted">This sheet looks healthy.</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {findings.map((finding, index) => {
              const key = findingKey(finding, index);
              const state = highlightStates[key] ?? { status: "idle" };
              return (
                <div
                  key={key}
                  className="-mx-5 flex gap-4 rounded-control px-5 py-4 transition-colors first:pt-0 last:pb-0 hover:bg-page"
                >
                  <span className="w-8 shrink-0 font-mono text-xl leading-none font-bold text-border-strong tabular-nums">
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
                          className={`rounded-tag px-1.5 py-0.5 text-[10px] font-extrabold tracking-wide text-white ${SEVERITY_TAG[finding.severity].bg}`}
                        >
                          {SEVERITY_TAG[finding.severity].label}
                        </span>
                      </div>
                      <span className="max-w-[45%] break-all font-mono text-xs text-muted">
                        {finding.cell_range}
                      </span>
                    </div>
                    <p className="text-sm break-words text-body">{finding.description}</p>
                    <p className="mt-1 text-xs break-words text-muted">
                      <span className="font-bold text-subtle">Recommended: </span>
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
