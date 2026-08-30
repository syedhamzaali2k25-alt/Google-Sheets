import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { ChangeHistoryReport, HealthReport, SpreadsheetDocumentation } from "@shared/types";
import { ErrorBoundary } from "../lib/ErrorBoundary";
import { getGoogleAccessToken, GoogleAuthError } from "../lib/googleAuth";
import { fetchChanges, fetchDocumentation, fetchHealth } from "./api";
import { CategoryScoreBars } from "./components/CategoryScoreBars";
import { ChangeAnalyticsPanel } from "./components/ChangeAnalyticsPanel";
import { DashboardSkeleton } from "./components/DashboardSkeleton";
import { DocumentationPanel } from "./components/DocumentationPanel";
import { FindingsList } from "./components/FindingsList";
import { HealthGauge } from "./components/HealthGauge";
import { Card, SectionLabel } from "./components/ReportPrimitives";
import { Logo } from "../lib/Logo";
import { ShareReportButton } from "./components/ShareReportButton";
import { ErrorBanner } from "./components/StatusViews";
import { Tabs, type TabKey } from "./components/Tabs";

type PanelState<T> = { status: "success"; data: T } | { status: "error"; error: string };

const CHANGE_WINDOW_DAYS = 30;

function describeError(reason: unknown, fallback: string): string {
  if (reason instanceof Error && reason.message) return reason.message;
  return fallback;
}

function CenteredCard({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F5F6F8] px-6">
      <div className="w-full max-w-md rounded-[4px] border border-[#E7E9EE] bg-white p-8 text-center shadow-sm">
        <div className="mb-4 flex justify-center">
          <Logo />
        </div>
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

  // Display-only scan timing for the report header/footer — purely
  // presentational bookkeeping around the same calls below, doesn't change
  // what's fetched or how.
  const scanStartedAtRef = useRef<number | null>(null);
  const [scannedAt, setScannedAt] = useState<Date | null>(null);
  const [scanSeconds, setScanSeconds] = useState<number | null>(null);

  useEffect(() => {
    if (!spreadsheetId) return;
    let cancelled = false;
    setStage("loading");
    setAuthError(null);
    scanStartedAtRef.current = performance.now();

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
      setScannedAt(new Date());
      setScanSeconds(
        scanStartedAtRef.current !== null ? (performance.now() - scanStartedAtRef.current) / 1000 : null,
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
        <h1 className="text-lg font-extrabold text-[#1A2233]">No spreadsheet selected</h1>
        <p className="mt-2 text-sm text-[#8A93A6]">
          Open a Google Sheet in a tab, then click "Analyze Sheet" from the extension popup to open it here.
        </p>
      </CenteredCard>
    );
  }

  if (stage === "auth-error") {
    return (
      <CenteredCard>
        <h1 className="text-lg font-extrabold text-[#1A2233]">Couldn't connect to Google</h1>
        <p className="mt-2 text-sm text-[#8A93A6]">{authError}</p>
        <button
          type="button"
          onClick={() => setRetryCount((n) => n + 1)}
          className="mt-4 rounded-[4px] bg-[#4F7CFF] px-4 py-2 text-sm font-bold text-white hover:bg-[#3D68EE]"
        >
          Try again
        </button>
      </CenteredCard>
    );
  }

  if (stage === "loading") {
    return <DashboardSkeleton />;
  }

  const categoryCount = health?.status === "success" ? Object.keys(health.data.category_scores).length : null;
  const findingCount = health?.status === "success" ? health.data.findings.length : null;

  const footerParts = ["Google Sheet Insights"];
  if (scanSeconds !== null) footerParts.push(`Scan completed in ${scanSeconds.toFixed(1)}s`);
  if (findingCount !== null && categoryCount !== null) {
    footerParts.push(`${findingCount} finding${findingCount === 1 ? "" : "s"} across ${categoryCount} categories`);
  }

  return (
    <div className="min-h-screen bg-[#F5F6F8]">
      <header className="bg-gradient-to-b from-[#0B1120] to-[#131B2E] px-6 pt-8">
        <div className="mx-auto max-w-5xl">
          <div className="flex flex-col gap-6 pb-6 sm:flex-row sm:items-end sm:justify-between">
            <div className="flex items-center gap-3">
              <Logo />
              <div>
                <p className="text-[11px] font-extrabold tracking-[0.18em] text-[#6B7C9E] uppercase">
                  Spreadsheet Audit Report
                </p>
                <h1 className="text-[28px] font-extrabold tracking-[-0.02em] text-white sm:text-[34px]">
                  Google Sheet Insights
                </h1>
              </div>
            </div>
            <div className="text-left sm:text-right">
              <p className="text-xs text-[#8A93A6]">
                Scanned <span className="font-bold text-white">{scannedAt ? scannedAt.toLocaleString() : "just now"}</span>
              </p>
              <p className="font-mono text-xs text-[#5B6478]">{spreadsheetId}</p>
            </div>
          </div>

          <div className="flex flex-col items-stretch gap-3 border-t border-white/10 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:py-0">
            <Tabs active={activeTab} onChange={setActiveTab} />
            {accessToken && <ShareReportButton accessToken={accessToken} spreadsheetId={spreadsheetId} days={CHANGE_WINDOW_DAYS} />}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        {activeTab === "dashboard" && (
          <ErrorBoundary key="dashboard">
            {health?.status === "success" ? (
              <div className="space-y-8">
                <section>
                  <SectionLabel>Overall Health</SectionLabel>
                  <Card className="p-6">
                    <div className="flex flex-col gap-8 md:flex-row md:items-center">
                      <div className="flex flex-1 justify-center border-b border-[#E7E9EE] pb-8 md:border-r md:border-b-0 md:pr-8 md:pb-0">
                        <HealthGauge score={health.data.overall_score} />
                      </div>
                      <div className="flex-1 md:pl-8">
                        <CategoryScoreBars scores={health.data.category_scores} />
                      </div>
                    </div>
                  </Card>
                </section>

                <FindingsList findings={health.data.findings} />
              </div>
            ) : (
              <ErrorBanner message={health?.error ?? "Could not compute the health score."} />
            )}
          </ErrorBoundary>
        )}

        {activeTab === "documentation" && (
          <ErrorBoundary key="documentation">
            {documentation?.status === "success" ? (
              <DocumentationPanel documentation={documentation.data} />
            ) : (
              <ErrorBanner message={documentation?.error ?? "Could not generate documentation."} />
            )}
          </ErrorBoundary>
        )}

        {activeTab === "changes" && (
          <ErrorBoundary key="changes">
            {changes?.status === "success" ? (
              <ChangeAnalyticsPanel changes={changes.data} />
            ) : (
              <ErrorBanner message={changes?.error ?? "Could not fetch change history."} />
            )}
          </ErrorBoundary>
        )}
      </main>

      <footer className="border-t border-[#E7E9EE] px-6 py-4">
        <p className="mx-auto max-w-5xl font-mono text-[11px] tracking-wide text-[#8A93A6]">
          {footerParts.join(" · ").toUpperCase()}
        </p>
      </footer>
    </div>
  );
}

export default App;
