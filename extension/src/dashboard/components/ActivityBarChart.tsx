import type { ActivityEvent } from "@shared/types";

interface DayBucket {
  date: string;
  count: number;
}

const MAX_BAR_HEIGHT_PX = 120;

function bucketEventsByDay(events: ActivityEvent[]): DayBucket[] {
  const counts = new Map<string, number>();
  for (const event of events) {
    const day = event.timestamp.slice(0, 10); // YYYY-MM-DD
    counts.set(day, (counts.get(day) ?? 0) + 1);
  }
  return [...counts.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([date, count]) => ({ date, count }));
}

export function ActivityBarChart({ events }: { events: ActivityEvent[] }) {
  const buckets = bucketEventsByDay(events);

  if (buckets.length === 0) {
    return <p className="text-sm text-slate-500">No activity in this time window.</p>;
  }

  const max = Math.max(...buckets.map((bucket) => bucket.count));

  return (
    <div className="flex items-end gap-1 overflow-x-auto pb-1" style={{ height: MAX_BAR_HEIGHT_PX + 24 }}>
      {buckets.map((bucket) => {
        const heightPx = Math.max(4, Math.round((bucket.count / max) * MAX_BAR_HEIGHT_PX));
        return (
          <div key={bucket.date} className="flex min-w-[18px] flex-1 flex-col items-center justify-end gap-1">
            <div
              className="w-full rounded-t bg-blue-500"
              style={{ height: `${heightPx}px` }}
              title={`${bucket.date}: ${bucket.count} event${bucket.count === 1 ? "" : "s"}`}
            />
            <span className="text-[9px] whitespace-nowrap text-slate-400">{bucket.date.slice(5)}</span>
          </div>
        );
      })}
    </div>
  );
}
