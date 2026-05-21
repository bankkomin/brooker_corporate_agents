"use client";

import type { Proposal } from "@/types/proposal";

interface ProposalDiffProps {
  proposal: Proposal;
}

export function ProposalDiff({ proposal }: ProposalDiffProps) {
  return (
    <div data-testid="proposal-diff" className="flex flex-col md:flex-row gap-4">
      {/* Current Value (left / top) */}
      <div className="flex-1 rounded-lg border border-red-200 dark:border-red-800 overflow-hidden">
        <div className="bg-red-50 dark:bg-red-950/30 px-4 py-2 border-b border-red-200 dark:border-red-800">
          <h3 className="text-sm font-semibold text-red-800 dark:text-red-400">
            Current Value
          </h3>
          <p className="text-xs text-red-600 dark:text-red-500 mt-0.5">
            {proposal.file ?? "—"} &rarr; {proposal.tab ?? "—"} &rarr;{" "}
            {proposal.cell ?? "—"}
          </p>
        </div>
        <div className="bg-red-50/50 dark:bg-red-950/20 px-4 py-3">
          <pre className="text-sm font-mono whitespace-pre-wrap break-words text-red-800 dark:text-red-300">
            {proposal.old_value ?? "null"}
          </pre>
        </div>
      </div>

      {/* Proposed Value (right / bottom) */}
      <div className="flex-1 rounded-lg border border-green-200 dark:border-green-800 overflow-hidden">
        <div className="bg-green-50 dark:bg-green-950/30 px-4 py-2 border-b border-green-200 dark:border-green-800">
          <h3 className="text-sm font-semibold text-green-800 dark:text-green-400">
            Proposed Value
          </h3>
          <p className="text-xs text-green-600 dark:text-green-500 mt-0.5">
            Agent: {proposal.agent ?? "Unknown"}
          </p>
        </div>
        <div className="bg-green-50/50 dark:bg-green-950/20 px-4 py-3">
          <pre className="text-sm font-mono whitespace-pre-wrap break-words text-green-800 dark:text-green-300">
            {proposal.new_value ?? "—"}
          </pre>
        </div>
      </div>
    </div>
  );
}
