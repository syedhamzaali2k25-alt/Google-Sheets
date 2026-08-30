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
        <main className="w-[260px] bg-[#F5F6F8] p-4">
          <h1 className="text-sm font-extrabold text-[#1A2233]">Google Sheet Insights</h1>
          <p className={`mt-2 rounded-[4px] px-2 py-1 text-xs font-bold ${TIER_TINT.critical.bg} ${TIER_TINT.critical.text}`}>
            Something went wrong: {error.message}
          </p>
        </main>
      )}
    >
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
