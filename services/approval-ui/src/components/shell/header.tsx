"use client";

import { useRouter } from "next/navigation";
import { getDepartment } from "@/lib/departments";
import { getSessionUser, clearSession } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { MobileSidebar } from "@/components/shell/app-sidebar";

interface HeaderProps {
  dept: string;
}

export function Header({ dept }: HeaderProps) {
  const router = useRouter();
  const department = getDepartment(dept);
  const shortName = department?.shortName ?? dept.toUpperCase();
  const color = department?.color ?? "#64748b";
  const user = getSessionUser();

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background px-4">
      {/* Mobile hamburger */}
      <MobileSidebar dept={dept} />

      {/* Title */}
      <div className="flex items-center gap-2">
        <span className="text-base font-semibold">Brooker</span>
        <Badge
          variant="outline"
          className="text-xs font-semibold"
          style={{ borderColor: color, color }}
        >
          {shortName}
        </Badge>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Department description (hidden on mobile) */}
      <span className="hidden text-xs text-muted-foreground lg:inline">
        {department?.description ?? ""}
      </span>

      {/* User info + logout */}
      {user && (
        <div className="flex items-center gap-3 ml-3">
          <div className="hidden sm:flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
              {user.firstName?.[0]}{user.lastName?.[0] || ""}
            </div>
            <div className="text-right">
              <p className="text-xs font-medium leading-none">{user.firstName} {user.lastName}</p>
              <p className="text-[10px] text-muted-foreground capitalize">{user.role?.replace("_", " ")}</p>
            </div>
          </div>
          <button
            onClick={() => { clearSession(); router.push("/login"); }}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-muted"
          >
            Logout
          </button>
        </div>
      )}
    </header>
  );
}
