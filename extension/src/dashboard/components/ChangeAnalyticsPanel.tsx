import type { ChangeHistoryReport } from "@shared/types";
import { SEVERITY_BADGE } from "../severity";
import { ActivityBarChart } from "./ActivityBarChart";

const TOP_CONTRIBUTORS_LIMIT = 8;

export function ChangeAnalyticsPanel({ changes }: { changes: ChangeHistoryReport }) {
  const topContributors = changes.contributors.slice(0, TOP_CONTRIBUTORS_LIMIT);

  return (
    <div className="space-y-6">
      {changes.limited_data_warning && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <span className="font-medium">Limited data: </span>
          {changes.limited_data_warning}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-xs tracking-wide text-slate-400 uppercase">Total edits</p>
          <p className="text-2xl font-semibold text-slate-800">{changes.total_edits}</p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-xs tracking-wide text-slate-400 uppercase">Contributors</p>
          <p className="text-2xl font-semibold text-slate-800">{changes.contributors.length}</p>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-800">Activity over time</h3>
        <ActivityBarChart events={changes.events} />
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-800">Top contributors</h3>
        {topContributors.length === 0 ? (
          <p className="text-sm text-slate-500">No contributor activity in this window.</p>
        ) : (
          <ul className="space-y-2">
            {topContributors.map((contributor) => (
              <li key={contributor.identifier} className="flex items-center justify-between text-sm">
                <span className="text-slate-700">{contributor.display_name ?? contributor.identifier}</span>
                <span className="font-medium text-slate-800">
                  {contributor.edit_count} edit{contributor.edit_count === 1 ? "" : "s"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {changes.unusual_activity.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-800">Unusual activity</h3>
          <ul className="space-y-2">
            {changes.unusual_activity.map((flag, index) => (
              <li key={index} className="flex items-start gap-2 text-sm">
                <span className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-xs ${SEVERITY_BADGE[flag.severity]}`}>
                  {flag.severity}
                </span>
                <span className="text-slate-600">{flag.description}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
