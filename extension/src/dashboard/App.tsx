import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { ChangeHistoryReport, HealthReport, SpreadsheetDocumentation } from "@shared/types";
import { getGoogleAccessToken, GoogleAuthError } from "../lib/googleAuth";
import { fetchChanges, fetchDocumentation, fetchHealth } from "./api";
import { CategoryScoreBars } from "./components/CategoryScoreBars";
import { ChangeAnalyticsPanel } from "./components/ChangeAnalyticsPanel";
import { DocumentationPanel } from "./components/DocumentationPanel";
import { FindingsList } from "./components/FindingsList";
import { HealthGauge } from "./components/HealthGauge";
import { ShareReportButton } from "./components/ShareReportButton";
import { ErrorBanner, LoadingSpinner } from "./components/StatusViews";
import { Tabs, type TabKey } from "./components/Tabs";

type PanelState<T> = { status: "success"; data: T } | { status: "error"; error: string };

const CHANGE_WINDOW_DAYS = 30;

function describeError(reason: unknown, fallback: string): string {
  if (reason instanceof Error && reason.message) return reason.message;
  return fallback;
}

function CenteredCard({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 text-center shadow-sm">
        {children}
      </div>
    </div>
  );
}

function App() {
  const spreadsheetId = useMemo(() => new URLSearchParams(window.location.search).get("spreadsheetId"), []);

  const [stage, setStage] = useState<"loading" | "auth-error" | "ready">("loading");
  const [authError, setAuthError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("dashboard");
  const [retryCount, setRetryCount] = useState(0);

  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [health, setHealth] = useState<PanelState<HealthReport> | null>(null);
  const [documentation, setDocumentation] = useState<PanelState<SpreadsheetDocumentation> | null>(null);
  const [changes, setChanges] = useState<PanelState<ChangeHistoryReport> | null>(null);

  useEffect(() => {
    if (!spreadsheetId) return;
    let cancelled = false;
    setStage("loading");
    setAuthError(null);

    (async () => {
      let token: string;
      try {
        token = await getGoogleAccessToken(true);
      } catch (err) {
        if (cancelled) return;
        setAuthError(
          err instanceof GoogleAuthError || err instanceof Error ? err.message : "Could not sign in with Google.",
        );
        setStage("auth-error");
        return;
      }
      if (cancelled) return;
      setAccessToken(token);

      const [healthResult, docResult, changesResult] = await Promise.allSettled([
        fetchHealth(token, spreadsheetId),
        fetchDocumentation(token, spreadsheetId),
        fetchChanges(token, spreadsheetId, CHANGE_WINDOW_DAYS),
      ]);
      if (cancelled) return;

      setHealth(
        healthResult.status === "fulfilled"
          ? { status: "success", data: healthResult.value }
          : { status: "error", error: describeError(healthResult.reason, "Could not compute the health score.") },
      );
      setDocumentation(
        docResult.status === "fulfilled"
          ? { status: "success", data: docResult.value }
          : { status: "error", error: describeError(docResult.reason, "Could not generate documentation.") },
      );
      setChanges(
        changesResult.status === "fulfilled"
          ? { status: "success", data: changesResult.value }
          : { status: "error", error: describeError(changesResult.reason, "Could not fetch change history.") },
      );
      setStage("ready");
    })();

    return () => {
      cancelled = true;
    };
  }, [spreadsheetId, retryCount]);

  if (!spreadsheetId) {
    return (
      <CenteredCard>
        <h1 className="text-lg font-semibold text-slate-800">No spreadsheet selected</h1>
        <p className="mt-2 text-sm text-slate-500">
          Open a Google Sheet in a tab, then click "Analyze Sheet" from the extension popup to open it here.
        </p>
      </CenteredCard>
    );
  }

  if (stage === "auth-error") {
    return (
      <CenteredCard>
        <h1 className="text-lg font-semibold text-slate-800">Couldn't connect to Google</h1>
        <p className="mt-2 text-sm text-slate-500">{authError}</p>
        <button
          type="button"
          onClick={() => setRetryCount((n) => n + 1)}
          className="mt-4 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Try again
        </button>
      </CenteredCard>
    );
  }

  if (stage === "loading") {
    return (
      <CenteredCard>
        <LoadingSpinner label="Analyzing your spreadsheet…" />
      </CenteredCard>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Google Sheet Insights</h1>
          <p className="font-mono text-sm text-slate-500">{spreadsheetId}</p>
        </div>
        {accessToken && (
          <ShareReportButton accessToken={accessToken} spreadsheetId={spreadsheetId} days={CHANGE_WINDOW_DAYS} />
        )}
      </header>

      <Tabs active={activeTab} onChange={setActiveTab} />

      <main className="mt-6">
        {activeTab === "dashboard" &&
          (health?.status === "success" ? (
            <div className="space-y-6">
              <div className="flex flex-col items-center gap-6 rounded-lg border border-slate-200 bg-white p-6 sm:flex-row sm:items-start sm:justify-between">
                <HealthGauge score={health.data.overall_score} />
                <CategoryScoreBars scores={health.data.category_scores} />
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <h2 className="mb-3 text-sm font-semibold text-slate-800">Findings</h2>
                <FindingsList findings={health.data.findings} />
              </div>
            </div>
          ) : (
            <ErrorBanner message={health?.error ?? "Could not compute the health score."} />
          ))}

        {activeTab === "documentation" &&
          (documentation?.status === "success" ? (
            <DocumentationPanel documentation={documentation.data} />
          ) : (
            <ErrorBanner message={documentation?.error ?? "Could not generate documentation."} />
          ))}

        {activeTab === "changes" &&
          (changes?.status === "success" ? (
            <ChangeAnalyticsPanel changes={changes.data} />
          ) : (
            <ErrorBanner message={changes?.error ?? "Could not fetch change history."} />
          ))}
      </main>
    </div>
  );
}

export default App;
