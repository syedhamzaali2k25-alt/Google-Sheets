import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "../lib/ErrorBoundary";
import { TIER_TINT } from "../lib/theme";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary
      fallback={(error) => (
        <main className="w-72 bg-page p-4">
          <h1 className="text-sm font-extrabold text-ink">Google Sheet Insights</h1>
          <p
            className={`mt-2 rounded-tag border px-2 py-1 text-xs font-bold ${TIER_TINT.critical.bg} ${TIER_TINT.critical.text} ${TIER_TINT.critical.border}`}
          >
            Something went wrong: {error.message}
          </p>
        </main>
      )}
    >
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
