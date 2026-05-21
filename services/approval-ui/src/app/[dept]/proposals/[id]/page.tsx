"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ProposalDiff } from "@/components/proposals/proposal-diff";
import { ProposalReasoning } from "@/components/proposals/proposal-reasoning";
import { ProposalActions } from "@/components/proposals/proposal-actions";
import { apiClient } from "@/lib/api-client";
import { getToken } from "@/lib/auth";
import { ArrowLeftIcon } from "lucide-react";
import type { Proposal } from "@/types/proposal";

export default function ProposalDetailPage() {
  const params = useParams<{ dept: string; id: string }>();
  const router = useRouter();
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProposal = useCallback(async () => {
    const token = getToken();
    if (!token) {
      router.replace("/approve?error=session_expired");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getProposal(params.id);
      setProposal(data);
    } catch {
      setError("Proposal not found.");
    } finally {
      setLoading(false);
    }
  }, [params.id, router]);

  useEffect(() => {
    loadProposal();
  }, [loadProposal]);

  if (loading) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        Loading proposal...
      </div>
    );
  }

  if (error || !proposal) {
    return (
      <div className="space-y-4 py-12 text-center">
        <p className="text-red-600 dark:text-red-400">
          {error ?? "Proposal not found."}
        </p>
        <Button variant="outline" onClick={() => router.back()}>
          <ArrowLeftIcon className="size-4" />
          Go Back
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => router.push(`/${params.dept}/proposals`)}
        >
          <ArrowLeftIcon className="size-4" />
        </Button>
        <div>
          <h1 className="text-xl font-semibold">
            {proposal.agent ?? "Unknown agent"} &mdash;{" "}
            {proposal.file ?? "—"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {proposal.tab ?? "—"} &rarr; {proposal.cell ?? "—"}
          </p>
        </div>
      </div>

      <ProposalDiff proposal={proposal} />

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardContent>
            <ProposalReasoning proposal={proposal} />
          </CardContent>
        </Card>

        {proposal.status === "pending" && (
          <Card>
            <CardContent>
              <h3 className="text-sm font-semibold mb-3">Actions</h3>
              <ProposalActions
                proposalId={proposal.id}
                currentNewValue={proposal.new_value}
                onActionComplete={loadProposal}
              />
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
