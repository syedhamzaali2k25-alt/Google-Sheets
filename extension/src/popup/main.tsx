import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "../lib/ErrorBoundary";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary
      fallback={(error) => (
        <main className="popup">
          <h1>Google Sheet Insights</h1>
          <p className="status status--offline">Something went wrong: {error.message}</p>
        </main>
      )}
    >
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
