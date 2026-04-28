# Stage {N} — {Dept Name} Department Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Stand up the `{dept}` dept-orchestrator following the framework's 12-step onboarding checklist.

**Spec:** `docs/superpowers/specs/YYYY-MM-DD-stage{N}-{dept}-design.md`
**Framework:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md` (esp. §5 12-step checklist)
**Posture:** `{read_only | write}` · **Cross-reads:** {list} · **Existing scaffold:** {yes/no} · **Dependencies (live stages):** {list}

**Status:** skeleton — fleshed out at this stage's kickoff brainstorm

---

## Pre-flight (must be true before this plan starts)

- [ ] Stage 10 (framework) is live and tagged `stage-10-framework-live`
- [ ] All listed dependency stages are live
- [ ] `services/_template-orchestrator/` exists
- [ ] `skills/_template/` exists
- [ ] `scripts/validate_config.py` passes for `{dept}`
- [ ] `scripts/validate_skills.py` passes
- [ ] Worktree created (`superpowers:using-git-worktrees`)

---

## Phase A — Catalog audit + spec finalization *(framework §5 Steps 1-2)*

### Task A.1: Verify catalog row
- [ ] `python scripts/validate_config.py` succeeds for `{dept}`
- [ ] `documents` array on `{dept}` matches `document_inventory.json` rows where `ownerDept = "{dept}"`
- [ ] All TBDs in per-dept spec resolved (escalation thresholds, HOD email, ingest sources, etc.)

### Task A.2: Finalize per-dept spec
- [ ] Re-run `superpowers:brainstorming` to fill in spec §4 (escalation rules), §7 (HOD email), and any Out-of-Scope items
- [ ] Run `superpowers:spec-document-reviewer` until approved
- [ ] Commit final spec

---

## Phase B — Scaffold *(framework §5 Steps 3-4)*

### Task B.1: Service scaffold from template
- [ ] `skill scaffold-from-template --template services/_template-orchestrator --dest services/{dept}-orchestrator --dept-id {dept} --port 30XX`
- [ ] `cd services/{dept}-orchestrator && ruff check .` clean
- [ ] Health endpoint returns 200 against the bare scaffold

### Task B.2: Fill skill content
- [ ] `cp -r skills/_template skills/{dept}`
- [ ] For each of the 4 SKILL.md files: invoke `skill-writer` skill with dept's docs from inventory + specialist scope from spec §1
- [ ] Set frontmatter (permissions block + output_types) per spec §6
- [ ] `python scripts/validate_skills.py skills/{dept}/` clean

---

## Phase C — Wiring *(framework §5 Steps 5-6)*

### Task C.1: Implement specialist agents + LangGraph
- [ ] Create one Python class per specialist subclassing `services/shared/base_agent.BaseAgent`
- [ ] Wire `load_memory` node first
- [ ] Read-only depts: drop staging-path nodes (excel_navigator, validate_proposal, staging_writer)
- [ ] Custom nodes per spec §3 (if any)
- [ ] `python -m services.{dept}_orchestrator.src.graph --print-graph` outputs expected node list

### Task C.2: Database migration
- [ ] Author `migrations/0XX_add_{dept}_department.sql`
- [ ] INSERT into `paperclip_departments` and `paperclip_agents`
- [ ] `python scripts/run_migrations.py --dry-run` then real run

---

## Phase D — Tests *(framework §5 Step 7)*

### Task D.1: Unit tests
- [ ] `services/{dept}-orchestrator/tests/unit/test_agents.py` — one class per specialist
- [ ] `services/{dept}-orchestrator/tests/unit/test_graph.py` — graph compiles + node order
- [ ] `services/{dept}-orchestrator/tests/unit/test_memory_load.py` — load_memory reads triad

### Task D.2: Integration tests
- [ ] `tests/integration/test_{dept}_e2e.py` — full Slack→orchestrator→approval flow (write-capable depts) or query-only flow (read-only)
- [ ] `tests/integration/test_{dept}_cross_dept_read.py` — `crossReadAccess[]` enforcement
- [ ] `tests/integration/test_{dept}_reflection.py` — reflection engine processes day-old logs

### Task D.3: Coverage check
- [ ] `pytest services/{dept}-orchestrator tests/integration -k {dept} --cov=services.{dept}_orchestrator.src --cov-fail-under=80`

---

## Phase E — Deploy *(framework §5 Steps 8-10)*

### Task E.1: docker-compose entry
- [ ] Add service block to `docker-compose.yml` (port 30XX, volume mounts per capability tier)
- [ ] Add dev-mode override in `docker-compose.dev.yml`
- [ ] `docker compose config` validates
- [ ] `docker compose up -d {dept}-orchestrator` healthcheck passes

### Task E.2: Slack channel + bot routing
- [ ] **(user)** Create `#{dept}-committee` Slack channel + invite bot + add HOD/committee
- [ ] Verify `@agent ping` in channel returns threaded reply

### Task E.3: Vault folder + memory bootstrap
- [ ] Verify `obsidian-vault/{dept}/` exists (created in Stage 10) with `_memory/{agent_id}/` subdirs
- [ ] Hand-author `soul.md` for each agent (5-10 lines: tone, hard rules, identity)
- [ ] Empty `user.md` and `memory.md` with frontmatter placeholder
- [ ] Drop a test doc into `obsidian-vault/{dept}/concepts/test.md` → verify Qdrant indexing within 60s

---

## Phase F — Smoke + Go-live *(framework §5 Steps 11-12)*

### Task F.1: Six framework smoke tests
- [ ] `/health` returns 200
- [ ] Paperclip `/agents` shows dept registered + heartbeat green
- [ ] Memory load: `/debug/memory` returns soul/user/memory content
- [ ] Real query in `#{dept}-committee` returns threaded reply with citations
- [ ] Cross-dept read works (if applicable)
- [ ] Approval flow works (write-capable depts only)

### Task F.2: Flip live + restart gateway
- [ ] Edit `config/departments.json`: `{dept}.live = true`
- [ ] `docker compose restart gateway` (picks up routing)
- [ ] Update `CLAUDE.md` Phase 2 status: add `{dept}` to live list
- [ ] Update `docs/Implementation.md`: mark Stage {N} complete with file/test counts

### Task F.3: Tag + announce
- [ ] `git tag stage-{N}-{dept}-live`
- [ ] Announce in dept-of-record Slack channel

---

## Acceptance criteria

Mirror dept spec §9 + framework §5 Step 11 smoke tests. **Stage is not complete until every checkbox above is ticked AND dept spec acceptance criteria pass.**

## Estimated effort

~1.5 days focused work (framework §7.4). HOD/Slack-admin hand-offs may extend calendar time.

## Rollback

Per dept spec §10 — `live: false`, restart gateway, retain code on branch. No data destruction.
