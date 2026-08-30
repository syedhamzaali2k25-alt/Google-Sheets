export type TabKey = "dashboard" | "documentation" | "changes";

const TABS: { key: TabKey; label: string }[] = [
  { key: "dashboard", label: "Dashboard" },
  { key: "documentation", label: "Documentation" },
  { key: "changes", label: "Change Analytics" },
];

export function Tabs({ active, onChange }: { active: TabKey; onChange: (key: TabKey) => void }) {
  return (
    <div className="max-w-full overflow-x-auto">
      <div className="flex gap-6">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => onChange(tab.key)}
            className={`shrink-0 border-b-2 py-3 text-sm font-bold tracking-wide whitespace-nowrap transition-colors ${
              active === tab.key
                ? "border-[#4F7CFF] text-white"
                : "border-transparent text-[#6B7C9E] hover:text-[#9AA6C0]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  );
}
