"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { EscalationCard } from "@/components/escalations/escalation-card";
import { apiClient } from "@/lib/api-client";
import type { EscalationItem } from "@/types/api";

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

function sortBySeverity(items: EscalationItem[]): EscalationItem[] {
  return [...items].sort((a, b) => {
    const aOrder = SEVERITY_ORDER[a.severity ?? ""] ?? 99;
    const bOrder = SEVERITY_ORDER[b.severity ?? ""] ?? 99;
    return aOrder - bOrder;
  });
}

export default function EscalationsPage() {
  const params = useParams<{ dept: string }>();
  const dept = params.dept;
  const [escalations, setEscalations] = useState<EscalationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const resp = await apiClient.listEscalations(dept);
        setEscalations(sortBySeverity(resp.escalations));
      } catch {
        setError("Failed to load escalations.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [dept]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Escalations</h1>

      {loading && (
        <div className="py-12 text-center text-muted-foreground">
          Loading escalations...
        </div>
      )}

      {error && (
        <div className="py-12 text-center text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {!loading && !error && escalations.length === 0 && (
        <div className="py-12 text-center text-muted-foreground">
          No escalations found.
        </div>
      )}

      {!loading && !error && escalations.length > 0 && (
        <div className="flex flex-col gap-3">
          {escalations.map((e) => (
            <EscalationCard key={e.id} escalation={e} />
          ))}
        </div>
      )}
    </div>
  );
}
