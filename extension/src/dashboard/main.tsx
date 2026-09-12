import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "../lib/ErrorBoundary";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary
      fallback={(error, reset) => (
        <div className="flex min-h-screen items-center justify-center bg-page px-6">
          <div className="w-full max-w-md rounded-card border border-border bg-surface p-8 text-center shadow-card-hover">
            <h1 className="text-lg font-extrabold text-ink">Something went wrong</h1>
            <p className="mt-2 text-sm text-muted">{error.message}</p>
            <button
              type="button"
              onClick={() => {
                reset();
                window.location.reload();
              }}
              className="mt-4 rounded-control bg-accent-500 px-4 py-2 text-sm font-bold text-white shadow-card transition-colors hover:bg-accent-600 active:bg-accent-700"
            >
              Reload
            </button>
          </div>
        </div>
      )}
    >
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
