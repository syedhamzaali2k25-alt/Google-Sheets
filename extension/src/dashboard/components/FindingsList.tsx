import type { Finding, FindingCategory } from "@shared/types";
import { SEVERITY_BADGE, SEVERITY_LABEL, SEVERITY_ORDER } from "../severity";

const CATEGORY_LABELS: Record<FindingCategory, string> = {
  data_quality: "Data Quality",
  formula_quality: "Formula Quality",
  structure: "Structure",
  maintainability: "Maintainability",
  security: "Security",
};

export function FindingsList({ findings }: { findings: Finding[] }) {
  if (findings.length === 0) {
    return <p className="text-sm text-slate-500">No issues found — this sheet looks healthy.</p>;
  }

  const groups = SEVERITY_ORDER.map((severity) => ({
    severity,
    items: findings.filter((finding) => finding.severity === severity),
  })).filter((group) => group.items.length > 0);

  return (
    <div className="max-h-96 space-y-4 overflow-y-auto pr-1">
      {groups.map(({ severity, items }) => (
        <div key={severity}>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700">
            <span className={`rounded-full px-2 py-0.5 text-xs ${SEVERITY_BADGE[severity]}`}>
              {SEVERITY_LABEL[severity]}
            </span>
            {items.length} finding{items.length === 1 ? "" : "s"}
          </h3>
          <ul className="space-y-2">
            {items.map((finding, index) => (
              <li key={`${finding.cell_range}-${index}`} className="rounded-lg border border-slate-200 bg-white p-3">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="text-xs font-medium tracking-wide text-slate-400 uppercase">
                    {CATEGORY_LABELS[finding.category]}
                  </span>
                  <span className="font-mono text-xs text-slate-400">{finding.cell_range}</span>
                </div>
                <p className="text-sm text-slate-800">{finding.description}</p>
                <p className="mt-1 text-sm text-slate-500">
                  <span className="font-medium text-slate-600">Recommended: </span>
                  {finding.recommendation}
                </p>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
