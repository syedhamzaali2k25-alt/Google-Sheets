import type { FindingCategory, Severity } from "@shared/types";
import { scoreTier, TIER_COLORS, TIER_HEX, type Tier } from "../lib/theme";

export { scoreTier, TIER_COLORS, TIER_HEX, type Tier };

export const SEVERITY_ORDER: Severity[] = ["high", "medium", "low"];

export const SEVERITY_LABEL: Record<Severity, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

/** Solid-colored severity tag used throughout the report (findings,
 * unusual-activity flags) — red/amber/gray, drawn from the shared tier
 * palette in lib/theme.ts / styles/tokens.css. */
export const SEVERITY_TAG: Record<Severity, { bg: string; label: string }> = {
  high: { bg: "bg-critical-500", label: "HIGH" },
  medium: { bg: "bg-fair-500", label: "MEDIUM" },
  low: { bg: "bg-low-500", label: "LOW" },
};

export const CATEGORY_LABELS: Record<FindingCategory, string> = {
  data_quality: "Data Quality",
  formula_quality: "Formula Quality",
  structure: "Structure",
  maintainability: "Maintainability",
  security: "Security",
};

/** Distinct accent color per finding category, kept separate from the
 * severity colors above so a category label is never mistaken for a
 * severity indicator. */
export const CATEGORY_ACCENT: Record<FindingCategory, string> = {
  data_quality: "text-category-data",
  formula_quality: "text-category-formula",
  structure: "text-category-structure",
  maintainability: "text-category-maintainability",
  security: "text-category-security",
};
