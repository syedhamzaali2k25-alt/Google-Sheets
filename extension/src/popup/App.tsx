import { useEffect, useState } from "react";
import constants from "@shared/constants.json";
import type { HealthCheckResponse } from "@shared/types";
import "./App.css";

type BackendStatus = "checking" | "online" | "offline";

function App() {
  const [status, setStatus] = useState<BackendStatus>("checking");

  useEffect(() => {
    const controller = new AbortController();

    fetch(`${constants.backendBaseUrl}${constants.healthCheckPath}`, {
      signal: controller.signal,
    })
      .then((res) => res.json() as Promise<HealthCheckResponse>)
      .then((data) => setStatus(data.status === "ok" ? "online" : "offline"))
      .catch(() => setStatus("offline"));

    return () => controller.abort();
  }, []);

  return (
    <main className="popup">
      <h1>Google Sheet Insights</h1>
      <p className="tagline">Scaffold popup — no features wired up yet.</p>
      <p className={`status status--${status}`}>Backend: {status}</p>
    </main>
  );
}

export default App;
