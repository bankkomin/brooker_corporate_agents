"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  FileText,
  AlertTriangle,
  BarChart3,
  Activity,
  Bot,
  Database,
  LayoutDashboard,
  Menu,
  Sparkles,
  SearchX,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { getDepartment } from "@/lib/departments";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from "@/components/ui/tooltip";

const WIDGET_NAV: Record<
  string,
  { label: string; icon: React.ElementType; segment: string }
> = {
  board: { label: "Board", icon: LayoutDashboard, segment: "board" },
  proposals: { label: "Proposals", icon: FileText, segment: "proposals" },
  escalations: {
    label: "Escalations",
    icon: AlertTriangle,
    segment: "escalations",
  },
  analytics: { label: "Analytics", icon: BarChart3, segment: "analytics" },
  "agent-activity": {
    label: "Agent Activity",
    icon: Activity,
    segment: "activity",
  },
  agents: { label: "Agents", icon: Bot, segment: "agents" },
  data: { label: "Data", icon: Database, segment: "data" },
};

interface AppSidebarProps {
  dept: string;
  collapsed?: boolean;
}

function SidebarNav({
  dept,
  collapsed,
}: {
  dept: string;
  collapsed: boolean;
}) {
  const pathname = usePathname();
  const department = getDepartment(dept);
  const widgets = department?.dashboardWidgets ?? ["proposals"];

  const navItems = widgets
    .map((w) => WIDGET_NAV[w])
    .filter(Boolean);

  return (
    <TooltipProvider>
      <nav className="flex flex-col gap-1 p-2">
        {navItems.map((item) => {
          const href = `/${dept}/${item.segment}`;
          const isActive = pathname.startsWith(href);
          const Icon = item.icon;

          const link = (
            <Link
              key={item.segment}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                isActive &&
                  "bg-sidebar-accent text-sidebar-accent-foreground font-semibold",
                collapsed && "justify-center px-2"
              )}
            >
              <Icon className="size-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );

          if (collapsed) {
            return (
              <Tooltip key={item.segment}>
                <TooltipTrigger render={link} />
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            );
          }

          return link;
        })}
      </nav>
    </TooltipProvider>
  );
}

const SYSTEM_NAV = [
  { label: "Skill Updates", icon: Sparkles, href: "/skill-updates" },
  { label: "Knowledge Gaps", icon: SearchX, href: "/admin/knowledge-gaps" },
];

function SystemNav({ collapsed }: { collapsed: boolean }) {
  const pathname = usePathname();

  return (
    <TooltipProvider>
      <div className="mt-auto border-t border-sidebar-border">
        {!collapsed && (
          <p className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/50">
            System
          </p>
        )}
        <nav className="flex flex-col gap-1 p-2">
          {SYSTEM_NAV.map((item) => {
            const isActive = pathname.startsWith(item.href);
            const Icon = item.icon;

            const link = (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                  isActive &&
                    "bg-sidebar-accent text-sidebar-accent-foreground font-semibold",
                  collapsed && "justify-center px-2"
                )}
              >
                <Icon className="size-4 shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );

            if (collapsed) {
              return (
                <Tooltip key={item.href}>
                  <TooltipTrigger render={link} />
                  <TooltipContent side="right">{item.label}</TooltipContent>
                </Tooltip>
              );
            }

            return link;
          })}
        </nav>
      </div>
    </TooltipProvider>
  );
}

function SidebarBrand({
  dept,
  collapsed,
}: {
  dept: string;
  collapsed: boolean;
}) {
  const department = getDepartment(dept);
  const name = department?.shortName ?? dept.toUpperCase();
  const color = department?.color ?? "#64748b";

  return (
    <div className="flex items-center gap-2 border-b border-sidebar-border px-4 py-3">
      <div
        className="flex size-8 shrink-0 items-center justify-center rounded-md text-xs font-bold text-white"
        style={{ backgroundColor: color }}
      >
        {name.slice(0, 2)}
      </div>
      {!collapsed && (
        <span className="truncate text-sm font-semibold text-sidebar-foreground">
          {department?.name ?? dept}
        </span>
      )}
    </div>
  );
}

/** Full sidebar for desktop / tablet */
export function AppSidebar({ dept, collapsed = false }: AppSidebarProps) {
  return (
    <aside
      data-testid="app-sidebar"
      className={cn(
        "hidden h-full shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex",
        collapsed ? "w-16" : "w-60"
      )}
    >
      <SidebarBrand dept={dept} collapsed={collapsed} />
      <SidebarNav dept={dept} collapsed={collapsed} />
      <SystemNav collapsed={collapsed} />
    </aside>
  );
}

/** Mobile sheet drawer triggered from header */
export function MobileSidebar({ dept }: { dept: string }) {
  const [open, setOpen] = React.useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={
          <Button variant="ghost" size="icon" className="md:hidden">
            <Menu className="size-5" />
            <span className="sr-only">Open menu</span>
          </Button>
        }
      />
      <SheetContent side="left" className="w-72 p-0">
        <SheetHeader className="border-b px-4 py-3">
          <SheetTitle>Navigation</SheetTitle>
        </SheetHeader>
        <SidebarBrand dept={dept} collapsed={false} />
        {/* Close sheet on nav click */}
        <div onClick={() => setOpen(false)}>
          <SidebarNav dept={dept} collapsed={false} />
          <SystemNav collapsed={false} />
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** Bottom nav bar for mobile */
export function BottomNav({ dept }: { dept: string }) {
  const pathname = usePathname();
  const department = getDepartment(dept);
  const widgets = department?.dashboardWidgets ?? ["proposals"];

  const navItems = widgets
    .map((w) => WIDGET_NAV[w])
    .filter(Boolean)
    .slice(0, 4); // max 4 items in bottom nav

  return (
    <nav
      data-testid="bottom-nav"
      className="fixed inset-x-0 bottom-0 z-40 flex border-t border-border bg-background md:hidden"
    >
      {navItems.map((item) => {
        const href = `/${dept}/${item.segment}`;
        const isActive = pathname.startsWith(href);
        const Icon = item.icon;

        return (
          <Link
            key={item.segment}
            href={href}
            className={cn(
              "flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] font-medium transition-colors",
              isActive
                ? "text-primary"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="size-5" />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
