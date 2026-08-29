import type { SpreadsheetDocumentation } from "@shared/types";
import { Card, SectionLabel } from "./ReportPrimitives";

export function DocumentationPanel({ documentation }: { documentation: SpreadsheetDocumentation }) {
  const isAiEnhanced = documentation.source === "ai_enhanced";

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-extrabold text-[#1A2233]">{documentation.title || "Untitled workbook"}</h1>
        <span
          className={`shrink-0 rounded-[3px] px-2 py-0.5 text-[10px] font-extrabold tracking-wide uppercase ${
            isAiEnhanced ? "bg-[#EAF0FF] text-[#3B5FCC]" : "bg-[#EEF0F4] text-[#5B6478]"
          }`}
        >
          {isAiEnhanced ? "AI-Enhanced" : "Rule-Based"}
        </span>
      </div>

      <section>
        <SectionLabel>Workbook Summary</SectionLabel>
        <Card className="p-5">
          <p className="text-sm text-[#2B3245]">{documentation.workbook_summary}</p>
        </Card>
      </section>

      <section>
        <SectionLabel>Sheets</SectionLabel>
        <Card className="p-5">
          <div className="divide-y divide-[#E7E9EE]">
            {documentation.sheet_summaries.map((sheet) => (
              <div key={sheet.sheet_name} className="py-4 first:pt-0 last:pb-0">
                <h3 className="mb-1 font-mono text-xs font-bold tracking-wide text-[#4F7CFF] uppercase">
                  {sheet.sheet_name}
                </h3>
                <p className="text-sm text-[#2B3245]">{sheet.summary}</p>
              </div>
            ))}
          </div>
        </Card>
      </section>

      {documentation.relationships.length > 0 && (
        <section>
          <SectionLabel>Relationships</SectionLabel>
          <Card className="p-5">
            <div className="divide-y divide-[#E7E9EE]">
              {documentation.relationships.map((relationship) => (
                <div key={relationship.column_name} className="py-3 text-sm text-[#2B3245] first:pt-0 last:pb-0">
                  {relationship.description}
                </div>
              ))}
            </div>
          </Card>
        </section>
      )}
    </div>
  );
}
