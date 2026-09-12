import { useEffect, useState, type ReactNode } from "react";
import constants from "@shared/constants.json";
import type { HealthCheckResponse } from "@shared/types";
import { Logo } from "../lib/Logo";
import { connectGoogleAccount, GoogleAuthError } from "../lib/googleAuth";
import { extractSpreadsheetId } from "../lib/googleSheets";
import { FOCUS_RING_CLASSES, NAVY_HEADER_FROM, NAVY_HEADER_TO, TIER_TINT, type Tier } from "../lib/theme";

type BackendStatus = "checking" | "online" | "offline";
type GoogleConnectionState =
  | { status: "idle" }
  | { status: "connecting" }
  | { status: "connected"; scope?: string }
  | { status: "error"; message: string };
type AnalyzeState = { status: "idle" } | { status: "opening" } | { status: "no-sheet" };

function StatusPill({ tone, children }: { tone: Tier; children: ReactNode }) {
  const tint = TIER_TINT[tone];
  return (
    <p className={`flex items-center gap-1.5 rounded-tag border px-2 py-1 text-xs font-bold ${tint.bg} ${tint.text} ${tint.border}`}>
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current" aria-hidden="true" />
      {children}
    </p>
  );
}

function AccountIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 20 20" fill="none" aria-hidden="true" className="shrink-0">
      <circle cx="10" cy="6.5" r="3.25" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3.5 17c1.2-3.4 4-5 6.5-5s5.3 1.6 6.5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 20 20"
      fill="none"
      aria-hidden="true"
      className="shrink-0 transition-transform group-hover:translate-x-0.5"
    >
      <path d="M4 10h11.5M10.5 4.5 16 10l-5.5 5.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const PRIMARY_BUTTON_CLASSES =
  `group flex w-full items-center justify-center gap-2 rounded-control bg-navy-950 px-3 py-2.5 text-sm font-bold text-white shadow-card transition-colors hover:bg-navy-800 active:bg-navy-900 disabled:cursor-default disabled:bg-border-strong disabled:text-white disabled:shadow-none ${FOCUS_RING_CLASSES}`;

const SECONDARY_BUTTON_CLASSES =
  `flex w-full items-center justify-center gap-2 rounded-control border border-navy-950/15 bg-white px-3 py-2.5 text-sm font-bold text-navy-950 transition-colors hover:border-navy-950/30 hover:bg-page active:bg-border disabled:cursor-default disabled:border-border disabled:text-muted ${FOCUS_RING_CLASSES}`;

function App() {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [connection, setConnection] = useState<GoogleConnectionState>({ status: "idle" });
  const [analyzeState, setAnalyzeState] = useState<AnalyzeState>({ status: "idle" });

  useEffect(() => {
    const controller = new AbortController();

    fetch(`${constants.backendBaseUrl}${constants.healthCheckPath}`, {
      signal: controller.signal,
    })
      .then((res) => res.json() as Promise<HealthCheckResponse>)
      .then((data) => setBackendStatus(data.status === "ok" ? "online" : "offline"))
      .catch(() => setBackendStatus("offline"));

    return () => controller.abort();
  }, []);

  async function handleAnalyzeClick() {
    setAnalyzeState({ status: "opening" });
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const spreadsheetId = extractSpreadsheetId(tab?.url);

    if (!spreadsheetId) {
      setAnalyzeState({ status: "no-sheet" });
      return;
    }

    const dashboardUrl = chrome.runtime.getURL(
      `src/dashboard/index.html?spreadsheetId=${encodeURIComponent(spreadsheetId)}`,
    );
    await chrome.tabs.create({ url: dashboardUrl });
    window.close();
  }

  async function handleConnectClick() {
    setConnection({ status: "connecting" });
    try {
      const result = await connectGoogleAccount();
      setConnection({ status: "connected", scope: result.scope });
    } catch (err) {
      const message =
        err instanceof GoogleAuthError || err instanceof Error
          ? err.message
          : "Failed to connect Google account.";
      setConnection({ status: "error", message });
    }
  }

  const backendTone: Tier = backendStatus === "online" ? "good" : backendStatus === "checking" ? "fair" : "critical";

  return (
    <main className="w-72 bg-page">
      <header
        className="flex items-center gap-2.5 px-4 py-3 shadow-header"
        style={{ background: `linear-gradient(135deg, ${NAVY_HEADER_FROM}, ${NAVY_HEADER_TO})` }}
      >
        <Logo size={20} />
        <div className="min-w-0">
          <p className="truncate text-[13px] leading-tight font-extrabold tracking-tight text-white">
            Google Sheet Insights
          </p>
          <p className="text-[10px] leading-tight font-semibold tracking-wide text-navy-muted uppercase">
            Spreadsheet audit
          </p>
        </div>
      </header>

      <div className="space-y-4 p-4">
        <div className="space-y-2">
          <p className="text-xs leading-relaxed text-subtle">
            Analyze the health, docs, and history of a Google Sheet.
          </p>
          <StatusPill tone={backendTone}>Backend: {backendStatus}</StatusPill>
        </div>

        <div className="h-px bg-border" />

        <div className="space-y-2.5">
          <button type="button" onClick={handleAnalyzeClick} disabled={analyzeState.status === "opening"} className={PRIMARY_BUTTON_CLASSES}>
            {analyzeState.status === "opening" ? (
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            ) : (
              <ArrowIcon />
            )}
            {analyzeState.status === "opening" ? "Opening…" : "Analyze Sheet"}
          </button>
          {analyzeState.status === "no-sheet" && (
            <StatusPill tone="critical">Open a Google Sheet in this tab first, then try again.</StatusPill>
          )}

          <button
            type="button"
            onClick={handleConnectClick}
            disabled={connection.status === "connecting" || connection.status === "connected"}
            className={SECONDARY_BUTTON_CLASSES}
          >
            {connection.status === "connecting" ? (
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-navy-950/20 border-t-navy-950" />
            ) : (
              <AccountIcon />
            )}
            {connection.status === "connected" ? "Google account connected" : "Connect Google Account"}
          </button>

          {connection.status === "connecting" && <StatusPill tone="fair">Connecting…</StatusPill>}
          {connection.status === "connected" && <StatusPill tone="good">Verified with backend.</StatusPill>}
          {connection.status === "error" && <StatusPill tone="critical">{connection.message}</StatusPill>}
        </div>
      </div>
    </main>
  );
}

export default App;
