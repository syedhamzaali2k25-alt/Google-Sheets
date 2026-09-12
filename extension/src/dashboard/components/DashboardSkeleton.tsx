import { NAVY_HEADER_FROM, NAVY_HEADER_TO } from "../../lib/theme";

function Pulse({ className }: { className: string }) {
  // No default radius here: every call site names its own rounded-* class
  // (radius utilities don't compose safely — two of them on one element
  // race on stylesheet order, not className order — so exactly one must
  // ever be present).
  return <div className={`animate-pulse ${className}`} />;
}

/** Mimics the loaded report's shape (navy header, gauge + category list
 * card, findings card, collaborators card) while the four panels are in
 * flight, so there's no jarring shift once real content arrives. */
export function DashboardSkeleton() {
  return (
    <div className="min-h-screen bg-page">
      <div className="px-6 pt-9 shadow-header" style={{ background: `linear-gradient(135deg, ${NAVY_HEADER_FROM}, ${NAVY_HEADER_TO})` }}>
        <div className="mx-auto max-w-5xl">
          <div className="flex flex-col gap-6 pb-7 sm:flex-row sm:items-end sm:justify-between">
            <div className="flex items-center gap-3.5">
              <Pulse className="h-[30px] w-[30px] rounded-control bg-white/10" />
              <div className="space-y-2">
                <Pulse className="h-2.5 w-40 rounded-tag bg-white/10" />
                <Pulse className="h-8 w-56 rounded-tag bg-white/10" />
              </div>
            </div>
            <div className="space-y-2">
              <Pulse className="h-3 w-32 rounded-tag bg-white/10" />
              <Pulse className="h-3 w-24 rounded-tag bg-white/10" />
            </div>
          </div>
          <div className="flex gap-6 border-t border-white/10 py-3">
            <Pulse className="h-4 w-20 rounded-tag bg-white/10" />
            <Pulse className="h-4 w-28 rounded-tag bg-white/10" />
            <Pulse className="h-4 w-32 rounded-tag bg-white/10" />
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-5xl space-y-10 px-6 py-10">
        <div>
          <Pulse className="mb-3 h-3 w-32 rounded-tag bg-border" />
          <div className="rounded-card border border-border bg-surface p-6 shadow-card">
            <div className="flex flex-col gap-8 md:flex-row">
              <div className="flex flex-1 items-center justify-center">
                <Pulse className="h-[130px] w-[220px] rounded-2xl bg-track" />
              </div>
              <div className="flex-1 space-y-4">
                {Array.from({ length: 5 }).map((_, index) => (
                  <div key={index} className="space-y-2">
                    <Pulse className="h-3.5 w-full rounded-tag bg-track" />
                    <Pulse className="h-1.5 w-full rounded-full bg-track" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div>
          <Pulse className="mb-3 h-3 w-24 rounded-tag bg-border" />
          <div className="space-y-4 rounded-card border border-border bg-surface p-5 shadow-card">
            {Array.from({ length: 3 }).map((_, index) => (
              <Pulse key={index} className="h-16 w-full rounded-control bg-track" />
            ))}
          </div>
        </div>

        <div>
          <Pulse className="mb-3 h-3 w-28 rounded-tag bg-border" />
          <div className="space-y-3 rounded-card border border-border bg-surface p-5 shadow-card">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="flex items-center gap-3">
                <Pulse className="h-8 w-8 rounded-full bg-track" />
                <Pulse className="h-3.5 flex-1 rounded-tag bg-track" />
                <Pulse className="h-4 w-14 rounded-tag bg-track" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
