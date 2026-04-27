"use client";

import { useEffect, useMemo, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  isTokenExpired,
  decodeTokenPayload,
  setToken,
  setSessionUser,
  derivePermissions,
} from "@/lib/auth";

function ApprovePageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const { error, target } = useMemo(() => {
    const token = searchParams.get("token");

    if (!token) {
      // No token — redirect to login page
      return { error: null, target: "/login" };
    }

    if (isTokenExpired(token)) {
      return {
        error: "This link has expired. Please request a new one or sign in directly.",
        target: null,
      };
    }

    const claims = decodeTokenPayload(token);
    if (!claims) {
      return { error: "Invalid token. Please sign in directly.", target: null };
    }

    // Store the token for API calls
    setToken(token);

    // Build session user from token claims
    const dept = claims.dept ?? "cac";
    setSessionUser({
      id: claims.sub,
      email: claims.email ?? "",
      firstName: claims.email?.split("@")[0] ?? "User",
      lastName: "",
      role: claims.role,
      permissions: claims.permissions?.length ? claims.permissions : derivePermissions(claims.role),
      dept,
    });

    const dest = claims.proposal_id
      ? `/${dept}/proposals/${claims.proposal_id}`
      : `/${dept}`;

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
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-b from-blue-500 to-blue-700 shadow-lg mx-auto">
            <svg className="w-8 h-8 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 12l2 2 4-4" />
              <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
            Brooker Corporate Agent
          </h1>
          <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30 p-4">
            <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
          </div>
          <a
            href="/login"
            className="inline-block rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
          >
            Sign In
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-4">
      <div className="w-full max-w-md text-center space-y-4">
        <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
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
            <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
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
