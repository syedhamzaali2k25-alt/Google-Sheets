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
// new palette: navy-950 is the header color, accent-500 the accent blue,
// and low-500/subtle are the same muted grays used throughout severity.ts
// and FindingsList for low-emphasis tags and text.
const ROLE_BADGE: Record<Collaborator["role"], string> = {
  owner: "bg-navy-950",
  organizer: "bg-navy-950",
  fileOrganizer: "bg-navy-950",
  writer: "bg-accent-500",
  commenter: "bg-low-500",
  reader: "bg-subtle",
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

function LinkIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path
        d="M8.5 11.5a3 3 0 0 0 4.4.2l2-2a3 3 0 0 0-4.24-4.24l-1.1 1.1M11.5 8.5a3 3 0 0 0-4.4-.2l-2 2a3 3 0 0 0 4.24 4.24l1.1-1.1"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function DomainIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5" />
      <path d="M3 10h14M10 3c1.8 2 1.8 12 0 14M10 3c-1.8 2-1.8 12 0 14" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function CollaboratorAvatar({ collaborator, label }: { collaborator: Collaborator; label: string }) {
  if (collaborator.type === "anyone" || collaborator.type === "domain") {
    return (
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-track text-subtle">
        {collaborator.type === "anyone" ? <LinkIcon /> : <DomainIcon />}
      </span>
    );
  }
  const initial = label.trim().charAt(0).toUpperCase() || "?";
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-navy-950 text-xs font-bold text-white">
      {initial}
    </span>
  );
}

export function CollaboratorsPanel({ collaborators }: { collaborators: CollaboratorsResponse }) {
  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <SectionLabel>Shared With</SectionLabel>
        <span className="text-xs font-bold text-muted">
          {collaborators.total_count} collaborator{collaborators.total_count === 1 ? "" : "s"}
        </span>
      </div>

      <Card className="p-5">
        {collaborators.collaborators.length === 0 ? (
          <p className="text-sm text-muted">No sharing information is available for this sheet.</p>
        ) : (
          <>
            {collaborators.total_count === 1 && (
              <p className="mb-3 text-sm text-muted">
                This sheet is only shared with its owner — no other collaborators have access.
              </p>
            )}
            <div className="divide-y divide-border">
              {collaborators.collaborators.map((collaborator, index) => {
                const label = collaboratorLabel(collaborator);
                const secondary = collaboratorSecondaryLine(collaborator);
                return (
                  <div
                    key={`${collaborator.type}-${collaborator.email ?? collaborator.domain ?? index}`}
                    className="-mx-5 flex items-center gap-3 rounded-control px-5 py-2.5 transition-colors first:pt-0 last:pb-0 hover:bg-page"
                  >
                    <CollaboratorAvatar collaborator={collaborator} label={label} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-body" title={label}>
                        {label}
                      </p>
                      {secondary && (
                        <p className="truncate font-mono text-xs text-muted" title={secondary}>
                          {secondary}
                        </p>
                      )}
                    </div>
                    <span
                      className={`shrink-0 rounded-tag px-1.5 py-0.5 text-[10px] font-extrabold tracking-wide text-white uppercase ${ROLE_BADGE[collaborator.role]}`}
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
