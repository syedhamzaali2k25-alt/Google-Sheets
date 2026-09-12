import type { ChangeHistoryReport, Contributor } from "@shared/types";
import { SEVERITY_TAG } from "../severity";
import { ActivityBarChart } from "./ActivityBarChart";
import { Card, SectionLabel } from "./ReportPrimitives";

const TOP_CONTRIBUTORS_LIMIT = 8;

function PersonIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <circle cx="10" cy="6.5" r="3.25" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3.5 17c1.2-3.4 4-5 6.5-5s5.3 1.6 6.5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function WarningIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path
        d="M10 3.5 17.5 16h-15L10 3.5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M10 8.5v3.2M10 14v.01" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function ContributorAvatar({ contributor }: { contributor: Contributor }) {
  if (!contributor.display_name) {
    return (
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-track text-subtle">
        <PersonIcon />
      </span>
    );
  }
  return (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-navy-950 text-[11px] font-bold text-white">
      {contributor.display_name.trim().charAt(0).toUpperCase()}
    </span>
  );
}

export function ChangeAnalyticsPanel({ changes }: { changes: ChangeHistoryReport }) {
  const topContributors = changes.contributors.slice(0, TOP_CONTRIBUTORS_LIMIT);

  return (
    <div className="space-y-10">
      {changes.limited_data_warning && (
        <div className="flex items-start gap-2.5 rounded-control border border-fair-tint-border bg-fair-tint px-4 py-3 text-sm text-fair-text">
          <span className="mt-0.5 shrink-0">
            <WarningIcon />
          </span>
          <p>
            <span className="font-bold">Limited data: </span>
            {changes.limited_data_warning}
          </p>
        </div>
      )}

      <section>
        <SectionLabel>Summary</SectionLabel>
        <Card className="flex divide-x divide-border">
          <div className="flex-1 p-5">
            <p className="text-eyebrow font-bold tracking-wide text-muted uppercase">Total Edits</p>
            <p className="mt-1 font-mono text-3xl font-extrabold text-ink">{changes.total_edits}</p>
          </div>
          <div className="flex-1 p-5">
            <p className="text-eyebrow font-bold tracking-wide text-muted uppercase">Contributors</p>
            <p className="mt-1 font-mono text-3xl font-extrabold text-ink">{changes.contributors.length}</p>
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
            <p className="text-sm text-muted">No contributor activity in this window.</p>
          ) : (
            <div className="divide-y divide-border">
              {topContributors.map((contributor) => (
                <div
                  key={contributor.identifier}
                  className="-mx-5 flex items-center justify-between gap-3 rounded-control px-5 py-2.5 transition-colors first:pt-0 last:pb-0 hover:bg-page"
                >
                  <div className="flex min-w-0 items-center gap-2.5">
                    <ContributorAvatar contributor={contributor} />
                    <span
                      className="min-w-0 flex-1 truncate font-mono text-sm text-body"
                      title={contributor.display_name ?? contributor.identifier}
                    >
                      {contributor.display_name ?? contributor.identifier}
                    </span>
                  </div>
                  <span className="shrink-0 font-mono text-sm font-bold text-ink">
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
            <div className="divide-y divide-border">
              {changes.unusual_activity.map((flag, index) => (
                <div key={index} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
                  <span
                    className={`mt-0.5 shrink-0 rounded-tag px-1.5 py-0.5 text-[10px] font-extrabold tracking-wide text-white uppercase ${SEVERITY_TAG[flag.severity].bg}`}
                  >
                    {SEVERITY_TAG[flag.severity].label}
                  </span>
                  <span className="text-sm text-body">{flag.description}</span>
                </div>
              ))}
            </div>
          </Card>
        </section>
      )}
    </div>
  );
}
