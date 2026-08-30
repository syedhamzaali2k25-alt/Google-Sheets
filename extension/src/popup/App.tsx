import { useEffect, useState, type ReactNode } from "react";
import constants from "@shared/constants.json";
import type { HealthCheckResponse } from "@shared/types";
import { Logo } from "../lib/Logo";
import { connectGoogleAccount, GoogleAuthError } from "../lib/googleAuth";
import { extractSpreadsheetId } from "../lib/googleSheets";
import { NAVY_HEADER_FROM, NAVY_HEADER_TO, TIER_TINT, type Tier } from "../lib/theme";

type BackendStatus = "checking" | "online" | "offline";
type GoogleConnectionState =
  | { status: "idle" }
  | { status: "connecting" }
  | { status: "connected"; scope?: string }
  | { status: "error"; message: string };
type AnalyzeState = { status: "idle" } | { status: "opening" } | { status: "no-sheet" };

function StatusPill({ tone, children }: { tone: Tier; children: ReactNode }) {
  const tint = TIER_TINT[tone];
  return <p className={`rounded-[4px] px-2 py-1 text-xs font-bold ${tint.bg} ${tint.text}`}>{children}</p>;
}

const PRIMARY_BUTTON_CLASSES =
  "block w-full rounded-[4px] bg-[#0B1120] px-3 py-2 text-sm font-bold text-white transition-colors hover:bg-[#182238] focus-visible:ring-2 focus-visible:ring-[#4F7CFF] focus-visible:ring-offset-1 focus-visible:outline-none disabled:cursor-default disabled:bg-[#C7CCD6] disabled:text-white";

const SECONDARY_BUTTON_CLASSES =
  "block w-full rounded-[4px] border border-[#0B1120] bg-white px-3 py-2 text-sm font-bold text-[#0B1120] transition-colors hover:bg-[#0B1120]/5 focus-visible:ring-2 focus-visible:ring-[#4F7CFF] focus-visible:ring-offset-1 focus-visible:outline-none disabled:cursor-default disabled:border-[#C7CCD6] disabled:text-[#8A93A6]";

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
    <main className="w-[260px] bg-[#F5F6F8]">
      <header
        className="flex items-center gap-2 px-3 py-2.5"
        style={{ background: `linear-gradient(to bottom, ${NAVY_HEADER_FROM}, ${NAVY_HEADER_TO})` }}
      >
        <Logo size={18} />
        <h1 className="text-[13px] font-extrabold tracking-tight text-white">Google Sheet Insights</h1>
      </header>

      <div className="space-y-3 p-4">
        <div>
          <p className="text-xs text-[#5B6478]">Analyze the health, docs, and history of a Google Sheet.</p>
          <div className="mt-2">
            <StatusPill tone={backendTone}>Backend: {backendStatus}</StatusPill>
          </div>
        </div>

        <div>
          <button
            type="button"
            onClick={handleAnalyzeClick}
            disabled={analyzeState.status === "opening"}
            className={PRIMARY_BUTTON_CLASSES}
          >
            {analyzeState.status === "opening" ? "Opening…" : "Analyze Sheet"}
          </button>
          {analyzeState.status === "no-sheet" && (
            <div className="mt-2">
              <StatusPill tone="critical">Open a Google Sheet in this tab first, then try again.</StatusPill>
            </div>
          )}
        </div>

        <div>
          <button
            type="button"
            onClick={handleConnectClick}
            disabled={connection.status === "connecting" || connection.status === "connected"}
            className={SECONDARY_BUTTON_CLASSES}
          >
            {connection.status === "connected" ? "Google account connected" : "Connect Google Account"}
          </button>

          {connection.status === "connecting" && (
            <div className="mt-2">
              <StatusPill tone="fair">Connecting…</StatusPill>
            </div>
          )}
          {connection.status === "connected" && (
            <div className="mt-2">
              <StatusPill tone="good">Verified with backend.</StatusPill>
            </div>
          )}
          {connection.status === "error" && (
            <div className="mt-2">
              <StatusPill tone="critical">{connection.message}</StatusPill>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

export default App;
