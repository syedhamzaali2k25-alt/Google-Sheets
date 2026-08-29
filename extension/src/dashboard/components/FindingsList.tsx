import type { Finding } from "@shared/types";
import { CATEGORY_ACCENT, CATEGORY_LABELS, SEVERITY_ORDER, SEVERITY_TAG } from "../severity";
import { Card, SectionLabel } from "./ReportPrimitives";

export function FindingsList({ findings }: { findings: Finding[] }) {
  const counts = SEVERITY_ORDER.map((severity) => ({
    severity,
    count: findings.filter((finding) => finding.severity === severity).length,
  })).filter((entry) => entry.count > 0);

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <SectionLabel>Findings</SectionLabel>
        {counts.length > 0 && (
          <div className="flex items-center gap-1.5">
            {counts.map(({ severity, count }) => (
              <span
                key={severity}
                className={`rounded-[3px] px-2 py-0.5 text-[10px] font-extrabold tracking-wide text-white ${SEVERITY_TAG[severity].bg}`}
              >
                {SEVERITY_TAG[severity].label} · {count}
              </span>
            ))}
          </div>
        )}
      </div>

      <Card className="p-5">
        {findings.length === 0 ? (
          <p className="text-sm text-[#8A93A6]">No issues found — this sheet looks healthy.</p>
        ) : (
          <div className="divide-y divide-[#E7E9EE]">
            {findings.map((finding, index) => (
              <div key={`${finding.cell_range}-${index}`} className="flex gap-4 py-4 first:pt-0 last:pb-0">
                <span className="w-8 shrink-0 font-mono text-xl leading-none font-bold text-[#D7DBE3] tabular-nums">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-extrabold tracking-wide uppercase ${CATEGORY_ACCENT[finding.category]}`}
                      >
                        {CATEGORY_LABELS[finding.category]}
                      </span>
                      <span
                        className={`rounded-[3px] px-1.5 py-0.5 text-[10px] font-extrabold tracking-wide text-white ${SEVERITY_TAG[finding.severity].bg}`}
                      >
                        {SEVERITY_TAG[finding.severity].label}
                      </span>
                    </div>
                    <span className="shrink-0 font-mono text-xs text-[#8A93A6]">{finding.cell_range}</span>
                  </div>
                  <p className="text-sm text-[#2B3245]">{finding.description}</p>
                  <p className="mt-1 text-xs text-[#8A93A6]">
                    <span className="font-bold text-[#5B6478]">Recommended: </span>
                    {finding.recommendation}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </section>
  );
}
