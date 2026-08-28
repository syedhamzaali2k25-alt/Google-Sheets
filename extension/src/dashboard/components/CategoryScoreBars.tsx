import type { CategoryScores } from "@shared/types";

const CATEGORY_LABELS: Record<keyof CategoryScores, string> = {
  data_quality: "Data Quality",
  formula_quality: "Formula Quality",
  structure: "Structure",
  maintainability: "Maintainability",
  security: "Security",
};

const CATEGORY_KEYS = Object.keys(CATEGORY_LABELS) as (keyof CategoryScores)[];

function barColor(score: number): string {
  if (score >= 80) return "bg-green-500";
  if (score >= 50) return "bg-amber-500";
  return "bg-red-500";
}

export function CategoryScoreBars({ scores }: { scores: CategoryScores }) {
  return (
    <div className="w-full space-y-3">
      {CATEGORY_KEYS.map((key) => {
        const score = scores[key];
        return (
          <div key={key}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="font-medium text-slate-700">{CATEGORY_LABELS[key]}</span>
              <span className="text-slate-500">{Math.round(score)}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
              <div
                className={`h-full rounded-full ${barColor(score)}`}
                style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
