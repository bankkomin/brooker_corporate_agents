"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { StatsCards } from "@/components/analytics/stats-cards";
import { ProposalCard } from "@/components/proposals/proposal-card";
import { EscalationCard } from "@/components/escalations/escalation-card";
import { apiClient } from "@/lib/api-client";
import type { Proposal } from "@/types/proposal";
import type { EscalationItem, AnalyticsSummary } from "@/types/api";

export default function DepartmentHomePage() {
  const params = useParams<{ dept: string }>();
  const dept = params.dept;

  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [escalations, setEscalations] = useState<EscalationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [summaryData, proposalsData, escalationsData] = await Promise.all([
          apiClient.getAnalyticsSummary(dept),
          apiClient.listProposals("pending", dept),
          apiClient.listEscalations(dept),
        ]);
        setSummary(summaryData);
        setProposals(proposalsData.proposals.slice(0, 5));
        // Only show unresolved escalations on the home page
        setEscalations(
          escalationsData.escalations.filter((e) => !e.resolved_at)
        );
      } catch {
        setError("Failed to load dashboard.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [dept]);

  if (loading) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        Loading dashboard...
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-12 text-center text-red-600 dark:text-red-400">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Overview for your department
        </p>
      </div>

      {summary && <StatsCards summary={summary} />}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">Recent Pending Proposals</h2>
          <Link
            href={`/${dept}/proposals`}
            className="text-sm text-primary hover:underline"
          >
            View all
          </Link>
        </div>

        {proposals.length === 0 ? (
          <div className="py-6 text-center text-muted-foreground text-sm rounded-xl border border-dashed">
            No pending proposals.
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {proposals.map((p) => (
              <ProposalCard key={p.id} proposal={p} />
            ))}
          </div>
        )}
      </section>

      {escalations.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium">Active Escalations</h2>
            <Link
              href={`/${dept}/escalations`}
              className="text-sm text-primary hover:underline"
            >
              View all
            </Link>
          </div>
          <div className="flex flex-col gap-3">
            {escalations.map((e) => (
              <EscalationCard key={e.id} escalation={e} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
