import { useEffect, useState } from "react";
import constants from "@shared/constants.json";
import type { HealthCheckResponse } from "@shared/types";
import { connectGoogleAccount, GoogleAuthError } from "../lib/googleAuth";
import { extractSpreadsheetId } from "../lib/googleSheets";
import "./App.css";

type BackendStatus = "checking" | "online" | "offline";
type GoogleConnectionState =
  | { status: "idle" }
  | { status: "connecting" }
  | { status: "connected"; scope?: string }
  | { status: "error"; message: string };
type AnalyzeState = { status: "idle" } | { status: "opening" } | { status: "no-sheet" };

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

  return (
    <main className="popup">
      <h1>Google Sheet Insights</h1>
      <p className="tagline">Analyze the health, docs, and history of a Google Sheet.</p>
      <p className={`status status--${backendStatus}`}>Backend: {backendStatus}</p>

      <button type="button" onClick={handleAnalyzeClick} disabled={analyzeState.status === "opening"}>
        {analyzeState.status === "opening" ? "Opening…" : "Analyze Sheet"}
      </button>
      {analyzeState.status === "no-sheet" && (
        <p className="status status--offline">Open a Google Sheet in this tab first, then try again.</p>
      )}

      <button
        type="button"
        className="secondary"
        onClick={handleConnectClick}
        disabled={connection.status === "connecting" || connection.status === "connected"}
      >
        {connection.status === "connected" ? "Google account connected" : "Connect Google Account"}
      </button>

      {connection.status === "connecting" && <p className="status">Connecting…</p>}
      {connection.status === "connected" && (
        <p className="status status--online">Verified with backend.</p>
      )}
      {connection.status === "error" && (
        <p className="status status--offline">{connection.message}</p>
      )}
    </main>
  );
}

export default App;
