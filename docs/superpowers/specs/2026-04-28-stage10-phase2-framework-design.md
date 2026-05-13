# Stage 10 — Phase 2 Department Framework Design

**Date:** 2026-04-28
**Authors:** drafted with Claude (Opus 4.7) via `superpowers:brainstorming`
**Status:** draft — pending spec review + user approval
**Stage:** 10 (framework) ; downstream Stages 11-19 implement individual departments
**Pattern reference:** Stage 8 (HR) is the proof-of-concept this framework generalises
**Related specs:** Stages 4, 5, 7, 9 design docs in `docs/superpowers/specs/`

---

## Preamble — why this exists

Phase 1 shipped two live departments: **CAC Committee** (Stages 4-7) and **HR Department** (Stage 8). Phase 2 expands the system to the full corporate org chart — **9 additional departments** under a CEO Agent root: Finance, IB, IC Committee, CIO Office, Legal, Risk Committee, VCC, Communications (IR/PR), IT.

Two YouTube patterns are folded into this framework so agents don't just answer questions, they accumulate a **second brain** (Cole Medin) and **self-improve** from human feedback (Luuk Alleman):

- **Persistent memory triad** per agent (`soul.md` / `user.md` / `memory.md`) loaded at every interaction
- **Daily logs** capturing every Slack interaction
- **Reflection engine** nightly cron promotes raw logs → structured memory
- **Self-improvement actuator** turns HOD approve/edit/reject signals into SKILL.md update proposals (HOD-gated)
- **Heartbeat** (opt-in) for proactive agent behaviour

This spec is the **framework** itself — Stage 10. It produces templates, shared services, schema migrations, and skeleton spec+plan files for all 9 downstream stages. Each downstream stage then becomes a small, mechanical fill-in-the-blanks exercise.

---

## Table of contents

1. [Architecture Overview](#1-architecture-overview)
2. [File Layout & Project Structure Update](#2-file-layout--project-structure-update)
3. [Document Inventory & Cross-Dept Access Matrix](#3-document-inventory--cross-dept-access-matrix)
4. [Agent Topology + Self-Improvement Loop](#4-agent-topology--self-improvement-loop)
5. [Department Onboarding Checklist (12 steps)](#5-department-onboarding-checklist-12-steps)
6. [Per-Dept Spec Template](#6-per-dept-spec-template)
7. [Implementation Roadmap (Stages 10-19) + Deliverables](#7-implementation-roadmap-stages-10-19--deliverables)
8. [Testing Strategy](#8-testing-strategy)
9. [Risks & Mitigations](#9-risks--mitigations)
10. [Decisions Log](#10-decisions-log)
11. [References](#11-references)

---

## 1. Architecture Overview

The framework is the **Phase-2 department-onboarding pattern**. It scales the system from 2 live departments (CAC + HR) to 11 with predictable effort per dept. It has three layers stacked on what already exists.

### 1.1 Three layers

**1. Catalog layer (config-as-data)**

- `config/departments.json` — extended with `documents[]`, `capabilityTier`, `crossReadAccess[]`, `agentTopology`, `heartbeat{}` per dept entry
- `config/document_inventory.json` — new file. One row per corporate document: `id`, `title`, `ownerDept`, `vaultPath`, `qdrantCollection`, `tier`, `ingestSource`, `frequency`, `crossReadAccess[]`

**2. Template layer (code-as-scaffold)**

- `services/_template-orchestrator/` — minimal LangGraph dept-orchestrator skeleton (FastAPI + the standard graph). Copy-rename to bootstrap a new dept service.
- `skills/_template/` — orchestrator + 3 specialist SKILL.md placeholders with required frontmatter and section headers.

**3. Spec layer (docs)**

- This framework spec (single doc, intended ~30 pages)
- 9 thin per-dept specs (~1 page each), pre-skeletoned in Stage 10, filled per stage

### 1.2 Lifecycle (per dept, downstream stages)

12-step onboarding checklist (full detail in §5): **audit catalog row → write thin spec → scaffold from template → fill skills → wire LangGraph → migrations → tests → docker-compose entry → Slack channel → vault folder → smoke test → flip `live: true`**.

### 1.3 Reuse of existing infrastructure (no changes needed)

| Service | Already supports | Used by Phase 2 |
|---|---|---|
| **Paperclip** (Stage 7) | Multi-dept registry & ticket routing | New dept rows seeded per stage |
| **approval-ui** (Stage 6) | Dept-scoped JWT/RBAC | Adding dept to departments.json auto-creates dashboard |
| **wiki-compiler** (Stage 9) | Routes by dept | New dept = new vault folder + Qdrant collection per catalog |
| **BaseAgent + SkillsLoader** (Stage 8) | Cross-department reuse via `services/shared/` | New orchestrators import & subclass |
| **VaultWatcher** (Stage 9) | Config-driven path → collection mapping | New dept paths added to `obsidian_watch.json` |
| **OpenClaw** (Stage 8) | Worker dispatch via Paperclip | Drafts SKILL.md updates from skill_proposals |

### 1.4 New infrastructure (Stage 10 builds)

| Component | Type | Purpose |
|---|---|---|
| `services/_template-orchestrator/` | Code skeleton | Step 3 of onboarding checklist |
| `skills/_template/` | Skill skeleton | Step 4 |
| `services/reflection-engine/` (port 3008) | New service | Nightly cron promoting daily logs → memory.md; triggers skill_proposals |
| `services/heartbeat/` (port 3009) | New service | Opt-in proactive layer; default disabled per dept |
| `agent_knowledge_gaps` | Postgres table | Logs retrieval misses for ingest prioritisation |
| `agent_skill_proposals` | Postgres table | Self-improvement actuator queue |
| `reflection_runs` | Postgres table | Audit log for nightly reflection |
| `agent_performance` | Postgres view | Computed signal_strength from approval_decisions |
| `config/document_inventory.json` | Config file | Doc catalog (~45 rows) |
| `scripts/validate_config.py`, `validate_skills.py` | Validation scripts | CI gates |

### 1.5 Out of scope of the framework spec

- Any one department's specific agent prompts, escalation thresholds, or Excel cell mappings (those belong in each per-dept spec)
- Voyager-style novel-skill invention (deferred)
- Cross-agent learning (skill X learning from skill Y in another dept) (deferred)
- True RL training loop (we evolve prompts + examples, not weights)

---

## 2. File Layout & Project Structure Update

Concrete changes against the current repo. Three buckets: **renames**, **deletes**, **creates**.

### 2.1 Skills folder reconciliation

| Current path | Action | Target path | Reason |
|---|---|---|---|
| `skills/invest/` | **rename** | `skills/ic/` | Match `dept_id: "ic-committee"` convention used by `cac/`, `hr/` |
| `skills/risk/` | keep | `skills/risk/` | Already aligned |
| `skills/it/` | keep | `skills/it/` | Already aligned |
| `skills/legal/` | keep | `skills/legal/` | Already aligned |
| `skills/ops/` | **delete** | — | Not in org chart |
| — | **create** | `skills/finance/` | New — Finance dept |
| — | **create** | `skills/ib/` | New — Investment Banking |
| — | **create** | `skills/cio/` | New — CIO Office |
| — | **create** | `skills/vcc/` | New — VCC dept |
| — | **create** | `skills/comms/` | New — Communications (IR/PR) |
| — | **create** | `skills/_template/` | New — skill scaffold (orchestrator.md + 3 specialist.md placeholders) |

After this pass, `skills/` has exactly 12 dirs: 11 dept-aligned (`cac`, `hr`, `finance`, `ib`, `ic`, `cio`, `vcc`, `comms`, `legal`, `risk`, `it`) + `shared` + `_template`.

The `shared/cfo-agent.md` already exists — moves to `skills/finance/cfo-agent.md` with a thin re-export stub kept in `shared/` for one stage as backwards compatibility.

### 2.2 Services folder

The framework spec creates **three** new directories:

| Action | Path | Notes |
|---|---|---|
| **create** | `services/_template-orchestrator/` | Copy of `hr-orchestrator/` minus dept-specific code; placeholders for `{DEPT_ID}`, `{AGENTS}`, `{COLLECTIONS}`, `{PORT}` |
| **create** | `services/reflection-engine/` | New service, port 3008. APScheduler nightly per dept. |
| **create** | `services/heartbeat/` | New service, port 3009. Code in place, default disabled per dept. |

Per-dept orchestrators (`finance-orchestrator/`, etc.) are created later, one per stage, by copying `_template-orchestrator/`.

### 2.3 Config

| Action | Path | Notes |
|---|---|---|
| **extend** | `config/departments.json` | Add `documents[]`, `capabilityTier`, `crossReadAccess[]`, `agentTopology`, `heartbeat{}` per dept; add 9 new dept entries (initially `live: false`) |
| **create** | `config/document_inventory.json` | New catalog — every doc in §3 mapped to owner dept + vaultPath + qdrantCollection + tier |
| **extend** | `config/departments.schema.json` | JSON Schema for new fields |
| **create** | `config/document_inventory.schema.json` | JSON Schema for the new file |
| **extend** | `config/obsidian_watch.json` | Add path mappings for the 9 new dept vault folders |

### 2.4 Obsidian vault

| Action | Path |
|---|---|
| **create** | `obsidian-vault/finance/`, `ib/`, `cio/`, `vcc/`, `comms/`, `ic/`, `it/`, `legal/`, `risk/` (each with `concepts/`, `decisions/`, `meeting-notes/`, `entities/`, `trends/`, `daily-logs/`, `_memory/{agent_id}/` subdirs per Stage 9 pattern) |

### 2.5 Qdrant collections (created at runtime by rag-ingestion on first dept boot)

Pattern: `{dept_id}_docs`, `{dept_id}_chat`, `{dept_id}_knowledge`. The `shared_policies` collection is already pan-dept and stays as-is.

New collections at full rollout: 27 (9 depts × 3) + existing.

### 2.6 What this section does NOT do

- It does **not** create the 9 new orchestrator services (per-dept stages do that)
- It does **not** populate skill content beyond placeholders
- It does **not** seed the new dept rows in `paperclip_departments` (per-dept stage migration does that)

This is the structural ground that lets each per-dept stage land mechanically.

---

## 3. Document Inventory & Cross-Dept Access Matrix

### 3.1 Document classification (4 tiers)

Every doc gets one tier; tier drives how the wiki-compiler ingests it and how agents weight it during retrieval.

| Tier | Definition | Examples | Agent behaviour |
|---|---|---|---|
| **policy** | Governing rules; rarely changes | HR policy, AML policy, Investment policy, Risk policy, Branding policy, Remuneration policy, IT policies | Pinned in retrieval; cited when agent recommends an action |
| **report** | Periodic, numeric, point-in-time | Annual report, Networth, BG/Coins weekly, Leadership monthly, MD&A, NAV reports, Custodian docs, Financial statements, Structured loan report | Time-decayed in retrieval; latest version preferred |
| **tracker** | Live operational data; agents may propose edits | ALCO Tracker, Networth tracker, NAV tracker, VCC client list | Cell-level RAG; staging proposals possible |
| **narrative** | Free-form context | Board minutes, IC minutes, deal docs, term sheets, due diligence, presentations, memos, press releases, earnings calls, contracts, legal opinions, PPM, SOPs, corporate info, strategic retreat plan | Standard RAG; no staging |

### 3.2 `document_inventory.json` schema

```json
{
  "id": "doc_finance_annual_report",
  "title": "Annual report",
  "ownerDept": "finance",
  "tier": "report",
  "vaultPath": "obsidian-vault/finance/entities/annual-report.md",
  "qdrantCollection": "finance_docs",
  "ingestSource": "sharepoint://Finance/Annual",
  "frequency": "annual",
  "crossReadAccess": ["ceo", "cac", "risk", "legal"]
}
```

Every corporate document gets a row. Total inventory: ~53 rows spanning 11 depts (per the §3.3 summary table; full enumeration in `config/document_inventory.json` after Stage 10).

### 3.3 Inventory summary

| Dept | Policies | Reports | Trackers | Narrative | Total |
|---|---|---|---|---|---|
| CEO | 1 (Strategic Retreat) | 2 (Leadership monthly, MD&A) | — | 4 (Board minutes, BG/BICL/Arun) | 7 |
| Finance | — | 5 | — | — | 5 |
| IB | — | 1 (Structured loan) | — | 6 (deal docs, pitch books, term sheets, memos, syndication, league tables) | 7 |
| HR | 2 (HR, Renum) | — | — | 1 (SOPs) | 3 |
| IC | 1 (Investment policy) | — | — | 2 (IC minutes, investment memos) | 3 |
| CAC | — | — | 1 (ALCO Tracker) | 3 (Capital plan, Funding facilities, Liquidity covenant) | 4 |
| CIO | — | 2 (NAV, Custodian) | — | 1 (PPM) | 3 |
| Legal | 1 (AML — co-owned with Risk) | — | — | 2 (Legal opinions, Contract templates) | 3 |
| Risk | 1 (Risk policy) | — | — | — *(co-owns AML)* | 1 |
| VCC | — | 2 (NAV, Subscriptions) | 1 (Client list) | 5 (Presentations, Contracts, DD, Newsletters, Memos) | 8 |
| Comms | 2 (Branding, Brand guidelines) | — | — | 5 (Press, IR newsletters, Earnings decks, Web/social, Marketing) | 7 |
| IT | 1 (IT policies) | — | — | 1 (IT SOPs) | 2 |

### 3.4 Cross-dept read access matrix

Read = "agent can retrieve from this collection during RAG context-gathering". Default rule: **own collection + `shared_policies` always**. Additions below are exceptions.

| Agent | Reads (beyond own + shared) | Reason |
|---|---|---|
| CEO Agent | **all** | Root supervisor |
| CFO Agent / CAC Agents | finance, risk, cio, ceo | Full financial picture for ALCO |
| Legal Agent | **all** | Contract review may touch any dept |
| Risk Agent | cac, cio, finance, legal | Risk surveillance |
| IC Chair Agent | finance, cio, vcc, legal | Investment decisions |
| CIO Agent | finance, vcc, ic | Fund / NAV cross-reference |
| VCC Head Agent | cio, ic | Client/fund alignment |
| Finance / IB / HR / Comms / IT Agents | own + shared only | Standard isolation |

Codified per-dept in `departments.json` as `crossReadAccess: ["dept_id", ...]`.

### 3.5 RAG retrieval pattern (extends existing)

The existing `services/shared/skills_loader.py` + Stage 4/5 retrieve_context pattern stays. Only change: dept-orchestrator's retrieve node reads its `crossReadAccess` list from `departments.json` and queries those Qdrant collections in parallel, weighted (own collection 1.0, shared_policies 0.7, cross-read 0.4).

```python
collections = (
    [f"{dept_id}_docs", f"{dept_id}_chat", f"{dept_id}_knowledge"]
    + ["shared_policies"]
    + [f"{d}_docs" for d in dept_config.crossReadAccess]
)
hits = await qdrant.search_multi(query, collections, weights=...)
```

**Graceful degradation rule:** stages roll out in dependency order, so cross-read targets may be queried before the target dept is live (Stage 12 Risk reads `legal_docs` / `cio_docs`; Stage 16 IC reads `cio_docs` / `vcc_docs`; etc). `retrieve_context` MUST tolerate missing Qdrant collections — log a one-time INFO line per missing collection, return zero hits for it, continue with available collections. Per-dept specs need not repeat this rule; it's framework-level invariant.

### 3.6 Ingest path for the doc inventory

Two-tier ingest (already exists in Stages 2 + 9 — only config changes):

- **Static docs** (policies, SOPs, PPM): dropped into `obsidian-vault/{dept}/entities/` → VaultWatcher picks up → wiki-compiler structures → Qdrant indexed
- **Periodic reports** (annual, weekly, monthly): pulled by sync-mirror from SharePoint/SFTP → Obsidian vault → same pipeline

For each doc in the inventory, the JSON records `ingestSource`. Actual SharePoint/SFTP paths filled in per-dept (HOD provides).

---

## 4. Agent Topology + Self-Improvement Loop

This section is the heart of the framework. It defines how each new dept-agent is composed, how it persists memory, and how it improves itself over time using the existing approval-decision feedback signal.

### 4.1 Agent topology pattern

Default per dept = **orchestrator + 3 specialists** (HR Stage 8 + existing scaffolds match this). Per-dept spec may declare more or fewer specialists.

Standard LangGraph (compiled per dept):

```
load_memory → classify_intent → retrieve_context → [specialist_agent]
  → escalation_check → [excel_navigator → validate_proposal → staging_writer]*
  → synthesise_response → log_interaction → create_paperclip_ticket
```

`*` bracketed nodes only present for `capabilityTier: write`; dropped at compile time for read-only depts.

Per-dept spec declares:

- `agentTopology: { orchestrator, specialists[] }`
- Specialist → skill mapping
- Custom nodes (e.g. CIO might add `custodian_check`)

### 4.2 Memory triad per agent

Three markdown files per agent in `obsidian-vault/{dept_id}/_memory/{agent_id}/`:

| File | Content | Loaded by | Updated by |
|---|---|---|---|
| `soul.md` | Personality, tone, hard rules | `load_memory` node | Human (rare) |
| `user.md` | Per-dept user/committee facts (names, preferences, recurring concerns) | `load_memory` node | Reflection engine, high-confidence only |
| `memory.md` | Key decisions, lessons, recurring corrections | `load_memory` node | Reflection engine, nightly |

`load_memory` concatenates the triad into LangGraph state field `agent_memory`, available alongside SKILL.md content downstream.

History preserved in `_memory/history/{agent_id}/{YYYY-MM-DD}-memory.md` for audit and rollback.

### 4.3 Daily logs

Append-only conversation history at `obsidian-vault/{dept_id}/daily-logs/YYYY-MM-DD.md`.

Hooked at end of `log_interaction` node. VaultWatcher (Stage 9) auto-indexes into `{dept_id}_chat` Qdrant collection — no new ingest path.

Entry schema:

```markdown
## 14:23 · @user_id · proposal: chg_4421
**Q:** [prompt]
**A:** [response]
**Citations:** [...]
**Confidence:** 0.91
**Outcome:** approved | edited(old→new) | rejected(reason) | pending
```

`Outcome` field updated retroactively when `approval_decisions` row lands (event-driven via Paperclip event router).

### 4.4 Reflection engine (new service)

`services/reflection-engine/` (port 3008). APScheduler nightly per dept.

**Inputs per run:**

- Yesterday's daily log
- `approval_decisions` joined with `staging_proposals` and `agent_interactions`
- `agent_knowledge_gaps` rows from yesterday
- Current `memory.md` + `user.md`

**Process** (Claude Agent SDK call per agent):

1. Group entries by outcome
2. For each edited proposal, compute delta (HOD value − agent value, plus `rejection_reason`)
3. Promote:
   - High-confidence facts → `user.md`
   - Lessons learned → `memory.md`
4. Detect patterns (≥ 5 same-shape corrections, signal_strength avg < 0.5) → insert `agent_skill_proposals` row
5. Archive prior `memory.md` to history before overwriting

**Output:** updated `memory.md` / `user.md`, optional skill_proposal rows. Audit row in `reflection_runs` table.

### 4.5 Knowledge gaps tracking

```sql
CREATE TABLE agent_knowledge_gaps (
  id              BIGSERIAL PRIMARY KEY,
  dept_id         TEXT NOT NULL,
  agent_id        TEXT NOT NULL,
  query           TEXT NOT NULL,
  hit_count       INT NOT NULL,
  llm_self_report TEXT,
  expected_doc_type TEXT,
  resolved_at     TIMESTAMPTZ,
  resolved_by     TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

Populated by `retrieve_context` (Qdrant hits < 3) or `synthesise_response` (LLM phrases like *"don't have data on"*, *"unable to find"*).

Consumed by reflection engine (drives ingestion priorities) and a new admin view in approval-ui (`/admin/knowledge-gaps`).

### 4.6 Approval-as-rating signal

Approval-ui edits/approves/rejects ARE the rating signal — Luuk Alleman's interactive 1-10 rating loop maps directly onto Brooker's existing approval flow.

| Luuk's signal | Brooker's existing signal | Source |
|---|---|---|
| Rating 9-10 | HOD **approves** as-is | `approval_decisions.action = 'approved'` |
| Rating 5-8 | HOD **edits** value | `approval_decisions.edited_value` |
| Rating 1-4 | HOD **rejects** | `approval_decisions.rejection_reason` |

```sql
CREATE VIEW agent_performance AS
SELECT
  ai.dept_id, ai.agent_id, sp.id AS proposal_id,
  ad.action,
  CASE ad.action
    WHEN 'approved' THEN 1.0
    WHEN 'edited'   THEN
      0.5 + 0.5 * (1.0 - LEAST(1.0, ABS(sp.proposed_value::numeric - ad.edited_value::numeric)
                         / NULLIF(GREATEST(ABS(sp.proposed_value::numeric), 1), 0)))
    WHEN 'rejected' THEN 0.0
  END AS signal_strength,
  ad.rejection_reason, ad.edited_value, ad.created_at
FROM approval_decisions ad
JOIN staging_proposals sp ON sp.id = ad.proposal_id
JOIN agent_interactions ai ON ai.id = sp.interaction_id;
```

`signal_strength ∈ [0.0, 1.0]` is the per-proposal label. Aggregated weekly per `(dept_id, agent_id, skill)`.

### 4.7 Self-improvement actuator — Moderate posture

```sql
CREATE TABLE agent_skill_proposals (
  id              BIGSERIAL PRIMARY KEY,
  dept_id         TEXT NOT NULL,
  agent_id        TEXT NOT NULL,
  skill_path      TEXT NOT NULL,
  trigger         TEXT NOT NULL,
  evidence        JSONB NOT NULL,
  status          TEXT DEFAULT 'pending',
  proposed_diff   TEXT,
  hod_decision_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

**Flow:**

1. Reflection engine inserts row when avg `signal_strength` < 0.5 over ≥ 5 same-shape interactions
2. Paperclip event router opens ticket → assigns to OpenClaw worker
3. OpenClaw reads skill + evidence → drafts `proposed_diff` → status `hod_review`
4. approval-ui new tab **Skill updates** renders diff → HOD approves / edits / rejects
5. On approve: OpenClaw commits to `skills/{dept}/{skill}.md`, auto-PR with metadata
6. On reject: pattern logged, threshold raised for that skill to avoid re-proposing

Memory.md updates by reflection engine **bypass** this flow (lower risk; agent-private). SKILL.md is the agent's published behaviour and stays HOD-gated.

### 4.8 Heartbeat (opt-in proactive layer)

`services/heartbeat/` (port 3009). Multi-tenant per dept. Default `enabled: false`.

`departments.json` extension:

```json
{
  "dept_id": "finance",
  "heartbeat": {
    "enabled": false,
    "schedule": "0 8 * * 1-5",
    "context_sources": ["sharepoint:Finance/Tracker", "slack:#finance-committee"],
    "outbound_actions": ["draft_email", "post_slack_summary"]
  }
}
```

When enabled: cron tick → deterministic context gather → invoke dept-orchestrator's `proactive_mode` → orchestrator emits anticipated need → posts to dept Slack channel:

> *"Tracker hasn't been updated this week. I gathered LCR=118.5, NSFR=104.2 from yesterday's CFO email. Draft a staging proposal? [Yes / No / Edit]"*

All outbound actions route through the existing staging gate — no new write paths, lethal trifecta unchanged.

### 4.9 Per-skill permission registry

SKILL.md frontmatter extended:

```yaml
---
name: liquidity-analysis
agent: liquidity-agent
dept: cac
permissions:
  mode: write_via_staging          # read_only | write_via_staging | write_direct
  data_zones: [1, 2]
  outbound_apis: []                # gmail | slack | sharepoint
  read_collections: [cac_docs, cac_chat, cac_knowledge, shared_policies]
---
```

Loaded by SkillsLoader at boot. Orchestrator runtime-enforces:

- `read_only` skill cannot reach staging_writer node
- Empty `outbound_apis` blocks heartbeat outbound actions for that skill
- `read_collections` enforced even if Qdrant client could reach others

Single source of truth for the lethal-trifecta surface — auditable per skill.

### 4.10 Output type registry

Each skill declares supported response shapes:

```yaml
output_types: [text, table, checklist, decision_tree, calculation]
```

approval-ui detects from agent response envelope and renders accordingly:

- `text` — markdown
- `table` — sortable
- `checklist` — interactive HOD-actionable
- `decision_tree` — flow diagram (Excalidraw skill)
- `calculation` — formula trace + values

New skills default to `[text]`. Extending is per-skill opt-in.

### 4.11 Out of scope (deferred)

- Voyager-style novel-skill invention (agent creating wholly new skills)
- Cross-agent learning (skill X learning from skill Y's corrections in another dept)
- True RL loop (we do prompt + example evolution only, no weight updates)

---

## 5. Department Onboarding Checklist (12 steps)

The mechanical 12-step runbook. Every per-dept stage follows this exactly. Each step has a verifiable outcome — no step is "done" until its check passes. Estimated 1-2 days per dept once the framework is in place.

### Step 1 — Catalog row audit *(verify, not create)*

`config/departments.json` and `config/document_inventory.json` already contain the dept (added when Stage 10 landed). Verify:

- [ ] `departments.json` row exists with `dept_id`, `capabilityTier`, `crossReadAccess[]`, `agentTopology`, `slackChannel`, `hodEmail`, `escalationRules`, `live: false`
- [ ] `document_inventory.json` has every doc this dept owns
- [ ] JSON Schema validation passes: `python scripts/validate_config.py`

### Step 2 — Write thin per-dept spec

File: `docs/superpowers/specs/YYYY-MM-DD-stage-N-{dept}-design.md` (~1 page; skeleton already exists from Stage 10).

Required sections (per template in §6):

1. Agent topology
2. References to `document_inventory.json` rows
3. Custom LangGraph nodes (if any)
4. Escalation rules
5. Heartbeat opt-in
6. Per-skill permission overrides

Run `superpowers:spec-document-reviewer` until approved before proceeding.

### Step 3 — Scaffold service from template

```bash
skill scaffold-from-template \
  --template services/_template-orchestrator \
  --dest services/{dept}-orchestrator \
  --dept-id {dept} \
  --port 30XX
```

**Outcome:** `services/{dept}-orchestrator/` exists with placeholders filled.

**Verify:** `cd services/{dept}-orchestrator && ruff check .` clean.

### Step 4 — Fill skill content

```bash
cp -r skills/_template skills/{dept}
```

For each of the 4 SKILL.md files, use `skill-writer` skill to draft content from:

- The dept's docs in `document_inventory.json`
- The dept's specialist scope (per spec §1)
- Standard frontmatter (permissions, data_zones, outbound_apis, read_collections, output_types)

**Verify:** `python scripts/validate_skills.py skills/{dept}/` — all frontmatter parses, all referenced collections exist.

### Step 5 — Wire LangGraph

In `services/{dept}-orchestrator/src/agents/`:

- One Python class per specialist, subclassing `services/shared/base_agent.BaseAgent`
- Each class declares `name` and `skill_path`; logic in BaseAgent
- Wire `load_memory` node (§4.2)
- For `capabilityTier: read` — drop staging path nodes

**Verify:** `python -m services.{dept}_orchestrator.src.graph --print-graph` outputs the expected node list.

### Step 6 — Database migration

New file: `migrations/0XX_add_{dept}_department.sql`

- INSERT into `paperclip_departments`
- INSERT into `paperclip_agents` (orchestrator + 3 specialists)
- (No schema changes — Stage 10 already added all framework tables)

**Verify:** `python scripts/run_migrations.py --dry-run` shows expected inserts; then run.

### Step 7 — Tests

Required test files:

- `services/{dept}-orchestrator/tests/unit/test_agents.py`
- `services/{dept}-orchestrator/tests/unit/test_graph.py`
- `services/{dept}-orchestrator/tests/unit/test_memory_load.py`
- `tests/integration/test_{dept}_e2e.py`
- `tests/integration/test_{dept}_cross_dept_read.py`
- `tests/integration/test_{dept}_reflection.py`

Coverage target: ≥ 80% on `services/{dept}-orchestrator/src/`.

**Verify:** `pytest services/{dept}-orchestrator tests/integration -k {dept} -v` all green.

### Step 8 — Docker Compose

Add service block to `docker-compose.yml` and override to `docker-compose.dev.yml`:

```yaml
{dept}-orchestrator:
  build: ./services/{dept}-orchestrator
  ports: ["30XX:30XX"]
  environment:
    DEPT_ID: {dept}
    QDRANT_URL: http://qdrant:6333
    POSTGRES_DSN: ${POSTGRES_DSN}
    PAPERCLIP_URL: http://paperclip:3100
    LLM_BASE_URL: http://nginx:8080/v1
  volumes:
    - ./data/mirror:/data/mirror:ro
    - ./data/staging:/data/staging:rw     # only if capabilityTier: write
    - ./obsidian-vault/{dept}:/vault/{dept}:rw
    - ./obsidian-vault/shared:/vault/shared:ro
    - ./skills/{dept}:/skills/{dept}:ro
    - ./skills/shared:/skills/shared:ro
  depends_on: [postgres, qdrant, paperclip, rag-ingestion]
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:30XX/health"]
    interval: 30s
```

**Verify:** `docker compose config` validates; `docker compose up -d {dept}-orchestrator` succeeds.

### Step 9 — Slack channel + bot routing

Manual:

- Create `#{dept}-committee` Slack channel
- Invite bot
- Add HOD + committee members
- Channel → orchestrator URL mapping is config-driven from `departments.json` (no slack-bot code change)

**Verify:** `@agent ping` in `#{dept}-committee` returns a threaded reply from `{dept}-orchestrator`.

### Step 10 — Obsidian vault + memory bootstrap

```bash
mkdir -p obsidian-vault/{dept}/{concepts,decisions,meeting-notes,entities,trends,daily-logs}
mkdir -p obsidian-vault/{dept}/_memory/{orchestrator,specialist1,specialist2,specialist3}
```

For each agent dir, hand-author `soul.md` (5-10 lines: tone, hard rules, identity). Empty `user.md` and `memory.md` with placeholder frontmatter.

VaultWatcher picks up new paths automatically because `config/obsidian_watch.json` was extended in Stage 10.

**Verify:** post a doc into `obsidian-vault/{dept}/concepts/test.md` → wait 60s → `curl qdrant:6333/collections/{dept}_knowledge/points/count` returns ≥ 1.

### Step 11 — Smoke test (end-to-end)

```bash
# 1. Health
curl http://localhost:30XX/health           # 200 OK
curl http://localhost:3100/agents            # dept registered, heartbeat green

# 2. Memory load
curl http://localhost:30XX/debug/memory      # returns soul/user/memory content

# 3. Real query — post in #{dept}-committee, expect threaded reply with citation

# 4. Cross-dept read enforcement (if applicable)

# 5. Approval flow (write-capable depts only)

# 6. Reflection cron
docker compose exec reflection-engine python -m reflection.engine --dept {dept} --dry-run
```

All 6 must pass.

### Step 12 — Go live

1. Edit `config/departments.json`: `{dept}.live = true`
2. Restart gateway: `docker compose restart gateway`
3. Edit `CLAUDE.md`: bump Phase 2 status, add dept to live list
4. Edit `docs/Implementation.md`: mark Stage N complete with file/test counts
5. `git tag stage-{N}-{dept}-live`
6. Announce in dept-of-record Slack channel

### Time estimate per dept

| Step | Time | Actor |
|---|---|---|
| 1 audit | 15 min | claude |
| 2 spec | 2-4h | claude (drafts) + user (reviews) |
| 3 scaffold | 5 min | claude (runs skill) |
| 4 skills | 4-6h | claude (drafts) + user (reviews tone) |
| 5 LangGraph | 2-3h | claude |
| 6 migration | 30 min | claude |
| 7 tests | 4-6h | claude |
| 8 docker | 30 min | claude |
| 9 Slack | 30 min | **user** (Slack admin) |
| 10 vault | 1h | claude (skeleton) + user (soul.md) |
| 11 smoke | 1h | claude + user |
| 12 go live | 15 min | claude + user |
| **Total** | **~1.5 days** | |

---

## 6. Per-Dept Spec Template

This is the literal structure each thin per-dept spec follows. Stored at `docs/superpowers/specs/_per-dept-spec-template.md` and copied per dept.

### 6.1 Template

```markdown
# Stage {N} — {Dept Name} Department Implementation

**Source:** `config/departments.json#{dept_id}` + `config/document_inventory.json` (rows where `ownerDept = "{dept_id}"`)
**Pattern:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
**Onboarding checklist:** §5 of the framework spec

## 1. Agent Topology

| Agent | Role | Skill file |
|---|---|---|
| `{orchestrator-name}` | Orchestrator | `skills/{dept}/{orchestrator-name}.md` |
| `{specialist-1}` | {1-line scope} | `skills/{dept}/{specialist-1}.md` |
| `{specialist-2}` | {1-line scope} | `skills/{dept}/{specialist-2}.md` |
| `{specialist-3}` | {1-line scope} | `skills/{dept}/{specialist-3}.md` |

**Deviations from default 4-agent shape:** {None | "+X custom agent because..." | "−1 specialist because..."}

## 2. Documents Owned

References `document_inventory.json`. Do not duplicate doc rows here — list IDs only.

```yaml
docs:
  - doc_{dept}_{slug1}    # title (tier)
  - doc_{dept}_{slug2}    # title (tier)
```

## 3. Custom LangGraph Nodes (if any)

If none: write *"None — uses standard graph"*.

## 4. Escalation Rules

```yaml
{rule_name}:
  trigger: {condition}
  severity: critical|high|medium|low
  notify: [hod_email | slack_channel | both]
```

## 5. Heartbeat (opt-in)

```yaml
heartbeat:
  enabled: false
  schedule: <cron>
  context_sources: [...]
  outbound_actions: [...]
```

If disabled: one-line rationale.

## 6. Per-skill Permission Overrides

| Skill | Override | Reason |
|---|---|---|

If none: write *"All skills use dept-default permissions"*.

## 7. Slack & HOD config

| Field | Value |
|---|---|
| Slack channel | `#{dept}-committee` |
| HOD email | (in `config/hod_emails.json`) |
| Approval-UI route | `/{dept}/dashboard` |

## 8. Out of Scope (for this stage)

## 9. Acceptance Criteria

- [ ] All 6 framework smoke tests pass
- [ ] {dept}-specific check 1
- [ ] {dept}-specific check 2

## 10. Rollback Plan

If stage fails post-deploy: `live: false` in departments.json, restart gateway, retain code on branch. No data destruction.
```

### 6.2 Worked example — Finance Department

```markdown
# Stage 11 — Finance Department Implementation

## 1. Agent Topology

| Agent | Role | Skill file |
|---|---|---|
| `cfo-agent` | Orchestrator | `skills/finance/cfo-agent.md` |
| `reporting-agent` | Owns Annual report, Financial statements & notes | `skills/finance/reporting.md` |
| `treasury-agent` | Owns Networth report, BG/Coins weekly | `skills/finance/treasury.md` |
| `mda-agent` | Owns MD&A drafting (cross-published with CEO) | `skills/finance/mda.md` |

**Deviations:** `cfo-agent` already exists in `skills/shared/cfo-agent.md`. Move to `skills/finance/cfo-agent.md`; thin re-export stub stays in `shared/` for one stage.

## 2. Documents Owned

```yaml
docs:
  - doc_finance_annual_report
  - doc_finance_statements_notes
  - doc_finance_networth_report
  - doc_finance_bg_weekly
  - doc_finance_coins_weekly
```

## 5. Heartbeat
`enabled: false`. Activate after Stage 11 stabilises (~30d).

## 8. Out of Scope
- Tax / audit specialist agent
- Heartbeat (deferred per §5)

## 9. Acceptance
- [ ] Standard 6 smoke tests
- [ ] CAC's CFO Agent can RAG-retrieve Finance docs (cross-dept read works end-to-end)
- [ ] Networth tracker staging proposal flows to approval-ui and back
```

---

## 7. Implementation Roadmap (Stages 10-19) + Deliverables

### 7.1 Stage 10 — Framework infrastructure (this spec → code)

**Builds:**

- Templates: `services/_template-orchestrator/`, `skills/_template/`
- New services: `reflection-engine` (port 3008), `heartbeat` (port 3009 — code in place, default disabled)
- New tables: `agent_knowledge_gaps`, `agent_skill_proposals`, `reflection_runs`
- New view: `agent_performance`
- Validation scripts: `scripts/validate_config.py`, `validate_skills.py`
- Skill rename + folder cleanup: `skills/invest` → `skills/ic`, delete `skills/ops`
- Extend `config/departments.json` schema and migrate existing 2 dept rows
- Create `config/document_inventory.json` (full ~45 rows, future-dept rows have `live: false` placeholders)
- Stub vault folders for the 9 future depts
- Approval-UI: new tab **Skill updates** + admin view `/admin/knowledge-gaps`
- 9 skeleton dept specs + 9 skeleton dept plans (Stage 10 deliverable, per skeleton-now decision)

**Implementation status:** ✅ shipped 2026-04-28 — see `docs/Implementation.md` § Stage 10.

**Acceptance:**

- All existing tests still green (CAC + HR regression)
- New services pass health/heartbeat
- Reflection engine processes a manual day's worth of CAC + HR data without errors
- Validation scripts catch a deliberately-broken JSON config

### 7.2 Stages 11-19 — Per-dept rollout

| Stage | Dept | Posture | Has scaffold? | Cross-read dependents |
|---|---|---|---|---|
| 11 | **Finance** | Write | No | CAC, IC, Risk, CIO read it |
| 12 | **Risk** | Read-only | ✅ | None new |
| 13 | **Legal** | Read-only | ✅ | IC, Risk read it |
| 14 | **IT** | Read-only | ✅ | None |
| 15 | **Communications** | Read-only | No | CEO publishes via it |
| 16 | **IC Committee** | Read-only | ✅ | Cross-reads Finance, CIO, VCC, Legal |
| 17 | **CIO Office** | Write | No | Cross-reads Finance, VCC, IC |
| 18 | **VCC** | Write | No | Cross-reads CIO, IC |
| 19 | **IB** | Read-only | No | None — narrative dept |

### 7.3 Dependencies

```
                       Stage 10 — Framework
                              │
                              ▼
                         Stage 11 — Finance  ◄────────┐
                              │                       │
              ┌───────┬───────┼───────┬───────┐      cross-read
              ▼       ▼       ▼       ▼       ▼      activates
          Stage 12  Stage 13  Stage 14  Stage 15  Stage 19
           Risk    Legal     IT       Comms     IB
              │       │
              └───┬───┘
                  ▼
              Stage 16 — IC ◄──── needs Finance + Legal live
                  │
                  ▼
              Stage 17 — CIO ◄─── needs Finance live
                  │
                  ▼
              Stage 18 — VCC ◄─── needs CIO live
```

### 7.4 Estimated calendar

| Block | Stages | Effort | Calendar |
|---|---|---|---|
| Framework | 10 | 1.5 weeks | Week 1-2 |
| Easy quad | 11, 12, 13, 14 | 1.5 days × 4 = 6 days | Week 3-4 |
| Medium pair | 15, 16 | 1.5 days × 2 = 3 days | Week 5 |
| Complex trio | 17, 18, 19 | 1.5 days × 3 = 4.5 days | Week 6-7 |
| Hardening | All-dept E2E + reflection soak | 3 days | Week 8 |
| **Total** | | **~6-8 weeks** | |

### 7.5 Decision gates

- After Stage 10: verify framework end-to-end against CAC + HR (regression)
- After Stage 11: verify cross-read enforcement works (CAC reading Finance's collection)
- After Stage 16: pause to evaluate; remaining 3 (CIO/VCC/IB) are higher complexity

### 7.6 Deliverables per stage

Every stage outputs **both** a spec and a plan as committed markdown files.

| Stage | Spec file | Plan file |
|---|---|---|
| 10 | `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md` | (plan archived 2026-05-13 — Stage 10 shipped; see `docs/Implementation.md`) |
| 11 | `docs/superpowers/specs/YYYY-MM-DD-stage11-finance-design.md` | `docs/superpowers/plans/YYYY-MM-DD-stage11-finance.md` |
| 12 | `docs/superpowers/specs/YYYY-MM-DD-stage12-risk-design.md` | `docs/superpowers/plans/YYYY-MM-DD-stage12-risk.md` |
| 13 | `docs/superpowers/specs/YYYY-MM-DD-stage13-legal-design.md` | `docs/superpowers/plans/YYYY-MM-DD-stage13-legal.md` |
| 14 | `docs/superpowers/specs/YYYY-MM-DD-stage14-it-design.md` | `docs/superpowers/plans/YYYY-MM-DD-stage14-it.md` |
| 15 | `docs/superpowers/specs/YYYY-MM-DD-stage15-comms-design.md` | `docs/superpowers/plans/YYYY-MM-DD-stage15-comms.md` |
| 16 | `docs/superpowers/specs/YYYY-MM-DD-stage16-ic-design.md` | `docs/superpowers/plans/YYYY-MM-DD-stage16-ic.md` |
| 17 | `docs/superpowers/specs/YYYY-MM-DD-stage17-cio-design.md` | `docs/superpowers/plans/YYYY-MM-DD-stage17-cio.md` |
| 18 | `docs/superpowers/specs/YYYY-MM-DD-stage18-vcc-design.md` | `docs/superpowers/plans/YYYY-MM-DD-stage18-vcc.md` |
| 19 | `docs/superpowers/specs/YYYY-MM-DD-stage19-ib-design.md` | `docs/superpowers/plans/YYYY-MM-DD-stage19-ib.md` |

**Workflow contract per stage:** brainstorm → spec written via `superpowers:brainstorming` → spec review loop → user reviews → plan written via `superpowers:writing-plans` → execute via `superpowers:executing-plans`. Both files committed before any code lands. Stage isn't "complete" in `Implementation.md` until both files exist *and* are linked from the stage entry.

**Skeleton-now decision:** all 9 dept specs + 9 dept plans created during Stage 10 with placeholder content. Each subsequent stage fills the blanks rather than starting from scratch.

---

## 8. Testing Strategy

### 8.1 Framework-level tests (Stage 10)

| Test | Lives at | Gate |
|---|---|---|
| Skill frontmatter validation | `tests/unit/test_skill_frontmatter.py` | All existing 12+ SKILL.md files parse with new permissions schema |
| `departments.json` schema validation | `tests/unit/test_departments_config.py` | All dept rows valid; cross-references resolve |
| `document_inventory.json` schema | `tests/unit/test_document_inventory.py` | Every doc row has owner + collection that exist |
| Reflection engine dry-run | `services/reflection-engine/tests/integration/test_engine.py` | Process synthetic CAC daily log → expected `memory.md` diff |
| Knowledge-gaps writer | `services/cac-orchestrator/tests/unit/test_knowledge_gaps.py` | Low-hit retrieve writes row; high-hit doesn't |
| `agent_performance` view | `tests/integration/test_agent_performance_view.py` | Synthetic approve/edit/reject rows produce expected signal_strength values |
| Skill-proposals actuator | `services/reflection-engine/tests/integration/test_skill_proposals.py` | 5 same-shape low-signal interactions → 1 row; 4 → 0 |
| Cross-dept read enforcement | `tests/integration/test_cross_dept_read.py` | Agent without crossReadAccess for collection X cannot retrieve from X |
| Skill rename safety | `tests/integration/test_invest_to_ic_rename.py` | After rename, all referencing services boot |

**Regression gate:** all 391+ existing tests still pass after framework migration. CAC and HR agents must produce identical outputs to a recorded fixture set (golden-master).

### 8.2 Per-dept stage tests (Stages 11-19, mandated by §5 Step 7)

Required per dept:

- 4 unit test files (one per agent + graph + memory_load)
- 3 integration tests (e2e, cross_dept_read, reflection)
- ≥ 80% coverage on `services/{dept}-orchestrator/src/`

### 8.3 System-level tests (after Stage 19)

- All-dept E2E: simulated 24h of cross-dept Slack chatter; reflection engine completes nightly cycle; no errors
- Lethal-trifecta audit: every skill's permissions verified against actual runtime behaviour; any discrepancy = bug

### 8.4 Test data strategy

- Synthetic fixtures for CAC + HR existing logs (committed to repo)
- Per-dept fixture set built during that dept's stage
- No production data in tests

---

## 9. Risks & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Framework migration breaks live CAC + HR | Medium | High | Golden-master regression test (8.1); staged rollout; rollback by `live: false` |
| 2 | Cross-dept read leakage | Medium | High | Two-layer enforcement: retrieve_context filters per `crossReadAccess[]`; SkillsLoader validates skill's `read_collections` matches dept config; integration test asserts denial |
| 3 | Reflection engine hallucinates into `memory.md` | High | Medium | Pre-overwrite archive; weekly HOD review; LLM critic pass before write |
| 4 | Self-improvement actuator spams skill_proposals | Medium | Medium | Threshold ≥ 5 same-shape corrections, avg signal_strength < 0.5; rate-limit 1 proposal per skill per week |
| 5 | Heartbeat fires unintended write | Low (default off) | High | Default `enabled: false`; outbound via existing staging gate; per-dept opt-in requires HOD signoff |
| 6 | Schema migration timing race | Low | Medium | All migrations non-destructive; deploy order: schema → services → flip flags |
| 7 | `invest` → `ic` rename breaks consumers | Low | High | Grep before rename — no production service imports `skills/invest/*`; symlink kept one stage as safety |
| 8 | JSON config drift | High | Low | Validation script in CI; cross-reference checker |
| 9 | Reflection-engine cron fails silently | Medium | Medium | Heartbeat from reflection-engine to paperclip; missing heartbeat alerts in `#cac-committee`; nightly summary email |
| 10 | Read-only dept accidentally activates write path | Low | High | `capabilityTier` checked at graph compilation; integration test verifies graph has no staging_writer node |
| 11 | Skill update PR auto-merged without review | Low | High | Moderate-posture (§4.7) requires HOD approve via approval-ui; auto-merge disabled |
| 12 | Vault folder permissions misconfigured | Medium | Medium | Docker volumes mount per-dept paths only; OpenClaw vault writer has path-traversal protection (Stage 8) |

---

## 10. Decisions Log

Recorded during the brainstorming session that produced this spec. All confirmed by the user.

| # | Decision | Reasoning |
|---|---|---|
| D1 | **Decomposition strategy = framework + thin per-dept specs** | Avoids one mega-spec; matches how HR was done; makes per-stage work mechanical |
| D2 | **Existing scaffolds = audit + adopt (rename invest→ic, delete ops)** | Keeps existing skill content; reconciles to org chart; removes orphan dept |
| D3 | **Capability posture per dept** | Finance / CIO / VCC = write-capable; rest = read-only. Mirrors HR (read-only, PII) and CAC (write, tracker) precedents |
| D4 | **Cross-dept read access matrix** | CEO reads all; Legal reads all; CFO/CAC/Risk/IC have specific cross-reads; rest isolated to own + shared |
| D5 | **Catalog + template + spec layers (option C)** | Hybrid matches existing departments.json single-source-of-truth + service-scaffold pattern |
| D6 | **Self-improvement engine = both videos combined** | Cole Medin memory triad + Luuk Alleman approval-as-rating; map HOD approve/edit/reject onto Luuk's 1-10 scale |
| D7 | **Heartbeat included in framework, default disabled per dept** | Lands architecture now; opt-in later as HODs supply API creds |
| D8 | **Self-improvement aggressiveness = (b) Moderate** | memory.md auto-updates (low risk, agent-private); SKILL.md updates require HOD review (lethal trifecta) |
| D9 | **Skeleton-now (option A)** | All 9 dept spec + plan files created in Stage 10 with placeholders; subsequent stages fill blanks |
| D10 | **Every stage produces spec + plan markdown files; both committed before code** | Aligns with existing Stages 4-8 pattern in Implementation.md |

---

## 11. References

- **Org chart:** `docs/diagrams/department-agent-map.drawio`
- **PRD:** `PRD.md` v2.2 (sections 7 — CAC; 11 — SKILL.md format; 13 — build order)
- **Architecture spec:** `docs/superpowers/specs/2026-03-25-architecture-design.md` (living document — covers Stages 1-19)
- **Implementation log:** `docs/Implementation.md` (canonical stage-by-stage record; Stages 1-10 ✅, 11-19 📋)
- **Project memory:** `CLAUDE.md`
- **Karpathy llm-wiki gist:** https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- **Video 1 (Luuk Alleman — self-improving agent):** https://www.youtube.com/watch?v=DA_2G4ZQ6UI
- **Video 2 (Cole Medin — second brain):** https://www.youtube.com/watch?v=1FiER-40zng

> *Note (2026-05-13): Per-stage execution plans/specs for Stages 1–9 were removed during doc cleanup. The architecture spec and Implementation.md retain the design decisions; git history retains the originals.*

---

## Next steps

1. ✅ Spec written
2. ✅ Spec review loop completed
3. ✅ Stage 10 implementation shipped 2026-04-28 — see `docs/Implementation.md` § Stage 10
4. Onboard Phase 2 departments using this framework (Stages 11–19) — one plan + spec pair per dept under `docs/superpowers/{plans,specs}/`
