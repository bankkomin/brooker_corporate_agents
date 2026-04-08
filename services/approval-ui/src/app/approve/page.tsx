"use client";

import { useEffect, useMemo, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  isTokenExpired,
  decodeTokenPayload,
  setToken,
} from "@/lib/auth";

function ApprovePageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const { error, target } = useMemo(() => {
    const token = searchParams.get("token");

    if (!token) {
      return { error: "No token provided. Please use the link from your email.", target: null };
    }

    if (isTokenExpired(token)) {
      return {
        error: "This link has expired. Please request a new one from your agent.",
        target: null,
      };
    }

    const claims = decodeTokenPayload(token);
    if (!claims || !claims.dept) {
      return { error: "Invalid token. Please use the link from your email.", target: null };
    }

    setToken(token);

    const dest = claims.proposal_id
      ? `/${claims.dept}/proposals/${claims.proposal_id}`
      : `/${claims.dept}/proposals`;

    return { error: null, target: dest };
  }, [searchParams]);

  useEffect(() => {
    if (target) {
      router.push(target);
    }
  }, [target, router]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-4">
        <div className="w-full max-w-md text-center space-y-4">
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
            Brooker Corporate Agent
          </h1>
          <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30 p-6">
            <p className="text-red-700 dark:text-red-400">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-4">
      <div className="w-full max-w-md text-center space-y-4">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Brooker Corporate Agent
        </h1>
        <p className="text-muted-foreground">Verifying your access...</p>
      </div>
    </div>
  );
}

export default function ApprovePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-4">
          <div className="w-full max-w-md text-center space-y-4">
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
              Brooker Corporate Agent
            </h1>
            <p className="text-muted-foreground">Loading...</p>
          </div>
        </div>
      }
    >
      <ApprovePageInner />
    </Suspense>
  );
}
