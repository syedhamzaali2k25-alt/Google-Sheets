/**
 * Design system reference for Google Sheet Insights.
 *
 * The source of truth for Tailwind utility classes is
 * `src/styles/tokens.css` (a Tailwind v4 `@theme` block) — that's what
 * makes `bg-navy-950`, `rounded-card`, `shadow-card`, `text-eyebrow` etc.
 * available as real classes everywhere. This file mirrors the same values
 * as plain JS/TS for the handful of places that can't consume a CSS custom
 * property directly: inline SVG `fill`/`stroke` attributes (HealthGauge),
 * and the one `style={{ background: ... }}` gradient (the navy header,
 * which needs a computed two-stop gradient string, not a single color).
 *
 * Keep the two in sync by hand — there's no build step that generates one
 * from the other, so a color/radius/shadow change belongs in both files.
 *
 * Color meaning is load-bearing elsewhere in the product: red = critical,
 * amber = fair, green = good. Never repurpose those hues for anything else.
 */

// --- Brand: navy + accent --------------------------------------------------

export const NAVY_950 = "#0B1120";
export const NAVY_900 = "#131B2E";
export const NAVY_800 = "#1E2A42";

/** Back-compat aliases used by the header's gradient (App.tsx / popup). */
export const NAVY_HEADER_FROM = NAVY_950;
export const NAVY_HEADER_TO = NAVY_900;

export const ACCENT_500 = "#4F7CFF";
export const ACCENT_600 = "#3D68EE";
export const ACCENT_700 = "#345BD1";

export const ACCENT_BLUE = ACCENT_500;
export const ACCENT_BLUE_HOVER = ACCENT_600;

// --- Neutrals, for the SVG contexts (HealthGauge) that can't use a
// Tailwind text-* class. Mirrors --color-ink / --color-muted in
// tokens.css. ----------------------------------------------------------

export const INK = "#1A2233";
export const MUTED = "#8A93A6";

// --- Spacing & motion reference (Tailwind's own scale already matches the
// requested 4/8/12/16/24/32/48 progression at steps 1/2/3/4/6/8/12 — this
// object exists for the rare non-Tailwind consumer, e.g. computing an SVG
// layout in HealthGauge, that wants the same scale named explicitly). ------

export const SPACE = { xs: 4, sm: 8, md: 12, base: 16, lg: 24, xl: 32, xxl: 48 } as const;

/** Matches --default-transition-duration in tokens.css. Every hover/focus/
 * tab-switch/panel-expand transition in the product uses this duration —
 * `prefers-reduced-motion: reduce` collapses it globally (see tokens.css). */
export const TRANSITION_MS = 160;

// --- Score-based tier (as opposed to a finding's own severity) — used for
// the health gauge, per-category status pills, and any other red/amber/
// green status indicator, e.g. the popup's backend/connection pill. --------

export type Tier = "critical" | "fair" | "good";

export function scoreTier(score: number): Tier {
  if (score >= 80) return "good";
  if (score >= 50) return "fair";
  return "critical";
}

/** Raw hex per tier — for SVG fill/stroke attributes, which can't consume
 * a Tailwind class. Mirrors --color-{critical,fair,good}-500 in tokens.css. */
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
    text: "text-critical-500",
    tagBg: "bg-critical-500",
    barBg: "bg-critical-500",
    label: "CRITICAL",
    verdict: "Needs Attention",
    subtext: "Multiple high-severity issues should be reviewed before relying on this sheet.",
  },
  fair: {
    text: "text-fair-text",
    tagBg: "bg-fair-500",
    barBg: "bg-fair-500",
    label: "FAIR",
    verdict: "Could Be Improved",
    subtext: "Some issues were found that are worth cleaning up.",
  },
  good: {
    text: "text-good-500",
    tagBg: "bg-good-500",
    barBg: "bg-good-500",
    label: "GOOD",
    verdict: "Healthy",
    subtext: "This sheet meets most data quality and structure best practices.",
  },
};

/** Light background tint per tier, for pill-style status indicators (e.g.
 * the popup's backend-status pill) where a solid fill would be too heavy. */
export const TIER_TINT: Record<Tier, { bg: string; text: string; border: string }> = {
  critical: { bg: "bg-critical-tint", text: "text-critical-500", border: "border-critical-tint-border" },
  fair: { bg: "bg-fair-tint", text: "text-fair-text", border: "border-fair-tint-border" },
  good: { bg: "bg-good-tint", text: "text-good-500", border: "border-good-tint-border" },
};

// --- Shared surface/interaction classNames ---------------------------------
// One definition per pattern, reused everywhere, so "what a card looks
// like" or "what a hover state does" is never redecided per component.

/** The resting elevation + radius + border for every white card/panel. */
export const CARD_CLASSES = "rounded-card border border-border bg-surface shadow-card";

/** Applied to a card that itself responds to hover (e.g. wraps a button) —
 * lifts slightly rather than just tinting. Picks up the shared 160ms
 * timing from --default-transition-duration in tokens.css, so no
 * duration-* utility is needed alongside transition-shadow. */
export const CARD_HOVER_CLASSES = "transition-shadow hover:shadow-card-hover";

/** Focus ring used on every interactive element for keyboard accessibility. */
export const FOCUS_RING_CLASSES =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-1";
