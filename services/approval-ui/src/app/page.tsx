"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { hasActiveSession, getSessionUser } from "@/lib/auth";

export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    if (hasActiveSession()) {
      const user = getSessionUser();
      router.replace(`/${user?.dept ?? "cac"}`);
    } else {
      router.replace("/login");
    }
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-muted-foreground">Redirecting...</p>
    </div>
  );
}
