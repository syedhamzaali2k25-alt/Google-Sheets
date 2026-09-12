export type TabKey = "dashboard" | "documentation" | "changes";

const TABS: { key: TabKey; label: string }[] = [
  { key: "dashboard", label: "Dashboard" },
  { key: "documentation", label: "Documentation" },
  { key: "changes", label: "Change Analytics" },
];

export function Tabs({ active, onChange }: { active: TabKey; onChange: (key: TabKey) => void }) {
  return (
    <div className="max-w-full overflow-x-auto">
      <div className="flex gap-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => onChange(tab.key)}
            className={`shrink-0 rounded-t-control border-b-2 px-3 py-3 text-sm font-bold tracking-wide whitespace-nowrap transition-colors ${
              active === tab.key
                ? "border-accent-500 text-white"
                : "border-transparent text-navy-muted hover:bg-white/5 hover:text-navy-muted-hover"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  );
}
