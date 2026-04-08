import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import type { Proposal } from "@/types/proposal";

// ---------------------------------------------------------------------------
// Mocks — must be declared before component import
// ---------------------------------------------------------------------------

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => "/treasury/proposals",
  useParams: () => ({ dept: "treasury" }),
}));

vi.mock("@/lib/departments", () => ({
  getDepartmentColor: (_dept: string) => "#3b82f6",
  getDepartment: () => ({
    name: "Treasury",
    shortName: "TRS",
    color: "#3b82f6",
    dashboardWidgets: ["proposals"],
  }),
}));

// Import after mocks are in place
import { ProposalCard } from "@/components/proposals/proposal-card";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeProposal(overrides: Partial<Proposal> = {}): Proposal {
  return {
    id: "chg_0001",
    created_at: new Date().toISOString(),
    agent: "funding-agent",
    file: "ALCO_Tracker.xlsx",
    tab: "Funding Facilities",
    cell: "E8",
    old_value: "2.75",
    new_value: "3.15",
    confidence: 0.91,
    reasoning: "Rate updated per latest Slack discussion",
    status: "pending",
    dept: "treasury",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ProposalCard", () => {
  it("renders agent name, file, and old/new values", () => {
    const proposal = makeProposal();
    render(<ProposalCard proposal={proposal} />);

    expect(screen.getByText("funding-agent")).toBeInTheDocument();
    // agent + file are combined in a single line
    expect(
      screen.getByText(/funding-agent.*ALCO_Tracker\.xlsx/i)
    ).toBeInTheDocument();
    expect(screen.getByText("2.75")).toBeInTheDocument();
    expect(screen.getByText("3.15")).toBeInTheDocument();
  });

  it("shows confidence percentage", () => {
    const proposal = makeProposal({ confidence: 0.85 });
    render(<ProposalCard proposal={proposal} />);

    expect(screen.getByText("Confidence: 85%")).toBeInTheDocument();
  });

  it("shows correct status badge for pending", () => {
    render(<ProposalCard proposal={makeProposal({ status: "pending" })} />);
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("shows correct status badge for approved", () => {
    render(<ProposalCard proposal={makeProposal({ status: "approved" })} />);
    expect(screen.getByText("Approved")).toBeInTheDocument();
  });

  it("shows correct status badge for rejected", () => {
    render(<ProposalCard proposal={makeProposal({ status: "rejected" })} />);
    expect(screen.getByText("Rejected")).toBeInTheDocument();
  });

  it("displays null for missing old_value", () => {
    render(
      <ProposalCard proposal={makeProposal({ old_value: null })} />
    );
    expect(screen.getByText("null")).toBeInTheDocument();
  });
});
