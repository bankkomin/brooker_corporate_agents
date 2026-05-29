"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { BoardEscalationCard } from "@/components/board/board-escalation-card";
import { BoardProposalCard } from "@/components/board/board-proposal-card";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import type { CeoBoardResponse } from "@/types/api";

type ColumnKey = "escalated" | "pending" | "approved" | "rejected";

const COLUMNS: { key: ColumnKey; title: (windowDays: number) => string; accent: string }[] = [
  { key: "escalated", title: () => "Escalated",                accent: "text-red-600 dark:text-red-400" },
  { key: "pending",   title: () => "Pending Approval",         accent: "text-amber-600 dark:text-amber-400" },
  { key: "approved",  title: (d) => `Approved (${d}d)`,        accent: "text-green-600 dark:text-green-400" },
  { key: "rejected",  title: (d) => `Rejected (${d}d)`,        accent: "text-muted-foreground" },
];

// Error codes that mean "your session is bad, send them to /login" — matches
// AuthGuard semantics for the rest of the app.
const SESSION_ERROR_CODES = new Set(["TOKEN_MISSING", "TOKEN_EXPIRED", "TOKEN_INVALID"]);

export default function CeoBoardPage() {
  const router = useRouter();
  const params = useParams<{ dept: string }>();
  const [board, setBoard] = useState<CeoBoardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const resp = await apiClient.getCeoBoard();
      setBoard(resp);
    } catch (err: unknown) {
      const code = (err as { code?: string } | null)?.code;
      if (code && SESSION_ERROR_CODES.has(code)) {
        router.replace("/login");
        return;
      }
      if (code === "CEO_BOARD_FORBIDDEN") {
        setError("Only the CEO role may view this board.");
      } else {
        setError("Failed to load board.");
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [router]);

  // Guard against non-CEO dept paths (e.g. /cac/board). Redirect to /ceo/board
  // so the CEO board is only ever rendered under its own dept chrome.
  useEffect(() => {
    if (params.dept && params.dept !== "ceo") {
      router.replace("/ceo/board");
    }
  }, [params.dept, router]);

  // Initial load + refresh when the tab regains visibility.
  useEffect(() => {
    if (params.dept !== "ceo") return;
    load();
    function onVisible() {
      if (!document.hidden) load();
    }
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [params.dept, load]);

  // Don't render anything while the dept-guard redirect is in flight.
  if (params.dept && params.dept !== "ceo") return null;

  const anyTruncated =
    board != null &&
    (board.truncated.escalated || board.truncated.pending ||
     board.truncated.approved || board.truncated.rejected);

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">CEO Board</h1>
        <div className="flex items-center gap-3">
          {board && (
            <span className="text-xs text-muted-foreground">
              {board.totals.escalated} escalated · {board.totals.pending} pending ·{" "}
              {board.totals.approved} approved · {board.totals.rejected} rejected
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => load(true)}
            disabled={loading || refreshing}
            aria-label="Refresh board"
          >
            <RefreshCw className={`size-4 ${refreshing ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {anyTruncated && board && (
        <div className="rounded-md border border-amber-300 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-700 px-3 py-2 text-xs text-amber-800 dark:text-amber-300">
          One or more columns hit the display cap. Showing the most recent items only.
        </div>
      )}

      {loading && (
        <div className="py-12 text-center text-muted-foreground">Loading board...</div>
      )}

      {error && (
        <div className="py-12 text-center text-red-600 dark:text-red-400">{error}</div>
      )}

      {!loading && !error && board && (
        <div className="grid gap-3 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
          {COLUMNS.map((col) => {
            const items =
              col.key === "escalated"
                ? board.columns.escalated
                : board.columns[col.key];
            const truncated = board.truncated[col.key];
            return (
              <div key={col.key} className="flex flex-col gap-2">
                <div className="flex items-baseline justify-between border-b border-border pb-1">
                  <h2 className={`text-sm font-semibold ${col.accent}`}>
                    {col.title(board.window_days)}
                  </h2>
                  <span className="text-xs text-muted-foreground">
                    {items.length}{truncated ? "+" : ""}
                  </span>
                </div>

                <div className="flex flex-col gap-2 min-h-[40px]">
                  {items.length === 0 && (
                    <p className="text-xs text-muted-foreground py-2">Nothing here.</p>
                  )}
                  {col.key === "escalated" &&
                    board.columns.escalated.map((e) => (
                      <BoardEscalationCard key={e.id} escalation={e} />
                    ))}
                  {col.key !== "escalated" &&
                    board.columns[col.key].map((p) => (
                      <BoardProposalCard key={p.id} proposal={p} />
                    ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
