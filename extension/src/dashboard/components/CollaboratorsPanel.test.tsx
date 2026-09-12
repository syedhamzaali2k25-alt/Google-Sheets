import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Collaborator, CollaboratorsResponse } from "@shared/types";
import { ErrorBanner } from "./StatusViews";
import { CollaboratorsPanel } from "./CollaboratorsPanel";

function makeResponse(collaborators: Collaborator[]): CollaboratorsResponse {
  return { collaborators, total_count: collaborators.length };
}

describe("CollaboratorsPanel", () => {
  it("renders a normal list of collaborators with their role badges", () => {
    render(
      <CollaboratorsPanel
        collaborators={makeResponse([
          { type: "user", role: "owner", email: "owner@example.com", display_name: "Olivia Owner", domain: null },
          { type: "user", role: "writer", email: "editor@example.com", display_name: "Eli Editor", domain: null },
          { type: "user", role: "commenter", email: "carl@example.com", display_name: null, domain: null },
          { type: "user", role: "reader", email: "vera@example.com", display_name: "Vera Viewer", domain: null },
        ])}
      />,
    );

    expect(screen.getByText("Olivia Owner")).toBeInTheDocument();
    expect(screen.getByText("owner@example.com")).toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();

    expect(screen.getByText("Eli Editor")).toBeInTheDocument();
    expect(screen.getByText("Editor")).toBeInTheDocument();

    // No display name -> falls back to showing the email as the primary
    // label, and doesn't also repeat it as a redundant second line.
    expect(screen.getByText("carl@example.com")).toBeInTheDocument();
    expect(screen.getByText("Commenter")).toBeInTheDocument();

    expect(screen.getByText("Vera Viewer")).toBeInTheDocument();
    expect(screen.getByText("Viewer")).toBeInTheDocument();

    expect(screen.getByText("4 collaborators")).toBeInTheDocument();
  });

  it("falls back to readable text for anyone-with-link and domain-wide permissions", () => {
    render(
      <CollaboratorsPanel
        collaborators={makeResponse([
          { type: "user", role: "owner", email: "owner@example.com", display_name: "Olivia Owner", domain: null },
          { type: "anyone", role: "reader", email: null, display_name: null, domain: null },
          { type: "domain", role: "writer", email: null, display_name: null, domain: "example.com" },
        ])}
      />,
    );

    expect(screen.getByText("Anyone with the link")).toBeInTheDocument();
    expect(screen.getByText("Anyone at example.com")).toBeInTheDocument();
    // Neither fallback row renders a blank/null email or domain line.
    expect(screen.queryByText("null")).not.toBeInTheDocument();
  });

  it("explicitly calls out the single-owner (nothing else shared) case", () => {
    render(
      <CollaboratorsPanel
        collaborators={makeResponse([
          { type: "user", role: "owner", email: "solo@example.com", display_name: "Solo Owner", domain: null },
        ])}
      />,
    );

    expect(screen.getByText(/only shared with its owner/i)).toBeInTheDocument();
    expect(screen.getByText("Solo Owner")).toBeInTheDocument();
    expect(screen.getByText("1 collaborator")).toBeInTheDocument();
  });

  it("shows a neutral message when no sharing information is available at all", () => {
    render(<CollaboratorsPanel collaborators={makeResponse([])} />);
    expect(screen.getByText(/no sharing information is available/i)).toBeInTheDocument();
  });
});

describe("CollaboratorsPanel error state", () => {
  // The dashboard (App.tsx) fetches collaborators independently of health/
  // documentation/changes and renders this same ErrorBanner used by every
  // other panel when the fetch fails — reusing the existing error pattern
  // rather than giving this panel its own bespoke one.
  it("renders the shared ErrorBanner with the failure message", () => {
    render(<ErrorBanner message="Could not fetch who this sheet is shared with." />);
    expect(screen.getByText("Could not fetch who this sheet is shared with.")).toBeInTheDocument();
  });
});
