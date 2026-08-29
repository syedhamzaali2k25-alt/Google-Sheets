import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "../lib/ErrorBoundary";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary
      fallback={(error, reset) => (
        <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
          <div className="w-full max-w-md rounded-lg border border-red-200 bg-white p-8 text-center shadow-sm">
            <h1 className="text-lg font-semibold text-slate-800">Something went wrong</h1>
            <p className="mt-2 text-sm text-slate-500">{error.message}</p>
            <button
              type="button"
              onClick={() => {
                reset();
                window.location.reload();
              }}
              className="mt-4 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
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
