"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";

interface SkillProposal {
  id: number;
  dept_id: string;
  agent_id: string;
  skill_path: string;
  trigger: string;
  evidence: { count: number; avg_signal: number };
  status: string;
  proposed_diff: string | null;
  created_at: string | null;
}

export default function SkillUpdatesPage() {
  const [proposals, setProposals] = useState<SkillProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProposals();
  }, []);

  async function fetchProposals() {
    try {
      const data = await apiClient.listSkillProposals("hod_review");
      setProposals(data.proposals || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  async function handleDecision(id: number, action: "approved" | "rejected") {
    try {
      await apiClient.decideSkillProposal(id, action);
      setProposals((prev) => prev.filter((p) => p.id !== id));
    } catch (e) {
      console.error("Decision failed:", e);
    }
  }

  if (loading) return <div className="p-8 text-gray-500">Loading skill proposals...</div>;
  if (error) return <div className="p-8 text-red-500">Error: {error}</div>;

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Skill Update Proposals</h1>
      <p className="text-gray-600 mb-4">
        Review AI-proposed changes to agent SKILL.md files based on approval feedback patterns.
      </p>

      {proposals.length === 0 ? (
        <div className="bg-gray-50 rounded-lg p-8 text-center text-gray-500">
          No skill update proposals pending review.
        </div>
      ) : (
        <div className="space-y-6">
          {proposals.map((p) => (
            <div key={p.id} className="border rounded-lg p-6 bg-white shadow-sm">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="font-semibold text-lg">{p.skill_path}</h3>
                  <p className="text-sm text-gray-500">
                    {p.dept_id} / {p.agent_id} ·{" "}
                    {p.created_at
                      ? new Date(p.created_at).toLocaleDateString()
                      : "—"}
                  </p>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                  {p.status}
                </span>
              </div>

              <div className="mb-4">
                <p className="text-sm font-medium text-gray-700 mb-1">Trigger</p>
                <p className="text-sm text-gray-600">{p.trigger}</p>
              </div>

              <div className="mb-4 grid grid-cols-2 gap-4">
                <div className="bg-gray-50 rounded p-3">
                  <p className="text-xs text-gray-500">Interactions</p>
                  <p className="text-lg font-semibold">{p.evidence.count}</p>
                </div>
                <div className="bg-gray-50 rounded p-3">
                  <p className="text-xs text-gray-500">Avg Signal</p>
                  <p className="text-lg font-semibold">{p.evidence.avg_signal?.toFixed(2)}</p>
                </div>
              </div>

              {p.proposed_diff && (
                <div className="mb-4">
                  <p className="text-sm font-medium text-gray-700 mb-1">Proposed Changes</p>
                  <pre className="bg-gray-900 text-green-400 p-4 rounded text-xs overflow-x-auto whitespace-pre-wrap">
                    {p.proposed_diff}
                  </pre>
                </div>
              )}

              <div className="flex gap-3">
                <button
                  onClick={() => handleDecision(p.id, "approved")}
                  className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm font-medium"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleDecision(p.id, "rejected")}
                  className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 text-sm font-medium"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
