"use client";

import { AppSidebar, BottomNav } from "@/components/shell/app-sidebar";
import { Header } from "@/components/shell/header";
import { AuthGuard } from "@/components/shell/auth-guard";

interface DepartmentShellProps {
  dept: string;
  children: React.ReactNode;
}

export function DepartmentShell({ dept, children }: DepartmentShellProps) {
  return (
    <AuthGuard>
      <div className="flex h-screen w-full overflow-hidden">
        {/* Desktop: full sidebar */}
        <div className="hidden lg:block">
          <AppSidebar dept={dept} />
        </div>

        {/* Tablet: collapsed sidebar */}
        <div className="hidden md:block lg:hidden">
          <AppSidebar dept={dept} collapsed />
        </div>

        {/* Main content area */}
        <div className="flex min-w-0 flex-1 flex-col">
          <Header dept={dept} />
          <main className="flex-1 overflow-y-auto p-4 pb-20 md:pb-4">
            {children}
          </main>
        </div>

        {/* Mobile: bottom nav */}
        <BottomNav dept={dept} />
      </div>
    </AuthGuard>
  );
}
