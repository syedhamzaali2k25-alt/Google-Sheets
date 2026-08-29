function Pulse({ className }: { className: string }) {
  return <div className={`animate-pulse rounded bg-slate-200 ${className}`} />;
}

/** Mimics the loaded layout's shape while the three panels are in flight,
 * so there's no jarring shift once real content arrives. */
export function DashboardSkeleton() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="space-y-2">
          <Pulse className="h-6 w-56" />
          <Pulse className="h-4 w-40" />
        </div>
        <Pulse className="h-8 w-28" />
      </div>

      <div className="flex gap-6 border-b border-slate-200 pb-3">
        <Pulse className="h-5 w-20" />
        <Pulse className="h-5 w-28" />
        <Pulse className="h-5 w-32" />
      </div>

      <div className="mt-6 space-y-6">
        <div className="flex flex-col items-center gap-6 rounded-lg border border-slate-200 bg-white p-6 sm:flex-row sm:items-start sm:justify-between">
          <Pulse className="h-36 w-36 shrink-0 rounded-full" />
          <div className="w-full space-y-3">
            {Array.from({ length: 5 }).map((_, index) => (
              <div key={index} className="space-y-1">
                <Pulse className="h-4 w-32" />
                <Pulse className="h-2 w-full" />
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
          <Pulse className="h-4 w-24" />
          {Array.from({ length: 3 }).map((_, index) => (
            <Pulse key={index} className="h-16 w-full" />
          ))}
        </div>
      </div>
    </div>
  );
}
