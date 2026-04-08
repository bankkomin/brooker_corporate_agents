"use client";

import { getDepartmentColor } from "@/lib/departments";
import type { Proposal } from "@/types/proposal";

interface ProposalReasoningProps {
  proposal: Proposal;
}

export function ProposalReasoning({ proposal }: ProposalReasoningProps) {
  const agentColor = getDepartmentColor(proposal.dept);
  const confidencePct = Math.round(proposal.confidence * 100);

  return (
    <div data-testid="proposal-reasoning" className="space-y-4">
      {/* Agent identity */}
      <div className="flex items-center gap-2">
        <span
          className="inline-block h-3 w-3 rounded-full shrink-0"
          style={{ backgroundColor: agentColor }}
        />
        <span className="text-sm font-semibold">{proposal.agent}</span>
      </div>

      {/* Confidence gauge */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Confidence</span>
          <span className="font-medium">{confidencePct}%</span>
        </div>
        <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${confidencePct}%`,
              backgroundColor:
                confidencePct >= 80
                  ? "#16a34a"
                  : confidencePct >= 50
                    ? "#d97706"
                    : "#dc2626",
            }}
          />
        </div>
      </div>

      {/* Reasoning */}
      <div className="space-y-1">
        <h4 className="text-sm font-semibold">Reasoning</h4>
        <p className="text-sm text-muted-foreground whitespace-pre-wrap">
          {proposal.reasoning}
        </p>
      </div>

      {/* Sources */}
      {proposal.source && (
        <div className="space-y-1">
          <h4 className="text-sm font-semibold">Sources</h4>
          <p className="text-sm text-muted-foreground whitespace-pre-wrap">
            {proposal.source}
          </p>
        </div>
      )}
    </div>
  );
}
