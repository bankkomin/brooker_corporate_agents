"use client";

import { useEffect, useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ProposalCard } from "@/components/proposals/proposal-card";
import { apiClient } from "@/lib/api-client";
import type { Proposal } from "@/types/proposal";

type StatusFilter = "all" | "pending" | "approved" | "rejected";

export default function ProposalsPage() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<StatusFilter>("all");

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const statusParam = filter === "all" ? undefined : filter;
        const resp = await apiClient.listProposals(statusParam);
        setProposals(resp.proposals);
      } catch {
        setError("Failed to load proposals.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [filter]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Proposals</h1>

      <Tabs
        defaultValue="all"
        onValueChange={(val) => setFilter(val as StatusFilter)}
      >
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="pending">Pending</TabsTrigger>
          <TabsTrigger value="approved">Approved</TabsTrigger>
          <TabsTrigger value="rejected">Rejected</TabsTrigger>
        </TabsList>

        {(["all", "pending", "approved", "rejected"] as const).map((tab) => (
          <TabsContent key={tab} value={tab}>
            {loading && (
              <div className="py-12 text-center text-muted-foreground">
                Loading proposals...
              </div>
            )}

            {error && (
              <div className="py-12 text-center text-red-600 dark:text-red-400">
                {error}
              </div>
            )}

            {!loading && !error && proposals.length === 0 && (
              <div className="py-12 text-center text-muted-foreground">
                No proposals found.
              </div>
            )}

            {!loading && !error && proposals.length > 0 && (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {proposals.map((p) => (
                  <ProposalCard key={p.id} proposal={p} />
                ))}
              </div>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
