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
 * unusual-activity flags) — red/amber/gray. */
export const SEVERITY_TAG: Record<Severity, { bg: string; label: string }> = {
  high: { bg: "bg-[#C0281C]", label: "HIGH" },
  medium: { bg: "bg-[#C79015]", label: "MEDIUM" },
  low: { bg: "bg-[#8A93A6]", label: "LOW" },
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
  data_quality: "text-[#3B6FE0]",
  formula_quality: "text-[#7C4FD1]",
  structure: "text-[#0E8C86]",
  maintainability: "text-[#B5651D]",
  security: "text-[#B2334D]",
};
