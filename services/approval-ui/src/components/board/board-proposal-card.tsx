"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { getDepartment, getDepartmentColor } from "@/lib/departments";
import type { Proposal } from "@/types/proposal";

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffSec = Math.floor((now - then) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${Math.floor(diffHr / 24)}d ago`;
}

interface BoardProposalCardProps {
  proposal: Proposal;
}

export function BoardProposalCard({ proposal }: BoardProposalCardProps) {
  // Defensive: never crash the whole board if dept is null/undefined.
  const deptKey = proposal.dept ?? "unknown";
  const dept = getDepartment(deptKey);
  const color = getDepartmentColor(deptKey);
  const deptLabel = dept?.shortName ?? deptKey.toUpperCase();

  return (
    <Card data-testid="board-proposal-card" className="border-l-4" style={{ borderLeftColor: color }}>
      <CardContent className="flex flex-col gap-2 p-3">
        <div className="flex items-center justify-between gap-2">
          <Badge
            variant="secondary"
            className="text-[10px] font-semibold"
            style={{ backgroundColor: `${color}1a`, color }}
          >
            {deptLabel}
          </Badge>
          <span className="text-[10px] text-muted-foreground whitespace-nowrap">
            {relativeTime(proposal.created_at)}
          </span>
        </div>

        <div className="text-xs font-medium text-foreground truncate" title={proposal.agent}>
          {proposal.agent}
        </div>

        <div
          className="text-[11px] text-muted-foreground truncate"
          title={`${proposal.file} · ${proposal.tab} · ${proposal.cell}`}
        >
          {proposal.file} · {proposal.cell}
        </div>

        <div className="flex items-center gap-1.5 text-[11px] font-mono">
          <span className="rounded bg-red-100 px-1.5 py-0.5 text-red-700 dark:bg-red-900/30 dark:text-red-400 truncate max-w-[45%]">
            {proposal.old_value ?? "null"}
          </span>
          <span className="text-muted-foreground">→</span>
          <span className="rounded bg-green-100 px-1.5 py-0.5 text-green-700 dark:bg-green-900/30 dark:text-green-400 truncate max-w-[45%]">
            {proposal.new_value}
          </span>
        </div>

        <div className="text-[10px] text-muted-foreground">
          Confidence: {Math.round(proposal.confidence * 100)}%
        </div>
      </CardContent>
    </Card>
  );
}
