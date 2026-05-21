"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { StatsCards } from "@/components/analytics/stats-cards";
import { apiClient } from "@/lib/api-client";
import type { AnalyticsSummary } from "@/types/api";

export default function AnalyticsPage() {
  const params = useParams<{ dept: string }>();
  const dept = params.dept;
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await apiClient.getAnalyticsSummary(dept);
        setSummary(data);
      } catch {
        setError("Failed to load analytics.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [dept]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Analytics</h1>

      {loading && (
        <div className="py-12 text-center text-muted-foreground">
          Loading analytics...
        </div>
      )}

      {error && (
        <div className="py-12 text-center text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {!loading && !error && summary && (
        <>
          <StatsCards summary={summary} />
          <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
            Detailed charts coming in Stage 7
          </div>
        </>
      )}
    </div>
  );
}
