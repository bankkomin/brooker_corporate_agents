"use client";

import { useRouter, useParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { getDepartmentColor } from "@/lib/departments";
import type { Proposal } from "@/types/proposal";

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

const statusConfig = {
  pending: { label: "Pending", className: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400" },
  approved: { label: "Approved", className: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400" },
  rejected: { label: "Rejected", className: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400" },
} as const;

interface ProposalCardProps {
  proposal: Proposal;
}

export function ProposalCard({ proposal }: ProposalCardProps) {
  const router = useRouter();
  const params = useParams<{ dept: string }>();
  const dept = params.dept;
  const agentColor = getDepartmentColor(proposal.dept);
  const status = statusConfig[proposal.status];

  return (
    <Card
      data-testid="proposal-card"
      className="cursor-pointer transition-shadow hover:shadow-md"
      onClick={() => router.push(`/${dept}/proposals/${proposal.id}`)}
    >
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full shrink-0"
              style={{ backgroundColor: agentColor }}
            />
            <Badge variant="secondary" className="text-xs">
              {proposal.agent}
            </Badge>
          </div>
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {relativeTime(proposal.created_at)}
          </span>
        </div>

        <div className="font-medium text-sm">
          {proposal.agent} &mdash; {proposal.file}
        </div>

        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="rounded bg-red-100 px-1.5 py-0.5 text-red-700 dark:bg-red-900/30 dark:text-red-400 truncate max-w-[40%]">
            {proposal.old_value ?? "null"}
          </span>
          <span className="text-muted-foreground">&rarr;</span>
          <span className="rounded bg-green-100 px-1.5 py-0.5 text-green-700 dark:bg-green-900/30 dark:text-green-400 truncate max-w-[40%]">
            {proposal.new_value}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            Confidence: {Math.round(proposal.confidence * 100)}%
          </span>
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${status.className}`}
          >
            {status.label}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
