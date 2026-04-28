# Stage 11 — Finance Department Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Stand up the `finance` dept-orchestrator (CFO Agent + 3 specialists) — first Phase 2 write-capable dept, stress-tests cross-dept read enforcement.

**Spec:** `docs/superpowers/specs/2026-04-28-stage11-finance-design.md`
**Framework:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md` (§5 12-step checklist)
**Posture:** `write` · **Cross-reads:** own + `shared_policies` only (read-side); CAC + IC + Risk + CIO read INTO finance · **Existing scaffold:** ❌ none · **Dependencies:** Stage 10 only · **Service port:** 3010

**Status:** skeleton — fleshed out at Stage 11 kickoff brainstorm

---

## Pre-flight

- [ ] Stage 10 tagged `stage-10-framework-live`
- [ ] `skills/finance/cfo-agent.md` exists (moved from `shared/` during Stage 10)
- [ ] `config/departments.json#finance` row complete (capabilityTier, agentTopology, documents)
- [ ] `config/document_inventory.json` has 5 finance rows (annual_report, statements_notes, networth, bg_weekly, coins_weekly)
- [ ] Worktree created via `superpowers:using-git-worktrees`

---

## Phase A — Catalog audit + spec finalization

### Task A.1: Verify catalog row
- [ ] `python scripts/validate_config.py` succeeds
- [ ] `python scripts/validate_skills.py skills/finance/` (cfo-agent.md only, others created in Phase B)

### Task A.2: Finalize spec
- [ ] Re-run `superpowers:brainstorming` to fill: §4 escalation thresholds (networth_drop %, cash_position_critical absolute), §7 HOD email, ingest source paths
- [ ] Run `superpowers:spec-document-reviewer` until approved
- [ ] Commit finalized spec

---

## Phase B — Scaffold

### Task B.1: Service scaffold (port 3010)
- [ ] Run `service-scaffold` skill from `services/_template-orchestrator/` → `services/finance-orchestrator/`
- [ ] Replace placeholders: DEPT_ID=finance, DEPT_NAME=Finance, PORT=3010
- [ ] `ruff check services/finance-orchestrator/` clean

### Task B.2: Fill skill content
- [ ] `cp -r skills/_template skills/finance` (cfo-agent.md already there from Stage 10 — preserve)
- [ ] `skill-writer` for `reporting.md` (Annual report + Financial statements)
- [ ] `skill-writer` for `treasury.md` (Networth + BG weekly + Coins weekly)
- [ ] `skill-writer` for `mda.md` (MD&A drafting, cross-published with CEO)
- [ ] Frontmatter for all 4: `mode: write_via_staging`, `data_zones: [1, 2]`, `read_collections: [finance_docs, finance_chat, finance_knowledge, shared_policies]`, `output_types: [text, table, calculation]`
- [ ] `python scripts/validate_skills.py skills/finance/` clean

---

## Phase C — Wiring

### Task C.1: Specialist agents + LangGraph
- [ ] `services/finance-orchestrator/src/agents/reporting_agent.py` (subclass BaseAgent)
- [ ] `agents/treasury_agent.py`, `agents/mda_agent.py`
- [ ] `agents/cfo_agent.py` is the orchestrator — delegates by intent classification
- [ ] Standard graph (no custom nodes per spec §3)
- [ ] Write-capable: keep staging path nodes
- [ ] `python -m services.finance_orchestrator.src.graph --print-graph` shows: load_memory → classify → retrieve → specialist → escalation → excel_navigator → validate → staging_writer → synthesise → log_interaction → paperclip_ticket

### Task C.2: Database migration
- [ ] `migrations/011_add_finance_department.sql`:
  - INSERT paperclip_departments (`finance`, `Finance`, 3010, `write`, `#finance-committee`)
  - INSERT paperclip_agents (cfo-agent, reporting-agent, treasury-agent, mda-agent)
- [ ] Run + verify

---

## Phase D — Tests

### Task D.1: Unit
- [ ] `tests/unit/test_agents.py` — 4 specialists × 3 tests each (intent match, retrieve scope, output shape)
- [ ] `tests/unit/test_graph.py` — graph compiles, all 11 nodes present, write path intact
- [ ] `tests/unit/test_memory_load.py` — soul/user/memory load correctly

### Task D.2: Integration (CRITICAL — cross-read is the framework's biggest risk)
- [ ] `tests/integration/test_finance_e2e.py` — Networth tracker proposal flow: query → agent proposes → HOD email → approval-ui approve → sync-back writes mirror
- [ ] **`tests/integration/test_finance_cross_dept_read.py`** — most important test of Stage 11:
  - CAC's CFO Agent queries about networth → retrieve_context returns finance_docs hits ✅
  - HR Agent queries about networth → finance_docs NOT in retrieved sources ❌
  - Stage 11 ships before CIO/Risk/IC — those depts not yet live, so reverse-cross-read isn't testable yet
- [ ] `tests/integration/test_finance_reflection.py` — reflection engine processes synthetic finance daily log

### Task D.3: Coverage
- [ ] `pytest services/finance-orchestrator -v --cov-fail-under=80`

---

## Phase E — Deploy

### Task E.1: docker-compose
- [ ] Add `finance-orchestrator` service block (port 3010, mirror:ro, staging:rw, vault rw, skills ro)
- [ ] dev override
- [ ] `docker compose up -d finance-orchestrator` healthcheck green

### Task E.2: Slack
- [ ] **(user)** Create `#finance-committee` channel, invite bot + HOD + Finance team
- [ ] Verify `@agent ping`

### Task E.3: Vault + memory
- [ ] `obsidian-vault/finance/_memory/{cfo,reporting,treasury,mda}/` (created in Stage 10)
- [ ] Hand-author 4 `soul.md` files (CFO Agent's tone is formal/precise; specialists are sub-personalities)
- [ ] Drop test doc → verify finance_knowledge indexing

---

## Phase F — Smoke + Go-live

### Task F.1: 6 smoke tests + cross-read verification
- [ ] All 6 framework smoke tests pass
- [ ] **Cross-dept regression:** CAC's existing test suite still passes; CAC now retrieves from finance_docs in cross-dept queries

### Task F.2: Live + restart gateway
- [ ] `config/departments.json#finance.live = true`
- [ ] `docker compose restart gateway`
- [ ] Update `CLAUDE.md` (Phase 2 status: Finance live)
- [ ] Update `docs/Implementation.md` (Stage 11 entry with file/test counts)

### Task F.3: Tag + announce
- [ ] `git tag stage-11-finance-live`
- [ ] Announce in `#finance-committee` and `#cac-committee` (cross-dept impact)

---

## Stage-specific acceptance criteria *(spec §9)*

- [ ] All 6 framework smoke tests pass
- [ ] **CAC's CFO Agent can RAG-retrieve Finance docs** — first end-to-end cross-dept-read test (biggest architectural risk per framework §7.5)
- [ ] Networth tracker staging proposal flow end-to-end works
- [ ] `agent_performance` view records `signal_strength` correctly for ≥ 1 approved + 1 edited proposal
- [ ] Reflection engine processes Finance daily logs without error after 24h activity

## Effort

~1.5 days. Slightly longer for the first dept because cross-read enforcement gets real-world testing.

## Decision gate after Stage 11

Per framework §7.5: pause to verify cross-read enforcement actually works before launching Stages 12-14 in parallel.
