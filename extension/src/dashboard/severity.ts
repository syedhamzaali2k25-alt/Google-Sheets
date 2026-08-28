import type { Severity } from "@shared/types";

export const SEVERITY_ORDER: Severity[] = ["high", "medium", "low"];

export const SEVERITY_BADGE: Record<Severity, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-slate-100 text-slate-600",
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};
