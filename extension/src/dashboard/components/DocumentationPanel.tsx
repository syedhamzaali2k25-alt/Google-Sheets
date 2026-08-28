import type { SpreadsheetDocumentation } from "@shared/types";

export function DocumentationPanel({ documentation }: { documentation: SpreadsheetDocumentation }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-slate-800">{documentation.title || "Untitled workbook"}</h2>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
            documentation.source === "ai_enhanced" ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-600"
          }`}
        >
          {documentation.source === "ai_enhanced" ? "AI-enhanced" : "Rule-based"}
        </span>
      </div>

      <p className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-700">
        {documentation.workbook_summary}
      </p>

      <div className="space-y-4">
        {documentation.sheet_summaries.map((sheet) => (
          <div key={sheet.sheet_name} className="rounded-lg border border-slate-200 bg-white p-4">
            <h3 className="mb-1 text-sm font-semibold text-slate-800">{sheet.sheet_name}</h3>
            <p className="text-sm text-slate-600">{sheet.summary}</p>
          </div>
        ))}
      </div>

      {documentation.relationships.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-800">Relationships</h3>
          <ul className="list-inside list-disc space-y-1 text-sm text-slate-600">
            {documentation.relationships.map((relationship) => (
              <li key={relationship.column_name}>{relationship.description}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
