import type { CategoryScores } from "@shared/types";
import { CATEGORY_LABELS, scoreTier, TIER_COLORS } from "../severity";

const CATEGORY_KEYS = Object.keys(CATEGORY_LABELS) as (keyof CategoryScores)[];

export function CategoryScoreBars({ scores }: { scores: CategoryScores }) {
  return (
    <div className="w-full divide-y divide-border">
      {CATEGORY_KEYS.map((key) => {
        const clamped = Math.max(0, Math.min(100, scores[key]));
        const colors = TIER_COLORS[scoreTier(clamped)];
        return (
          <div key={key} className="py-3.5 first:pt-0 last:pb-0">
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="text-sm font-bold text-ink">{CATEGORY_LABELS[key]}</span>
              <div className="flex shrink-0 items-center gap-2">
                <span className="text-sm">
                  <span className="font-extrabold text-ink">{Math.round(clamped)}</span>
                  <span className="text-muted">/100</span>
                </span>
                <span className={`rounded-tag px-1.5 py-0.5 text-[10px] font-extrabold tracking-wide text-white ${colors.tagBg}`}>
                  {colors.label}
                </span>
              </div>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-track">
              <div
                className={`h-full rounded-full transition-[width] ${colors.barBg}`}
                style={{ width: `${clamped}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
