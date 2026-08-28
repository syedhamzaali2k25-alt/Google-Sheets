import { useEffect, useState } from "react";
import constants from "@shared/constants.json";
import type { HealthCheckResponse } from "@shared/types";
import { connectGoogleAccount, GoogleAuthError } from "../lib/googleAuth";
import "./App.css";

type BackendStatus = "checking" | "online" | "offline";
type GoogleConnectionState =
  | { status: "idle" }
  | { status: "connecting" }
  | { status: "connected"; scope?: string }
  | { status: "error"; message: string };

function App() {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [connection, setConnection] = useState<GoogleConnectionState>({ status: "idle" });

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
      <p className="tagline">Scaffold popup — no features wired up yet.</p>
      <p className={`status status--${backendStatus}`}>Backend: {backendStatus}</p>

      <button
        type="button"
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
