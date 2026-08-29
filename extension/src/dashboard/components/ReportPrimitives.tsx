import type { ReactNode } from "react";

/** Small bold uppercase eyebrow label preceding a report section, e.g.
 * "OVERALL HEALTH" or "FINDINGS". */
export function SectionLabel({ children }: { children: ReactNode }) {
  return <h2 className="mb-3 text-[11px] font-extrabold tracking-[0.14em] text-[#8A93A6] uppercase">{children}</h2>;
}

/** Flat white report card: thin border, sharp corners, no heavy shadow —
 * the base surface for every section in the diagnostic-report layout. */
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-[4px] border border-[#E7E9EE] bg-white ${className}`}>{children}</div>;
}
