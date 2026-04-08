import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    approveProposal: vi.fn().mockResolvedValue({ status: "approved" }),
    rejectProposal: vi.fn().mockResolvedValue({ status: "rejected" }),
    editProposal: vi.fn().mockResolvedValue({ status: "approved" }),
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/treasury/proposals",
  useParams: () => ({ dept: "treasury" }),
}));

import { ProposalActions } from "@/components/proposals/proposal-actions";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ProposalActions", () => {
  it("renders approve, reject, and edit buttons", () => {
    render(
      <ProposalActions proposalId="chg_0001" currentNewValue="3.15" />
    );

    expect(screen.getByTestId("approve-btn")).toBeInTheDocument();
    expect(screen.getByTestId("reject-btn")).toBeInTheDocument();
    expect(screen.getByTestId("edit-btn")).toBeInTheDocument();
  });

  it("approve button contains the text Approve", () => {
    render(
      <ProposalActions proposalId="chg_0001" currentNewValue="3.15" />
    );

    const approveBtn = screen.getByTestId("approve-btn");
    expect(approveBtn).toHaveTextContent("Approve");
  });

  it("reject button contains the text Reject", () => {
    render(
      <ProposalActions proposalId="chg_0001" currentNewValue="3.15" />
    );

    const rejectBtn = screen.getByTestId("reject-btn");
    expect(rejectBtn).toHaveTextContent("Reject");
  });

  it("edit button contains the text Edit", () => {
    render(
      <ProposalActions proposalId="chg_0001" currentNewValue="3.15" />
    );

    const editBtn = screen.getByTestId("edit-btn");
    expect(editBtn).toHaveTextContent("Edit");
  });

  it("clicking approve opens a confirmation dialog", async () => {
    render(
      <ProposalActions proposalId="chg_0001" currentNewValue="3.15" />
    );

    const approveBtn = screen.getByTestId("approve-btn");
    fireEvent.click(approveBtn);

    // The AlertDialog should render its content with the confirmation title
    expect(
      await screen.findByText("Apply this change?")
    ).toBeInTheDocument();
  });
});
