/** Shared visual tokens for the diagnostic-report look — the dark navy
 * header, the accent blue, and the red/amber/green tier system — so the
 * popup and the dashboard draw from one source instead of duplicating hex
 * values across surfaces. */

export const NAVY_HEADER_FROM = "#0B1120";
export const NAVY_HEADER_TO = "#131B2E";

export const ACCENT_BLUE = "#4F7CFF";
export const ACCENT_BLUE_HOVER = "#3D68EE";

/** Score-based tier (as opposed to a finding's own severity) used for the
 * health gauge, per-category status pills, and any other red/amber/green
 * status indicator — e.g. the popup's backend/connection status pill. */
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

/** Light background tint per tier, for pill-style status indicators (e.g.
 * the popup's backend-status pill) where a solid fill would be too heavy. */
export const TIER_TINT: Record<Tier, { bg: string; text: string }> = {
  critical: { bg: "bg-[#FDE9E7]", text: "text-[#C0281C]" },
  fair: { bg: "bg-[#FDF2DC]", text: "text-[#9A6300]" },
  good: { bg: "bg-[#E4F5EA]", text: "text-[#0F7A3D]" },
};
