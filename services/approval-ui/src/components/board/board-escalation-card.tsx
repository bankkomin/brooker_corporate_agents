"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { getDepartment, getDepartmentColor } from "@/lib/departments";
import type { EscalationItem } from "@/types/api";

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

const SEVERITY = {
  critical: { label: "Critical", className: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400", border: "border-red-500" },
  high:     { label: "High",     className: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400", border: "border-orange-500" },
  medium:   { label: "Medium",   className: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400", border: "border-yellow-500" },
  low:      { label: "Low",      className: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400", border: "border-blue-500" },
} as const;

type Severity = keyof typeof SEVERITY;

function sev(severity: string) {
  return SEVERITY[severity as Severity] ?? {
    label: severity,
    className: "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400",
    border: "border-gray-400",
  };
}

interface BoardEscalationCardProps {
  escalation: EscalationItem;
}

export function BoardEscalationCard({ escalation }: BoardEscalationCardProps) {
  const s = sev(escalation.severity);
  // Defensive: never crash the whole board if dept is null/undefined.
  const deptKey = escalation.dept ?? "unknown";
  const deptColor = getDepartmentColor(deptKey);
  const deptLabel = getDepartment(deptKey)?.shortName ?? deptKey.toUpperCase();

  return (
    <Card data-testid="board-escalation-card" className={`border-l-4 ${s.border}`}>
      <CardContent className="flex flex-col gap-2 p-3">
        <div className="flex items-center justify-between gap-2">
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${s.className}`}>
            {s.label}
          </span>
          <span className="text-[10px] text-muted-foreground whitespace-nowrap">
            {relativeTime(escalation.created_at)}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <Badge
            variant="secondary"
            className="text-[10px] font-semibold"
            style={{ backgroundColor: `${deptColor}1a`, color: deptColor }}
          >
            {deptLabel}
          </Badge>
          <span className="text-xs font-medium truncate" title={escalation.trigger_type}>
            {escalation.trigger_type}
          </span>
        </div>

        <p className="text-[11px] text-muted-foreground leading-snug line-clamp-3">
          {escalation.detail}
        </p>
      </CardContent>
    </Card>
  );
}
