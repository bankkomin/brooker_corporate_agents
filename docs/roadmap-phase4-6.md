# Corporate AI Agents — Phase 4, 5, 6 Roadmap

**Date:** 2026-04-29
**Prereqs:** Phase 1 (CAC live), Phase 2 (framework + departments), Phase 3 (scaling + second Spark)
**Informed by:** `reality-check-2026-04-29.md` — builds only on what works, not on overclaimed features

---

## Current State (end of Phase 3)

Per PRD §15:
- **Phase 1:** CAC Committee live (Stages 1-9) — RAG Q&A, staging proposals, approval gate
- **Phase 2:** Framework + 11 departments (Stage 10-19) — templates, configs, per-dept rollout
- **Phase 3:** Second DGX Spark, all departments live, auto-sync for low-risk categories

What we learned from Phase 1-3:
- Core RAG Q&A works for simple lookups (~60-70% reliable)
- Staging pipeline is solid — data safety architecture proven
- Self-improvement loop produces noise — daily logs are useful, LLM reflection is not
- Confidence scoring is uncalibrated — not trustworthy for automation
- 8 read-only departments don't need full LangGraph pipelines

---

## Phase 4 — Quality & Trust (8-12 weeks)

**Theme:** Make the existing system trustworthy before adding features.
**Goal:** Users trust the system enough to rely on it daily, not just experiment with it.

### 4.1 Evaluation Framework

The single most important missing piece. You cannot improve what you cannot measure.

- [ ] **Golden answer dataset** — 100 questions per department with verified correct answers, sourced from HODs
  - 50 simple lookups ("What is the LCR?")
  - 30 analytical ("Compare Q2 vs Q3 capital adequacy")
  - 20 edge cases ("What happens if NSFR breaches 100%?")
- [ ] **Automated eval pipeline** — runs nightly against the golden set, tracks accuracy/citation quality/latency over time
- [ ] **Accuracy dashboard** — visible to team, shows trend lines per department per question type
- [ ] **Regression gate** — no deployment if accuracy drops >5% on the golden set

### 4.2 Citation Grounding

Fix the ~20-30% wrong citation rate.

- [ ] **Post-generation citation verification** — after the LLM generates `[N]` references, verify each cited claim actually appears in source `[N]`
- [ ] **Extractive citation fallback** — when grounding fails, replace with the exact text span from the source
- [ ] **Citation confidence indicator** — show users "verified" vs "approximate" citation badges
- [ ] **Track citation accuracy** — log grounding pass/fail rates per department

### 4.3 Calibrated Confidence

Replace LLM self-reported confidence with measurable heuristics.

- [ ] **Retrieval-based confidence** — compute from: number of chunks retrieved, top-chunk similarity score, whether extracted value appears verbatim in source
- [ ] **Historical calibration** — track actual approval rates per confidence bucket, adjust thresholds quarterly
- [ ] **Confidence disclaimer** — show users "Based on 3 matching documents" instead of "Confidence: 91%"
- [ ] **Threshold tuning** — use 4 weeks of approval data to set per-department staging thresholds empirically

### 4.4 Observability

You have 16+ services and zero monitoring.

- [ ] **Prometheus metrics** — request latency, error rate, queue depth per service
- [ ] **Grafana dashboards** — system health, LLM latency, RAG hit rates, approval rates
- [ ] **OpenTelemetry tracing** — trace a query from Slack through all services to response
- [ ] **Alerting** — PagerDuty/Slack alerts for: service down, p95 > 60s, error rate > 5%

### 4.5 Chunking Strategy for Tables

Fix the shredded Excel table problem.

- [ ] **Table-aware chunking** — detect table structures in documents, keep rows together
- [ ] **Excel-specific indexing** — index ALCO Tracker tabs as structured data, not text chunks
- [ ] **Hybrid retrieval** — text search for narrative questions, structured lookup for cell-value questions

### 4.6 Consolidate Read-Only Departments

Cut 8 containers down to 1.

- [ ] **Single read-only orchestrator** — one service that serves all read-only departments with config-driven routing (which collections, which SKILL.md, which Slack channel)
- [ ] **Remove per-dept LangGraph overhead** — replace 10-node pipeline with 5-step flow: embed → search → format → synthesise → log
- [ ] **Keep write-capable orchestrators** separate (CAC, Finance, CIO, VCC) — they need the full staging pipeline

**Phase 4 success metric:** Accuracy on golden set reaches 80%+ for simple lookups, 60%+ for analytical. Citation grounding rate above 85%. System uptime 99.5%+.

---

## Phase 5 — Intelligence & Integration (8-12 weeks)

**Theme:** Make the system smarter and connect it to real workflows.
**Prereq:** Phase 4 metrics are solid. Users trust the system.

### 5.1 Chain-of-Thought for Complex Queries

The biggest quality improvement possible with the current LLM.

- [ ] **Multi-step reasoning prompt** — for analytical questions, force the LLM to show its work: "Step 1: Find the current LCR. Step 2: Find the covenant threshold. Step 3: Calculate headroom."
- [ ] **Tool-use integration** — let the LLM call a calculator tool for arithmetic instead of doing math in-context (LLMs are bad at math)
- [ ] **Multi-document synthesis** — when a question requires data from multiple sources, retrieve from each explicitly and present side-by-side to the LLM
- [ ] **"I don't know" training** — tune prompts so the agent says "I don't have enough data to answer this" instead of hallucinating

### 5.2 Practical Memory (Replace Reflection Engine)

Replace the noisy LLM reflection with human-curated + rule-based memory.

- [ ] **Human-authored memory** — HODs and analysts write memory.md entries directly via a simple UI (not LLM-generated)
- [ ] **Rule-based pattern detection** — replace the LLM reflection with deterministic rules:
  - If same cell edited by HOD 3+ times in same direction → suggest adjusting the agent's extraction logic
  - If same question asked 5+ times with no good answer → flag for document ingestion
  - If a department's approval rate drops below 50% for 2+ weeks → alert the admin
- [ ] **Memory pruning** — auto-archive entries older than 90 days unless pinned by a human
- [ ] **Knowledge gap actionability** — connect the knowledge_gaps table to the document ingestion pipeline so gaps automatically become "ingest this document" tasks

### 5.3 Email Ingestion

The #1 user request that Phase 1-3 didn't address.

- [ ] **Email-to-agent pipeline** — forward committee emails to a monitored inbox, auto-ingest attachments (PDFs, Excel) into the RAG pipeline
- [ ] **Email thread context** — when a Slack question references "the email Jane sent yesterday," the agent can search the email corpus
- [ ] **Meeting minutes auto-ingest** — when someone uploads meeting minutes, auto-extract action items and key decisions

### 5.4 SharePoint / OneDrive Integration

Replace the sync-mirror stub with real data sources.

- [ ] **SharePoint connector** — Microsoft Graph API, reads from designated folders per department
- [ ] **OneDrive connector** — for documents shared via Teams/OneDrive links
- [ ] **Incremental sync** — only fetch changed files, not full folder scans
- [ ] **Version tracking** — detect when a document is updated, re-ingest only the changed version

### 5.5 Structured Report Generation

Move beyond Q&A into producing outputs.

- [ ] **Weekly committee brief** — auto-generate a 1-page summary of: key metrics, changes since last week, pending proposals, knowledge gaps
- [ ] **Pre-meeting prep** — before a scheduled ALCO meeting, generate a briefing doc with current positions, recent changes, and outstanding items
- [ ] **Export to Excel** — let users request data in spreadsheet format, not just text answers

**Phase 5 success metric:** Complex query accuracy reaches 50%+. Memory entries are human-curated, not LLM-generated. SharePoint integration live for at least CAC and Finance. Weekly brief adopted by at least 1 committee.

---

## Phase 6 — Automation & Cross-System (8-12 weeks)

**Theme:** Earned automation — automate only what has proven accurate enough.
**Prereq:** Phase 5 metrics show the system is reliably accurate for specific task types.

### 6.1 Auto-Approve for Low-Risk Updates

The original Phase 3 PRD goal, but now backed by data.

- [ ] **Define "low-risk" empirically** — use 6+ months of approval data to identify proposal categories that are approved >95% of the time without edits
- [ ] **Auto-approve pipeline** — for qualifying proposals only: skip HOD review, write directly to staging → sync-back
- [ ] **Auto-approve audit** — every auto-approved change logged with full provenance, weekly HOD review of auto-approved batch
- [ ] **Kill switch** — any HOD can disable auto-approve for their department instantly
- [ ] **Gradual rollout** — start with 1 cell type in 1 department, expand over 4 weeks

### 6.2 Cross-Department Intelligence

Connect insights across departments (the real value of 11 departments).

- [ ] **Cross-department query routing** — "What is our total exposure to [company X]?" routes to CAC + CIO + VCC simultaneously, synthesizes a unified answer
- [ ] **Conflict detection** — if Finance reports one NAV and CIO reports a different one, flag the discrepancy automatically
- [ ] **Dependency tracking** — when a Legal opinion affects an IC investment decision, the system connects the dots
- [ ] **CEO dashboard** — single view of all department statuses, key metrics, pending items

### 6.3 Venture Monitor Integration

Connect the two systems — corporate agents + VC monitoring.

- [ ] **Fund data in corporate context** — when CAC discusses portfolio allocation, pull relevant fund performance data from venture-monitor
- [ ] **Signal forwarding** — high-severity venture-monitor signals (fund NAV drop, GP issue) auto-forwarded to relevant corporate department channels
- [ ] **Unified document search** — search across both corporate documents and LP reports from a single query

### 6.4 Proactive Agents (Earned, Not Premature)

Only now, after 6+ months of proven accuracy, enable proactive behavior.

- [ ] **Implement real context gathering** — replace heartbeat stubs with actual SharePoint + Slack API integration
- [ ] **Conservative proactive mode** — agent posts to a private "draft" channel first, not directly to the committee channel. A human promotes useful drafts.
- [ ] **Proactive accuracy tracking** — measure what % of proactive messages are useful (user engagement, not ignored)
- [ ] **Gradual escalation** — start with weekly summaries (low risk), graduate to daily alerts (medium risk), then real-time proactive (high risk) only if accuracy >80%

### 6.5 Natural Language Analytics

Let users query data across all systems.

- [ ] **NLQ engine** — "Show me all departments where approval rate dropped last month" → SQL query → formatted answer
- [ ] **Trend analysis** — "How has our LCR trended over the last 6 months?" → time-series chart from historical data
- [ ] **What-if scenarios** — "What happens to our capital ratio if we approve the proposed new facility?" → calculation with assumptions stated

### 6.6 Compliance & Audit

For regulatory readiness.

- [ ] **Full audit trail** — every question, every answer, every proposal, every approval, searchable and exportable
- [ ] **Compliance reports** — auto-generate quarterly compliance summaries from the audit trail
- [ ] **Data retention policies** — auto-archive data older than regulatory requirements, with secure deletion options
- [ ] **Access audit** — who accessed what data when, exportable for regulators

**Phase 6 success metric:** Auto-approve running for at least 2 cell types with >95% accuracy. Cross-department queries working. Venture-monitor integration live. At least 1 proactive agent mode in production with >70% usefulness rate.

---

## Timeline Summary

| Phase | Duration | Key Deliverable | Prereq |
|-------|----------|-----------------|--------|
| **4: Quality & Trust** | 8-12 weeks | Eval framework, citation grounding, observability, consolidated read-only service | Phase 3 complete, real users |
| **5: Intelligence & Integration** | 8-12 weeks | Chain-of-thought, human-curated memory, email/SharePoint ingestion, structured reports | Phase 4 metrics met |
| **6: Automation & Cross-System** | 8-12 weeks | Auto-approve (earned), cross-dept intelligence, venture-monitor integration, proactive agents (real) | Phase 5 metrics met |

**Total estimated timeline:** 6-9 months after Phase 3 completes.

---

## Principles Behind This Roadmap

1. **Measure before you build.** Phase 4 is entirely about creating the ability to measure quality. Without it, everything else is guessing.

2. **Earn automation gradually.** Auto-approve only after 6+ months of data proving specific proposal types are >95% accurate. Not before.

3. **Human-curated over LLM-generated.** Replace noisy reflection engine with human-authored memory + deterministic rules. Humans understand the domain better than the LLM.

4. **Connect before you expand.** Cross-department intelligence and venture-monitor integration create more value than adding more features to individual departments.

5. **Proactive is a privilege, not a feature.** The system earns the right to be proactive by proving it can be accurate when asked. Not before.
