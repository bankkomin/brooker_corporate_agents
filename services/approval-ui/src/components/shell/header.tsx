"use client";

import { getDepartment } from "@/lib/departments";
import { Badge } from "@/components/ui/badge";
import { MobileSidebar } from "@/components/shell/app-sidebar";

interface HeaderProps {
  dept: string;
}

export function Header({ dept }: HeaderProps) {
  const department = getDepartment(dept);
  const shortName = department?.shortName ?? dept.toUpperCase();
  const color = department?.color ?? "#64748b";

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
    </header>
  );
}
