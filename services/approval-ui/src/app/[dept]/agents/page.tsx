"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Bot,
  Zap,
  ShieldCheck,
  TrendingUp,
  Landmark,
  Briefcase,
  BookOpen,
  MessageSquare,
  LayoutGrid,
  GitFork,
  Info,
  AlertTriangle,
  Hammer,
  Scale,
  Gavel,
  PieChart,
  Wrench,
  Users,
  Monitor,
  Crown,
  CreditCard,
  BarChart3,
  FileSearch,
  Building2,
  ClipboardCheck,
  FileText,
  Search,
  UserCheck,
  DollarSign,
  ScrollText,
  Server,
  Lock,
  GitBranch,
  Cog,
  Truck,
  Home,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { getDepartment, getDepartmentIds } from "@/lib/departments";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from "@/components/ui/tooltip";

/* ------------------------------------------------------------------ */
/*  Agent registry — all departments                                   */
/* ------------------------------------------------------------------ */

type AgentStatus = "active" | "staged" | "planned";
type AgentRole = "orchestrator" | "specialist" | "support" | "fallback" | "worker";

interface AgentDef {
  label: string;
  icon: React.ElementType;
  mandate: string;
  status: AgentStatus;
  role: AgentRole;
  skills: string[];
  service: string;
  dept: string;          // which department this agent belongs to
  parent?: string;       // id of supervising agent within the dept
}

/* Key format: globally unique agent id */
const ALL_AGENTS: Record<string, AgentDef> = {
  /* ── CAC ── */
  "cac:cfo": {
    label: "CFO Agent", icon: Briefcase,
    mandate: "Cross-domain synthesizer providing whole-of-firm board-level view. Aggregates inputs from all specialist agents for strategic allocation decisions.",
    status: "active", role: "orchestrator", skills: ["cfo-agent", "escalation-protocol"], service: "cac-orchestrator", dept: "cac",
  },
  "cac:liquidity": {
    label: "Liquidity Agent", icon: TrendingUp,
    mandate: "Reviews liquidity ratios (LCR, NSFR, current/quick ratio) and cash flow projections against regulatory and internal thresholds.",
    status: "active", role: "specialist", skills: ["liquidity-analysis", "covenant-monitoring"], service: "cac-orchestrator", dept: "cac", parent: "cac:cfo",
  },
  "cac:capital": {
    label: "Capital Agent", icon: ShieldCheck,
    mandate: "Reviews capital adequacy (CAR, CET1, RWA, ICAAP), capital buffers, and stress testing results against regulatory and internal thresholds.",
    status: "active", role: "specialist", skills: ["capital-allocation", "covenant-monitoring"], service: "cac-orchestrator", dept: "cac", parent: "cac:cfo",
  },
  "cac:alm": {
    label: "ALM Agent", icon: Zap,
    mandate: "Reviews interest rate risk, duration gap, NII sensitivity, EVE sensitivity, and repricing gap analysis (IRRBB).",
    status: "active", role: "specialist", skills: ["alm-review", "covenant-monitoring"], service: "cac-orchestrator", dept: "cac", parent: "cac:cfo",
  },
  "cac:funding": {
    label: "Funding Agent", icon: Landmark,
    mandate: "Reviews facility utilization, covenant compliance, maturity profiles, rollover risk, and borrowing costs.",
    status: "active", role: "specialist", skills: ["funding-facilities", "covenant-monitoring"], service: "cac-orchestrator", dept: "cac", parent: "cac:cfo",
  },
  "cac:general": {
    label: "General Handler", icon: MessageSquare,
    mandate: "Handles unclassified or general queries using retrieved context. Fallback when intent classification doesn't match a specialist domain.",
    status: "active", role: "fallback", skills: ["rag-retrieval", "citation-format"], service: "cac-orchestrator", dept: "cac", parent: "cac:cfo",
  },
  "cac:escalation": {
    label: "Escalation Agent", icon: AlertTriangle,
    mandate: "Dedicated escalation handler. Routes breach alerts and threshold violations to HODs via email and Slack.",
    status: "active", role: "specialist", skills: ["escalation-protocol"], service: "cac-orchestrator", dept: "cac", parent: "cac:cfo",
  },

  /* ── Risk ── */
  "risk:orchestrator": {
    label: "CRO Agent", icon: Scale,
    mandate: "Synthesizes credit, market, and operational risk into unified risk posture for board reporting. Coordinates risk appetite framework.",
    status: "planned", role: "orchestrator", skills: ["risk-orchestrator", "escalation-protocol"], service: "risk-orchestrator", dept: "risk",
  },
  "risk:credit-risk": {
    label: "Credit Risk Agent", icon: CreditCard,
    mandate: "Assesses PD/LGD/EAD models, expected credit loss (ECL), IFRS 9 staging, NPL ratios, and credit concentration risk.",
    status: "planned", role: "specialist", skills: ["credit-risk"], service: "risk-orchestrator", dept: "risk", parent: "risk:orchestrator",
  },
  "risk:market-risk": {
    label: "Market Risk Agent", icon: BarChart3,
    mandate: "Measures VaR (parametric, historical, Monte Carlo), stressed VaR, FRTB, sensitivity analysis, and backtesting exceptions.",
    status: "planned", role: "specialist", skills: ["market-risk"], service: "risk-orchestrator", dept: "risk", parent: "risk:orchestrator",
  },
  "risk:operational-risk": {
    label: "Op Risk Agent", icon: AlertTriangle,
    mandate: "Monitors RCSA, KRIs, loss data collection, scenario analysis, Basel SMA, business continuity, and cyber risk indicators.",
    status: "planned", role: "specialist", skills: ["operational-risk"], service: "risk-orchestrator", dept: "risk", parent: "risk:orchestrator",
  },

  /* ── Legal ── */
  "legal:orchestrator": {
    label: "CLO Agent", icon: Gavel,
    mandate: "Synthesizes compliance, regulatory, and contract intelligence for legal committee reporting. Coordinates regulatory response.",
    status: "planned", role: "orchestrator", skills: ["legal-orchestrator", "escalation-protocol"], service: "legal-orchestrator", dept: "legal",
  },
  "legal:compliance": {
    label: "Compliance Agent", icon: ClipboardCheck,
    mandate: "Monitors AML/KYC, sanctions screening, regulatory reporting deadlines, compliance breaches, and remediation tracking.",
    status: "planned", role: "specialist", skills: ["compliance"], service: "legal-orchestrator", dept: "legal", parent: "legal:orchestrator",
  },
  "legal:regulatory": {
    label: "Regulatory Agent", icon: FileText,
    mandate: "Monitors regulatory landscape, impact assessments, submissions, examination management, and consent orders.",
    status: "planned", role: "specialist", skills: ["regulatory"], service: "legal-orchestrator", dept: "legal", parent: "legal:orchestrator",
  },
  "legal:contract-review": {
    label: "Contract Review Agent", icon: FileSearch,
    mandate: "Analyzes contracts, extracts key clauses, tracks renewals, monitors SLA compliance and counterparty obligations.",
    status: "planned", role: "specialist", skills: ["contract-review"], service: "legal-orchestrator", dept: "legal", parent: "legal:orchestrator",
  },

  /* ── Investment ── */
  "invest:orchestrator": {
    label: "CIO Agent", icon: PieChart,
    mandate: "Synthesizes portfolio, valuation, and due diligence for investment committee decisions. Coordinates asset allocation strategy.",
    status: "planned", role: "orchestrator", skills: ["ic-orchestrator", "escalation-protocol"], service: "invest-orchestrator", dept: "invest",
  },
  "invest:portfolio": {
    label: "Portfolio Agent", icon: TrendingUp,
    mandate: "Manages asset allocation, benchmark tracking, performance attribution, rebalancing triggers, and tracking error.",
    status: "planned", role: "specialist", skills: ["portfolio"], service: "invest-orchestrator", dept: "invest", parent: "invest:orchestrator",
  },
  "invest:valuation": {
    label: "Valuation Agent", icon: DollarSign,
    mandate: "Handles mark-to-market, fair value hierarchy (Level 1/2/3), impairment testing, NAV calculation, and stale price detection.",
    status: "planned", role: "specialist", skills: ["valuation"], service: "invest-orchestrator", dept: "invest", parent: "invest:orchestrator",
  },
  "invest:due-diligence": {
    label: "Due Diligence Agent", icon: Search,
    mandate: "Performs investment due diligence, ESG scoring, credit quality review, operational DD, and manager selection.",
    status: "planned", role: "specialist", skills: ["due-diligence"], service: "invest-orchestrator", dept: "invest", parent: "invest:orchestrator",
  },

  /* ── Operations ── */
  "ops:orchestrator": {
    label: "COO Agent", icon: Cog,
    mandate: "Synthesizes process, vendor, and facilities intelligence for operations committee. Coordinates efficiency initiatives.",
    status: "planned", role: "orchestrator", skills: ["ops-orchestrator", "escalation-protocol"], service: "ops-orchestrator", dept: "ops",
  },
  "ops:process": {
    label: "Process Agent", icon: Wrench,
    mandate: "Optimizes processes, monitors SLAs, tracks throughput metrics, detects bottlenecks, and assesses automation opportunities.",
    status: "planned", role: "specialist", skills: ["process"], service: "ops-orchestrator", dept: "ops", parent: "ops:orchestrator",
  },
  "ops:vendor": {
    label: "Vendor Agent", icon: Truck,
    mandate: "Manages vendor relationships, SLA compliance, contract performance, cost optimization, and procurement pipeline.",
    status: "planned", role: "specialist", skills: ["vendor"], service: "ops-orchestrator", dept: "ops", parent: "ops:orchestrator",
  },
  "ops:facilities": {
    label: "Facilities Agent", icon: Home,
    mandate: "Manages facilities, space utilization, maintenance scheduling, capex tracking, lease management, and BCP readiness.",
    status: "planned", role: "specialist", skills: ["facilities"], service: "ops-orchestrator", dept: "ops", parent: "ops:orchestrator",
  },

  /* ── HR ── */
  "hr:orchestrator": {
    label: "CHRO Agent", icon: Users,
    mandate: "Synthesizes talent, compensation, and policy intelligence for HR committee. Coordinates workforce planning.",
    status: "planned", role: "orchestrator", skills: ["hr-orchestrator", "escalation-protocol"], service: "hr-orchestrator", dept: "hr",
  },
  "hr:talent": {
    label: "Talent Agent", icon: UserCheck,
    mandate: "Handles talent acquisition, headcount planning, attrition analysis, succession planning, and diversity metrics.",
    status: "planned", role: "specialist", skills: ["talent"], service: "hr-orchestrator", dept: "hr", parent: "hr:orchestrator",
  },
  "hr:compensation": {
    label: "Compensation Agent", icon: DollarSign,
    mandate: "Benchmarks compensation, analyzes pay equity, allocates bonus pools, and models total rewards.",
    status: "planned", role: "specialist", skills: ["compensation"], service: "hr-orchestrator", dept: "hr", parent: "hr:orchestrator",
  },
  "hr:policy": {
    label: "Policy Agent", icon: ScrollText,
    mandate: "Monitors HR policy compliance, employee relations cases, grievance tracking, and training completion rates.",
    status: "planned", role: "specialist", skills: ["policy"], service: "hr-orchestrator", dept: "hr", parent: "hr:orchestrator",
  },

  /* ── IT ── */
  "it:orchestrator": {
    label: "CTO Agent", icon: Monitor,
    mandate: "Synthesizes infrastructure, security, and devops intelligence for IT committee. Coordinates technology strategy.",
    status: "planned", role: "orchestrator", skills: ["it-orchestrator", "escalation-protocol"], service: "it-orchestrator", dept: "it",
  },
  "it:infrastructure": {
    label: "Infrastructure Agent", icon: Server,
    mandate: "Monitors uptime SLAs, capacity planning, incident management, MTTR/MTBF, cloud costs, and disaster recovery.",
    status: "planned", role: "specialist", skills: ["infrastructure"], service: "it-orchestrator", dept: "it", parent: "it:orchestrator",
  },
  "it:security": {
    label: "Security Agent", icon: Lock,
    mandate: "Manages cybersecurity posture, vulnerability management, patch compliance, threat intelligence, and access reviews.",
    status: "planned", role: "specialist", skills: ["security"], service: "it-orchestrator", dept: "it", parent: "it:orchestrator",
  },
  "it:devops": {
    label: "DevOps Agent", icon: GitBranch,
    mandate: "Monitors CI/CD pipeline health, deployment frequency, change failure rate, DORA metrics, and release management.",
    status: "planned", role: "specialist", skills: ["devops"], service: "it-orchestrator", dept: "it", parent: "it:orchestrator",
  },

  /* ── CEO ── */
  "ceo:ceo-agent": {
    label: "CEO Agent", icon: Crown,
    mandate: "Cross-department meta-agent synthesizing inputs from ALL department orchestrators (CFO, CRO, CLO, CIO, COO, CHRO, CTO) for board-level strategic decisions.",
    status: "planned", role: "orchestrator", skills: ["ceo-agent", "escalation-protocol"], service: "paperclip", dept: "ceo",
  },

  /* ── Shared / cross-dept ── */
  "shared:openclaw": {
    label: "OpenClaw", icon: Hammer,
    mandate: "Paperclip worker that writes SKILL.md files to the Obsidian vault via MCP. Scaffolds new agent skill definitions.",
    status: "staged", role: "worker", skills: ["escalation-protocol", "citation-format"], service: "paperclip", dept: "shared",
  },
  "shared:wiki": {
    label: "Wiki Maintenance", icon: BookOpen,
    mandate: "Runs scheduled Obsidian vault health checks — linting, stale content archival, knowledge gap detection, and index rebuilds.",
    status: "active", role: "support", skills: ["wiki-maintenance"], service: "wiki-compiler", dept: "shared",
  },
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function getAgentsForDept(dept: string): [string, AgentDef][] {
  return Object.entries(ALL_AGENTS).filter(
    ([, a]) => a.dept === dept || a.dept === "shared"
  );
}

function getOrchestratorId(dept: string): string | undefined {
  return Object.keys(ALL_AGENTS).find(
    (id) => ALL_AGENTS[id].dept === dept && ALL_AGENTS[id].role === "orchestrator"
  );
}

const STATUS_STYLES: Record<AgentStatus, { bg: string; text: string; label: string }> = {
  active:  { bg: "bg-green-100 dark:bg-green-900/30",  text: "text-green-700 dark:text-green-400",  label: "Active" },
  staged:  { bg: "bg-amber-100 dark:bg-amber-900/30",  text: "text-amber-700 dark:text-amber-400",  label: "Staged" },
  planned: { bg: "bg-gray-100 dark:bg-gray-800",        text: "text-gray-500 dark:text-gray-400",    label: "Planned" },
};

const ROLE_STYLES: Record<AgentRole, { bg: string; text: string }> = {
  orchestrator: { bg: "bg-purple-100 dark:bg-purple-900/30", text: "text-purple-700 dark:text-purple-400" },
  specialist:   { bg: "bg-blue-100 dark:bg-blue-900/30",     text: "text-blue-700 dark:text-blue-400" },
  worker:       { bg: "bg-orange-100 dark:bg-orange-900/30", text: "text-orange-700 dark:text-orange-400" },
  support:      { bg: "bg-teal-100 dark:bg-teal-900/30",     text: "text-teal-700 dark:text-teal-400" },
  fallback:     { bg: "bg-gray-100 dark:bg-gray-800",         text: "text-gray-600 dark:text-gray-400" },
};

/* ------------------------------------------------------------------ */
/*  Org Chart                                                          */
/* ------------------------------------------------------------------ */

function OrgChart({ dept }: { dept: string }) {
  const agents = getAgentsForDept(dept);
  const orchestratorId = getOrchestratorId(dept);
  const orchestrator = orchestratorId ? ALL_AGENTS[orchestratorId] : undefined;
  const children = agents.filter(([, a]) => a.parent === orchestratorId);
  const standalone = agents.filter(([id, a]) => id !== orchestratorId && !a.parent);

  return (
    <div className="space-y-8 overflow-x-auto pb-4">
      {/* Paperclip orchestration shell */}
      <div className="mx-auto w-fit">
        <div className="rounded-lg border-2 border-dashed border-muted-foreground/30 px-6 py-2 text-center">
          <p className="text-xs font-medium text-muted-foreground">Paperclip Orchestration Shell</p>
          <p className="text-[10px] text-muted-foreground">port 3100 &middot; audit + heartbeat</p>
        </div>
      </div>

      <div className="mx-auto h-6 w-px bg-border" />

      {/* Root orchestrator */}
      {orchestrator && orchestratorId && (
        <div className="mx-auto w-fit">
          <OrgNode id={orchestratorId} agent={orchestrator} highlight />
        </div>
      )}

      {/* Children */}
      {children.length > 0 && (
        <div className="mx-auto flex items-start justify-center">
          <div className="relative flex items-start justify-center" style={{ minWidth: children.length * 180 }}>
            <div className="absolute -top-2 left-1/2 h-4 w-px -translate-x-1/2 bg-border" />
            <div
              className="absolute top-2 bg-border"
              style={{
                left: `${100 / (children.length * 2)}%`,
                right: `${100 / (children.length * 2)}%`,
                height: 1,
              }}
            />
            <div className="flex gap-4 pt-6">
              {children.map(([id, agent]) => (
                <div key={id} className="flex flex-col items-center">
                  <div className="h-4 w-px bg-border -mt-4" />
                  <OrgNode id={id} agent={agent} />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Standalone agents (shared services) */}
      {standalone.length > 0 && (
        <div className="space-y-3 pt-4 border-t border-dashed border-border">
          <p className="text-xs font-medium text-muted-foreground text-center">
            Shared Services
          </p>
          <div className="flex justify-center gap-4 flex-wrap">
            {standalone.map(([id, agent]) => (
              <OrgNode key={id} id={id} agent={agent} />
            ))}
          </div>
        </div>
      )}

      {/* Routing label */}
      <div className="mx-auto max-w-md rounded-lg border border-dashed border-muted-foreground/30 bg-muted/30 px-4 py-3 text-center">
        <p className="text-xs text-muted-foreground">
          <strong>Routing:</strong> classify_intent routes each query to one specialist based on intent analysis
        </p>
      </div>
    </div>
  );
}

function OrgNode({ id, agent, highlight }: { id: string; agent: AgentDef; highlight?: boolean }) {
  const Icon = agent.icon;
  const status = STATUS_STYLES[agent.status];
  const role = ROLE_STYLES[agent.role];

  return (
    <div
      className={cn(
        "relative flex flex-col items-center gap-1.5 rounded-lg border bg-card p-3 shadow-sm w-[160px]",
        highlight && "border-primary/50 ring-1 ring-primary/20"
      )}
    >
      <Tooltip>
        <TooltipTrigger
          render={
            <button className="absolute top-1.5 right-1.5 text-muted-foreground hover:text-foreground transition-colors">
              <Info className="size-3.5" />
            </button>
          }
        />
        <TooltipContent side="top" className="max-w-[260px] text-xs leading-relaxed">
          {agent.mandate}
        </TooltipContent>
      </Tooltip>
      <div className={cn("flex size-9 items-center justify-center rounded-md", role.bg, role.text)}>
        <Icon className="size-4" />
      </div>
      <p className="text-xs font-semibold text-center leading-tight">{agent.label}</p>
      <div className="flex gap-1">
        <span className={cn("rounded-full px-1.5 py-px text-[9px] font-medium", status.bg, status.text)}>
          {status.label}
        </span>
        <span className={cn("rounded-full px-1.5 py-px text-[9px] font-medium", role.bg, role.text)}>
          {agent.role}
        </span>
      </div>
      <p className="text-[10px] text-muted-foreground">{agent.service}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Card grid                                                          */
/* ------------------------------------------------------------------ */

function AgentGrid({ dept }: { dept: string }) {
  const agents = getAgentsForDept(dept);

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {agents.map(([id, agent]) => {
        const Icon = agent.icon;
        const status = STATUS_STYLES[agent.status];
        const role = ROLE_STYLES[agent.role];
        const parentAgent = agent.parent ? ALL_AGENTS[agent.parent] : undefined;

        return (
          <div
            key={id}
            className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5 shadow-sm"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className={cn("flex size-10 items-center justify-center rounded-md", role.bg, role.text)}>
                  <Icon className="size-5" />
                </div>
                <div>
                  <h3 className="font-semibold">{agent.label}</h3>
                  <div className="flex gap-1.5 mt-0.5">
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", status.bg, status.text)}>
                      {status.label}
                    </span>
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium capitalize", role.bg, role.text)}>
                      {agent.role}
                    </span>
                  </div>
                </div>
              </div>
              <Tooltip>
                <TooltipTrigger
                  render={
                    <button className="text-muted-foreground hover:text-foreground transition-colors">
                      <Info className="size-4" />
                    </button>
                  }
                />
                <TooltipContent side="top" className="max-w-[300px] text-xs leading-relaxed">
                  {agent.mandate}
                </TooltipContent>
              </Tooltip>
            </div>

            <p className="text-sm leading-relaxed text-muted-foreground">
              {agent.mandate}
            </p>

            <div className="text-xs text-muted-foreground">
              Service: <code className="text-foreground">{agent.service}</code>
              {parentAgent && (
                <> &middot; Reports to: <code className="text-foreground">{parentAgent.label}</code></>
              )}
            </div>

            <div className="mt-auto pt-2 border-t border-border">
              <p className="text-xs font-medium text-muted-foreground mb-1.5">Skills</p>
              <div className="flex flex-wrap gap-1.5">
                {agent.skills.map((skill) => (
                  <span
                    key={skill}
                    className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  All-departments summary                                            */
/* ------------------------------------------------------------------ */

function DeptCard({ deptId, isCurrent }: { deptId: string; isCurrent: boolean }) {
  const [expanded, setExpanded] = React.useState(isCurrent);
  const dept = getDepartment(deptId);
  if (!dept) return null;

  const deptAgents = Object.entries(ALL_AGENTS).filter(([, a]) => a.dept === deptId);

  return (
    <div
      className={cn(
        "rounded-lg border transition-colors",
        isCurrent ? "border-primary bg-primary/5" : "border-border",
      )}
    >
      {/* Header — always visible, clickable */}
      <button
        onClick={() => setExpanded((p) => !p)}
        className="flex w-full items-center justify-between p-4 text-left hover:bg-muted/30 transition-colors rounded-lg"
      >
        <div className="flex items-center gap-3">
          <div
            className="flex size-9 shrink-0 items-center justify-center rounded-md text-xs font-bold text-white"
            style={{ backgroundColor: dept.color }}
          >
            {dept.shortName.slice(0, 2)}
          </div>
          <div>
            <p className="text-sm font-semibold">{dept.name}</p>
            <p className="text-xs text-muted-foreground">
              {deptAgents.length} agents &middot; {dept.description}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {isCurrent && (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
              Current
            </span>
          )}
          {expanded ? (
            <ChevronUp className="size-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="size-4 text-muted-foreground" />
          )}
        </div>
      </button>

      {/* Expanded: full agent list with details */}
      {expanded && (
        <div className="border-t border-border px-5 pb-5 pt-4 space-y-4">
          {deptAgents.length === 0 ? (
            <p className="text-sm text-muted-foreground italic py-3">
              Escalation target only — receives cross-department escalations from all orchestrators.
            </p>
          ) : (
            deptAgents.map(([id, agent]) => {
              const Icon = agent.icon;
              const status = STATUS_STYLES[agent.status];
              const role = ROLE_STYLES[agent.role];

              return (
                <div
                  key={id}
                  className="rounded-lg border border-border bg-card p-4 space-y-3"
                >
                  <div className="flex items-start gap-3">
                    <div className={cn("flex size-10 shrink-0 items-center justify-center rounded-md mt-0.5", role.bg, role.text)}>
                      <Icon className="size-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="text-sm font-semibold">{agent.label}</span>
                        <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", status.bg, status.text)}>
                          {status.label}
                        </span>
                        <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium capitalize", role.bg, role.text)}>
                          {agent.role}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {agent.mandate}
                      </p>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-2 border-t border-border text-xs text-muted-foreground">
                    <span>Service: <code className="text-foreground font-medium">{agent.service}</code></span>
                    {agent.parent && ALL_AGENTS[agent.parent] && (
                      <span>Reports to: <code className="text-foreground font-medium">{ALL_AGENTS[agent.parent].label}</code></span>
                    )}
                  </div>

                  {agent.skills.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {agent.skills.map((s) => (
                        <span
                          key={s}
                          className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

function AllDepartmentsSummary({ currentDept }: { currentDept: string }) {
  const deptIds = getDepartmentIds();
  const totalAgents = Object.keys(ALL_AGENTS).length;

  return (
    <div className="space-y-4 pt-4 border-t border-border">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">All Departments</h2>
        <p className="text-xs text-muted-foreground">
          {totalAgents} agents across {deptIds.length} departments &middot; Click to expand
        </p>
      </div>
      <div className="space-y-3">
        {deptIds.map((deptId) => (
          <DeptCard key={deptId} deptId={deptId} isCurrent={deptId === currentDept} />
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function AgentsPage() {
  const { dept } = useParams<{ dept: string }>();
  const department = getDepartment(dept);
  const [view, setView] = React.useState<"grid" | "org">("org");
  const deptAgents = getAgentsForDept(dept);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Agents</h1>
          <p className="text-muted-foreground">
            {deptAgents.length} AI agents serving{" "}
            {department?.name ?? dept}
          </p>
        </div>
        <div className="flex rounded-lg border border-border bg-muted p-0.5">
          <button
            onClick={() => setView("org")}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              view === "org" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <GitFork className="size-3.5" />
            Org Chart
          </button>
          <button
            onClick={() => setView("grid")}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              view === "grid" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <LayoutGrid className="size-3.5" />
            Cards
          </button>
        </div>
      </div>

      <TooltipProvider>
        {view === "org" ? <OrgChart dept={dept} /> : <AgentGrid dept={dept} />}
      </TooltipProvider>

      <AllDepartmentsSummary currentDept={dept} />
    </div>
  );
}
