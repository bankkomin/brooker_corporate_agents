"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken, decodeTokenPayload } from "@/lib/auth";

export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    const token = getToken();
    if (token) {
      const claims = decodeTokenPayload(token);
      if (claims?.dept) {
        router.push(`/${claims.dept}`);
        return;
      }
    }
    // Default department for v1
    router.push("/cac");
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-muted-foreground">Redirecting...</p>
    </div>
  );
}
