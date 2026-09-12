import type { Collaborator, CollaboratorsResponse } from "@shared/types";
import { Card, SectionLabel } from "./ReportPrimitives";

const ROLE_LABEL: Record<Collaborator["role"], string> = {
  owner: "Owner",
  organizer: "Organizer",
  fileOrganizer: "Organizer",
  writer: "Editor",
  commenter: "Commenter",
  reader: "Viewer",
};

// Reuses hex values already established elsewhere rather than inventing a
// new palette: #0B1120 is the navy header color (lib/theme.ts
// NAVY_HEADER_FROM), #4F7CFF is the accent blue (lib/theme.ts ACCENT_BLUE),
// and #8A93A6/#5B6478 are the same muted grays used throughout
// severity.ts and FindingsList for low-emphasis tags and text.
const ROLE_BADGE: Record<Collaborator["role"], string> = {
  owner: "bg-[#0B1120]",
  organizer: "bg-[#0B1120]",
  fileOrganizer: "bg-[#0B1120]",
  writer: "bg-[#4F7CFF]",
  commenter: "bg-[#8A93A6]",
  reader: "bg-[#5B6478]",
};

function collaboratorLabel(collaborator: Collaborator): string {
  if (collaborator.type === "anyone") return "Anyone with the link";
  if (collaborator.type === "domain") return `Anyone at ${collaborator.domain ?? "this domain"}`;
  return collaborator.display_name || collaborator.email || "Unknown collaborator";
}

function collaboratorSecondaryLine(collaborator: Collaborator): string | null {
  // Only worth a second line when it adds information beyond the primary
  // label above — e.g. a display name with an email underneath it. A
  // domain/anyone permission, or a user with no display name (whose email
  // is already the primary label), has nothing more to show.
  if (collaborator.type !== "user" && collaborator.type !== "group") return null;
  if (collaborator.display_name && collaborator.email) return collaborator.email;
  return null;
}

export function CollaboratorsPanel({ collaborators }: { collaborators: CollaboratorsResponse }) {
  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <SectionLabel>Shared With</SectionLabel>
        <span className="text-xs font-bold text-[#8A93A6]">
          {collaborators.total_count} collaborator{collaborators.total_count === 1 ? "" : "s"}
        </span>
      </div>

      <Card className="p-5">
        {collaborators.collaborators.length === 0 ? (
          <p className="text-sm text-[#8A93A6]">No sharing information is available for this sheet.</p>
        ) : (
          <>
            {collaborators.total_count === 1 && (
              <p className="mb-3 text-sm text-[#8A93A6]">
                This sheet is only shared with its owner — no other collaborators have access.
              </p>
            )}
            <div className="divide-y divide-[#E7E9EE]">
              {collaborators.collaborators.map((collaborator, index) => {
                const label = collaboratorLabel(collaborator);
                const secondary = collaboratorSecondaryLine(collaborator);
                return (
                  <div
                    key={`${collaborator.type}-${collaborator.email ?? collaborator.domain ?? index}`}
                    className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-[#2B3245]" title={label}>
                        {label}
                      </p>
                      {secondary && (
                        <p className="truncate font-mono text-xs text-[#8A93A6]" title={secondary}>
                          {secondary}
                        </p>
                      )}
                    </div>
                    <span
                      className={`shrink-0 rounded-[3px] px-1.5 py-0.5 text-[10px] font-extrabold tracking-wide text-white uppercase ${ROLE_BADGE[collaborator.role]}`}
                    >
                      {ROLE_LABEL[collaborator.role]}
                    </span>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </Card>
    </section>
  );
}
