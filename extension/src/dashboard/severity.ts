import type { FindingCategory, Severity } from "@shared/types";

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

/** Score-based tier (distinct from a finding's own severity) used for the
 * health gauge and the per-category status pills. */
export type Tier = "critical" | "fair" | "good";

export function scoreTier(score: number): Tier {
  if (score >= 80) return "good";
  if (score >= 50) return "fair";
  return "critical";
}

export const TIER_HEX: Record<Tier, string> = {
  critical: "#C0281C",
  fair: "#C79015",
  good: "#0F7A3D",
};

export const TIER_COLORS: Record<
  Tier,
  { text: string; tagBg: string; barBg: string; label: string; verdict: string; subtext: string }
> = {
  critical: {
    text: "text-[#C0281C]",
    tagBg: "bg-[#C0281C]",
    barBg: "bg-[#C0281C]",
    label: "CRITICAL",
    verdict: "Needs Attention",
    subtext: "Multiple high-severity issues should be reviewed before relying on this sheet.",
  },
  fair: {
    text: "text-[#9A6300]",
    tagBg: "bg-[#C79015]",
    barBg: "bg-[#C79015]",
    label: "FAIR",
    verdict: "Could Be Improved",
    subtext: "Some issues were found that are worth cleaning up.",
  },
  good: {
    text: "text-[#0F7A3D]",
    tagBg: "bg-[#0F7A3D]",
    barBg: "bg-[#0F7A3D]",
    label: "GOOD",
    verdict: "Healthy",
    subtext: "This sheet meets most data quality and structure best practices.",
  },
};
