import type { ChangeHistoryReport } from "@shared/types";
import { SEVERITY_TAG } from "../severity";
import { ActivityBarChart } from "./ActivityBarChart";
import { Card, SectionLabel } from "./ReportPrimitives";

const TOP_CONTRIBUTORS_LIMIT = 8;

export function ChangeAnalyticsPanel({ changes }: { changes: ChangeHistoryReport }) {
  const topContributors = changes.contributors.slice(0, TOP_CONTRIBUTORS_LIMIT);

  return (
    <div className="space-y-8">
      {changes.limited_data_warning && (
        <div className="rounded-[4px] border border-[#F3D9A6] bg-[#FDF2DC] px-4 py-3 text-sm text-[#9A6300]">
          <span className="font-bold">Limited data: </span>
          {changes.limited_data_warning}
        </div>
      )}

      <section>
        <SectionLabel>Summary</SectionLabel>
        <Card className="flex divide-x divide-[#E7E9EE]">
          <div className="flex-1 p-5">
            <p className="text-[11px] font-bold tracking-wide text-[#8A93A6] uppercase">Total Edits</p>
            <p className="mt-1 font-mono text-3xl font-extrabold text-[#1A2233]">{changes.total_edits}</p>
          </div>
          <div className="flex-1 p-5">
            <p className="text-[11px] font-bold tracking-wide text-[#8A93A6] uppercase">Contributors</p>
            <p className="mt-1 font-mono text-3xl font-extrabold text-[#1A2233]">{changes.contributors.length}</p>
          </div>
        </Card>
      </section>

      <section>
        <SectionLabel>Activity Over Time</SectionLabel>
        <Card className="p-5">
          <ActivityBarChart events={changes.events} />
        </Card>
      </section>

      <section>
        <SectionLabel>Top Contributors</SectionLabel>
        <Card className="p-5">
          {topContributors.length === 0 ? (
            <p className="text-sm text-[#8A93A6]">No contributor activity in this window.</p>
          ) : (
            <div className="divide-y divide-[#E7E9EE]">
              {topContributors.map((contributor) => (
                <div key={contributor.identifier} className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0">
                  <span className="font-mono text-sm text-[#2B3245]">
                    {contributor.display_name ?? contributor.identifier}
                  </span>
                  <span className="font-mono text-sm font-bold text-[#1A2233]">
                    {contributor.edit_count} edit{contributor.edit_count === 1 ? "" : "s"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </section>

      {changes.unusual_activity.length > 0 && (
        <section>
          <SectionLabel>Unusual Activity</SectionLabel>
          <Card className="p-5">
            <div className="divide-y divide-[#E7E9EE]">
              {changes.unusual_activity.map((flag, index) => (
                <div key={index} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
                  <span
                    className={`mt-0.5 shrink-0 rounded-[3px] px-1.5 py-0.5 text-[10px] font-extrabold tracking-wide text-white uppercase ${SEVERITY_TAG[flag.severity].bg}`}
                  >
                    {SEVERITY_TAG[flag.severity].label}
                  </span>
                  <span className="text-sm text-[#2B3245]">{flag.description}</span>
                </div>
              ))}
            </div>
          </Card>
        </section>
      )}
    </div>
  );
}
