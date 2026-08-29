function Pulse({ className }: { className: string }) {
  return <div className={`animate-pulse rounded-[3px] ${className}`} />;
}

/** Mimics the loaded report's shape (navy header, gauge + category list card,
 * findings card) while the three panels are in flight, so there's no
 * jarring shift once real content arrives. */
export function DashboardSkeleton() {
  return (
    <div className="min-h-screen bg-[#F5F6F8]">
      <div className="bg-gradient-to-b from-[#0B1120] to-[#131B2E] px-6 pt-8">
        <div className="mx-auto max-w-5xl">
          <div className="flex flex-col gap-6 pb-6 sm:flex-row sm:items-end sm:justify-between">
            <div className="flex items-center gap-3">
              <Pulse className="h-9 w-9 bg-white/10" />
              <div className="space-y-2">
                <Pulse className="h-2.5 w-40 bg-white/10" />
                <Pulse className="h-7 w-56 bg-white/10" />
              </div>
            </div>
            <div className="space-y-2">
              <Pulse className="h-3 w-32 bg-white/10" />
              <Pulse className="h-3 w-24 bg-white/10" />
            </div>
          </div>
          <div className="flex gap-6 border-t border-white/10 py-3">
            <Pulse className="h-4 w-20 bg-white/10" />
            <Pulse className="h-4 w-28 bg-white/10" />
            <Pulse className="h-4 w-32 bg-white/10" />
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-5xl space-y-8 px-6 py-8">
        <div>
          <Pulse className="mb-3 h-3 w-32 bg-[#E7E9EE]" />
          <div className="rounded-[4px] border border-[#E7E9EE] bg-white p-6">
            <div className="flex flex-col gap-8 md:flex-row">
              <div className="flex flex-1 items-center justify-center">
                <Pulse className="h-[130px] w-[220px] bg-[#EEF0F4]" />
              </div>
              <div className="flex-1 space-y-4">
                {Array.from({ length: 5 }).map((_, index) => (
                  <div key={index} className="space-y-2">
                    <Pulse className="h-3.5 w-full bg-[#EEF0F4]" />
                    <Pulse className="h-1.5 w-full bg-[#EEF0F4]" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div>
          <Pulse className="mb-3 h-3 w-24 bg-[#E7E9EE]" />
          <div className="space-y-4 rounded-[4px] border border-[#E7E9EE] bg-white p-5">
            {Array.from({ length: 3 }).map((_, index) => (
              <Pulse key={index} className="h-16 w-full bg-[#EEF0F4]" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
