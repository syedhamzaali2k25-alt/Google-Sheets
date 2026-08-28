/**
 * Types shared between the extension and the backend.
 * The backend's Pydantic models (backend/app/main.py) should mirror these shapes.
 */

export interface HealthCheckResponse {
  status: "ok";
  service: "google-sheet-insights-backend";
}
