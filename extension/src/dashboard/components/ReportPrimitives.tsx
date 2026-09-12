import type { ReactNode } from "react";
import { CARD_CLASSES } from "../../lib/theme";

/** Small bold uppercase eyebrow label preceding a report section, e.g.
 * "OVERALL HEALTH" or "FINDINGS". */
export function SectionLabel({ children }: { children: ReactNode }) {
  return <h2 className="mb-3 text-eyebrow font-extrabold tracking-[0.14em] text-muted uppercase">{children}</h2>;
}

/** The base white card surface used by every section in the dashboard:
 * consistent radius, border, and resting elevation (see CARD_CLASSES in
 * lib/theme.ts). Pass `interactive` for a card that should lift slightly
 * on hover (e.g. one that wraps a clickable action). */
export function Card({
  children,
  className = "",
  interactive = false,
}: {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
}) {
  return (
    <div
      className={`${CARD_CLASSES} ${interactive ? "transition-shadow hover:shadow-card-hover" : ""} ${className}`}
    >
      {children}
    </div>
  );
}
