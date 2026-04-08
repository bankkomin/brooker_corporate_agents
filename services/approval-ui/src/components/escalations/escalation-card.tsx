"use client";

import { Card, CardContent } from "@/components/ui/card";
import type { EscalationItem } from "@/types/api";

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

const severityConfig = {
  critical: {
    label: "Critical",
    className:
      "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
    borderClassName: "border-l-4 border-red-500",
  },
  high: {
    label: "High",
    className:
      "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
    borderClassName: "border-l-4 border-orange-500",
  },
  medium: {
    label: "Medium",
    className:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
    borderClassName: "border-l-4 border-yellow-500",
  },
  low: {
    label: "Low",
    className:
      "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
    borderClassName: "border-l-4 border-blue-500",
  },
} as const;

type Severity = keyof typeof severityConfig;

function getSeverityConfig(severity: string) {
  return (
    severityConfig[severity as Severity] ?? {
      label: severity,
      className:
        "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400",
      borderClassName: "border-l-4 border-gray-400",
    }
  );
}

interface EscalationCardProps {
  escalation: EscalationItem;
}

export function EscalationCard({ escalation }: EscalationCardProps) {
  const sev = getSeverityConfig(escalation.severity);

  return (
    <Card
      data-testid="escalation-card"
      className={sev.borderClassName}
    >
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${sev.className}`}
            >
              {sev.label}
            </span>
            <span className="font-medium text-sm">{escalation.trigger_type}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {escalation.resolved_at && (
              <span
                className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-400"
                title={`Resolved ${relativeTime(escalation.resolved_at)}`}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="h-3.5 w-3.5"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
                    clipRule="evenodd"
                  />
                </svg>
                Resolved
              </span>
            )}
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              {relativeTime(escalation.created_at)}
            </span>
          </div>
        </div>

        <p className="text-sm text-muted-foreground leading-relaxed">
          {escalation.detail}
        </p>
      </CardContent>
    </Card>
  );
}
