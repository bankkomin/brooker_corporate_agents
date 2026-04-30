"use client";

import { useEffect, useState } from "react";

interface KnowledgeGap {
  id: number;
  dept_id: string;
  agent_id: string;
  query: string;
  hit_count: number;
  llm_self_report: string | null;
  expected_doc_type: string | null;
  created_at: string;
  resolved_at: string | null;
}

export default function KnowledgeGapsPage() {
  const [gaps, setGaps] = useState<KnowledgeGap[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"created_at" | "dept_id" | "hit_count">("created_at");

  useEffect(() => {
    fetchGaps();
  }, []);

  async function fetchGaps() {
    try {
      const res = await fetch("/api/admin/knowledge-gaps");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setGaps(data.gaps || []);
    } catch (e) {
      console.error("Failed to fetch gaps:", e);
    } finally {
      setLoading(false);
    }
  }

  async function markResolved(id: number) {
    try {
      await fetch(`/api/admin/knowledge-gaps/${id}/resolve`, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      });
      setGaps((prev) =>
        prev.map((g) =>
          g.id === id ? { ...g, resolved_at: new Date().toISOString() } : g
        )
      );
    } catch (e) {
      console.error("Resolve failed:", e);
    }
  }

  const filtered = gaps
    .filter((g) => {
      if (filter === "all") return true;
      if (filter === "unresolved") return !g.resolved_at;
      return g.dept_id === filter;
    })
    .sort((a, b) => {
      if (sortBy === "created_at") return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      if (sortBy === "dept_id") return a.dept_id.localeCompare(b.dept_id);
      return b.hit_count - a.hit_count;
    });

  const depts = [...new Set(gaps.map((g) => g.dept_id))].sort();

  if (loading) return <div className="p-8 text-gray-500">Loading knowledge gaps...</div>;

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-2">Knowledge Gaps</h1>
      <p className="text-gray-600 mb-6">
        Queries where agents had insufficient data. Use this to prioritize document ingestion.
      </p>

      <div className="flex gap-4 mb-6">
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="all">All departments</option>
          <option value="unresolved">Unresolved only</option>
          {depts.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="created_at">Newest first</option>
          <option value="dept_id">Department</option>
          <option value="hit_count">Hit count</option>
        </select>
        <span className="text-sm text-gray-500 self-center">
          {filtered.length} of {gaps.length} gaps shown
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-50 border-b">
              <th className="text-left p-3 font-medium">Department</th>
              <th className="text-left p-3 font-medium">Agent</th>
              <th className="text-left p-3 font-medium">Query</th>
              <th className="text-center p-3 font-medium">Hits</th>
              <th className="text-left p-3 font-medium">Date</th>
              <th className="text-center p-3 font-medium">Status</th>
              <th className="text-center p-3 font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((g) => (
              <tr key={g.id} className="border-b hover:bg-gray-50">
                <td className="p-3">
                  <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-medium">
                    {g.dept_id}
                  </span>
                </td>
                <td className="p-3 text-gray-600">{g.agent_id}</td>
                <td className="p-3 max-w-md truncate" title={g.query}>{g.query}</td>
                <td className="p-3 text-center">
                  <span className={`font-mono ${g.hit_count === 0 ? "text-red-600" : "text-yellow-600"}`}>
                    {g.hit_count}
                  </span>
                </td>
                <td className="p-3 text-gray-500">{new Date(g.created_at).toLocaleDateString()}</td>
                <td className="p-3 text-center">
                  {g.resolved_at ? (
                    <span className="text-green-600 text-xs">Resolved</span>
                  ) : (
                    <span className="text-orange-600 text-xs">Open</span>
                  )}
                </td>
                <td className="p-3 text-center">
                  {!g.resolved_at && (
                    <button
                      onClick={() => markResolved(g.id)}
                      className="text-xs px-2 py-1 border rounded hover:bg-gray-100"
                    >
                      Resolve
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-12 text-gray-400">No knowledge gaps match your filter.</div>
      )}
    </div>
  );
}
