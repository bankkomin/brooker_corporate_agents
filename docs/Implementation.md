# Implementation Progress

**Source:** PRD.md v2.2 + Architecture Design Spec
**Current:** Stage 8 — Worker Dispatch + Obsidian + HR Department (complete)
**Started:** 2026-03-25

---

## Stage 1 — Infrastructure ✅ (2026-03-25)
- [x] Create repository directory structure (all folders from PRD §4)
- [x] Create .gitignore (Python, Docker, .env, data/, node_modules, .obsidian/)
- [x] Create .env.example (all env vars from PRD §12)
- [x] Create README.md
- [x] Create AGENTS.md (session context paste)
- [x] Write docker-compose.yml (postgres, qdrant, minio, nginx, gateway)
- [x] Write docker-compose.dev.yml (local dev overrides, mock LLM)
- [x] Write infra/vllm/start-122b.sh
- [x] Write infra/vllm/start-embed.sh
- [x] Write infra/nginx/nginx.conf (dual-Spark LB, port 8080)
- [x] Write migrations/001_initial_schema.sql (7 Postgres tables)
- [x] Create config/ skeleton files (alco_tracker.json, dept_channels.json, hod_emails.json, escalation_rules.json, obsidian_watch.json)
- [x] Write data directory setup script
- [x] Verify: docker compose up starts postgres, qdrant, minio, nginx
- [x] Verify: all health checks pass (6/6)
- [x] Verify: Postgres has all 7 tables (8/8 integration tests pass)

## Stage 2 — Mirror + RAG (partial ✅ 2026-03-30)

### sync-mirror (partial — connectors + hash_check done earlier)
- [x] Build services/sync-mirror/src/config.py
- [x] Build services/sync-mirror/src/connectors/base.py (ABC + RemoteFile)
- [x] Build services/sync-mirror/src/connectors/sharepoint.py (stub)
- [x] Build services/sync-mirror/src/connectors/sftp.py (stub)
- [x] Build services/sync-mirror/src/hash_check.py (SHA-256 manifest)
- [x] Build services/sync-mirror/src/sync_log.py (Postgres logger)
- [ ] Build sync-mirror scheduler (APScheduler, 15-min interval)
- [ ] Dockerfile + docker-compose entry
- [ ] Integration test: test_mirror_sync

### rag-ingestion ✅ (2026-03-30)
- [x] Build services/rag-ingestion/src/chunker.py (PDF/DOCX/XLSX/MD/TXT)
- [x] Build services/rag-ingestion/src/embedder.py (async vLLM wrapper, batching, retry)
- [x] Build services/rag-ingestion/src/qdrant_store.py (4 collections, async CRUD)
- [x] Build services/rag-ingestion/src/chat_indexer.py (SHA-256 dedup)
- [x] Build services/rag-ingestion/src/vault_watcher.py (watchdog, debounce, Postgres dedup)
- [x] Build services/rag-ingestion/src/main.py (FastAPI: /ingest/document, /ingest/message, /health, /collections)
- [x] Dockerfile + docker-compose uncommented (mirror:ro, extra_hosts)
- [x] Unit tests: test_chunker (20), test_embedder (26), test_qdrant_store (30), test_chat_indexer (16), test_vault_watcher (19), test_models (10)
- [x] Integration test: test_rag_pipeline (15)
- [x] Verify: ruff clean, 136 rag-ingestion tests passing
- [ ] Verify: container cannot write to /data/mirror/ (:ro enforced)

**Architecture:** FastAPI on port 3004. Documents chunked (character-based splitter with overlap),
embedded via vLLM Qwen 9B (OpenAI-compatible), stored in Qdrant (4 collections: cac_docs, cac_chat,
cac_knowledge, shared_policies). VaultWatcher uses watchdog + debounce + Postgres hash dedup.
**Files:** 6 source files, 7 test files | **Tests:** 136 (121 unit + 15 integration)
**Plan:** `docs/superpowers/plans/2026-03-30-stage2-rag-ingestion.md`

## Stage 3 — Slack Bot ✅ (2026-03-30)
- [x] Create Slack App (permissions: channels:history, files:read, chat:write, app_mentions:read)
- [x] Add bot to #cac-committee test channel
- [x] Build services/slack-bot/ (config, models, clients, events, file_handler, responder, main)
- [x] Test: post message → Qdrant indexed (via rag-ingestion POST /ingest/message)
- [x] Test: share file → ingestion triggers (download + multipart POST /ingest/document)
- [x] Test: @agent hello → threaded reply (orchestrator stub returns canned message)
- [x] Integration test: test_slack_bot (health + URL verification)
- [x] Docker Compose: slack-bot entry + dev overrides
- [x] Code review: 4 findings fixed (retry logic, file size check, httpx leak, curl in Dockerfile)
- [x] Verify: ruff clean, 47 slack-bot tests passing, 79 total suite

**Architecture:** Slack Bolt (async) + FastAPI via AsyncSlackRequestHandler, port 3003.
ACK-then-process pattern — all events acknowledged < 100ms, processed via asyncio.create_task().
Orchestrator stubbed via ORCHESTRATOR_ENABLED=false feature flag (flip in Stage 4).
**Files:** 11 source files, 9 test files | **Tests:** 47 new (45 unit + 2 integration)
**Plan:** `docs/superpowers/plans/2026-03-30-stage3-slack-bot.md`

## Stage 4 — CAC Orchestrator ✅ (2026-03-31)
- [x] Write AgentState TypedDict (src/state.py — 24 fields incl. validation_passed, validation_warnings)
- [x] Build graph.py skeleton — all 10 nodes wired with conditional routing
- [x] Implement classify_intent (Qwen 122B via nginx:8080, JSON parse with graceful fallback)
- [x] Implement retrieve_context (Qdrant search across cac_docs, cac_chat, cac_knowledge)
- [x] Implement all 4 specialist agents as smart stubs (liquidity, capital, alm, funding)
- [x] Implement escalation_check (escalation_rules.json threshold matching)
- [x] Implement excel_navigator (alco_tracker.json cell mapping)
- [x] Implement validate_proposal (independent LLM cross-check + 7-day history contradiction detection)
- [x] Implement staging_writer (manifest.json to /data/staging/pending/, confidence >= 0.85 gate)
- [x] Implement synthesise_response (Qwen 122B with citations, confidence labels)
- [x] Implement create_paperclip_ticket (stub — PPC-XXXX IDs until Stage 7)
- [x] Wire end-to-end: POST /query → structured QueryResponse
- [x] Load SKILL.md via skills/loader.py (async, cached, graceful degradation)
- [x] Create 6 placeholder SKILL.md files (shared/escalation-protocol, shared/citation-format, cac/liquidity-analysis, cac/capital-allocation, cac/alm-review, cac/funding-facilities)
- [x] Docker Compose: cac-orchestrator uncommented (port 3001, /data/mirror:ro, /data/staging:rw)
- [x] Unit tests: test_config (20), test_models (14), test_state (5), test_llm_client (5), test_db_client (6), test_skills_loader (4), test_classify_intent (10), test_rag_retrieve (8), test_escalation (6), test_excel_nav (6), test_validate_proposal (10), test_staging_writer (8), test_synthesise (6), test_agents (12), test_skills_loader_integration (13)
- [x] Integration test: test_cac_graph (9 tests — query endpoint, health, heartbeat)
- [x] Code review: C1 (hardcoded threshold), C2 (thread-safe counters), I5 (raw variable) fixed
- [x] Verify: 142 Stage 4 tests passing, 275 total suite passing, data safety verified

**Architecture:** LangGraph StateGraph with conditional routing (not parallel fan-out — documented
deviation from PRD). Linear chain: classify → retrieve → agent → escalation → excel_nav →
validate → staging → synthesise → paperclip. Validation gate added beyond PRD spec — independent
LLM cross-check with 4 checks (source accuracy, cell validity, reasoning soundness, contradiction
detection) plus 7-day history cross-check against staging_proposals DB.
**Scope note:** Consolidates PRD Weeks 4+5 — all nodes present as smart stubs, full end-to-end testable.
**Deferred to Stage 5:** AsyncPostgresSaver checkpointer (multi-turn), agents using skills loader,
interaction_id audit trail link, validation fail-closed on parse errors.
**Files:** 30 source files + 6 placeholder skills, 16 test files | **Tests:** 142 (133 unit + 9 integration)
**Plan:** `docs/superpowers/plans/2026-03-30-stage4-cac-orchestrator.md`

## Stage 5 — All Agents + Staging Writer ✅ (2026-03-31)
- [x] Wire AsyncPostgresSaver checkpointer for multi-turn conversations
- [x] Implement real agent logic (replace smart stubs) using SKILL.md via skills/loader.py
- [x] Wire interaction_id from agent_interactions to staging_proposals (audit trail)
- [x] Connect escalation_check → POST email-notifier /notify/escalation (stub ok)
- [x] Change validate_proposal to fail-closed on LLM parse errors (production hardening)
- [x] Flesh out SKILL.md content for all 10 files (5 shared + 5 CAC)
- [x] Build email-notifier stub service (4 /notify/* endpoints, Docker)
- [x] Build SkillsLoader class (frontmatter stripping, caching, agent skill concatenation)
- [x] Refactor BaseAgent with DI (llm_client, skills_loader) and LLM-backed analyze()
- [x] Add two-phase audit trail (create_interaction before, update_interaction after)
- [x] Integration tests: test_staging_flow, test_escalation_flow
- [x] Code review: C1/C2 verified safe, S1 (proposed_tab in general_handler) + S4 (restart policy) fixed
- [x] Verify: 377 total tests passing, ruff clean on all Stage 5 files

**Architecture:** BaseAgent refactored with dependency injection — each specialist agent is a thin
subclass (name + skill_path) with all logic in BaseAgent.analyze(). Prompt-based chains: SKILL.md
content + RAG context + conversation history → single LLM call → JSON parse with fallback.
AsyncPostgresSaver enables multi-turn conversations keyed on (user_id, thread_ts). Two-phase audit
trail: create_interaction() before graph, update_interaction() after, with interaction_id FK linking
to staging_proposals. Escalation wiring: notify_escalation node fires POST to email-notifier stub
(fire-and-forget). Validation hardened to fail-closed on unparseable LLM responses.
**Files:** 17 new files, 20 modified files | **Tests:** 52 new (377 total)
**Spec:** `docs/superpowers/specs/2026-03-31-stage5-agents-staging-design.md`
**Plan:** `docs/superpowers/plans/2026-03-31-stage5-agents-staging.md`

## Stage 6 — Approval UI + Sync Back + Email Notifier ✅ (2026-04-02)
- [x] Build services/approval-ui/ (Next.js 15 + shadcn/ui + Tailwind CSS 4, port 4000)
- [x] Build department dashboard with proposal list, diff view, action buttons
- [x] Build JWT deep-link entry page (/approve?token=xyz)
- [x] Build RS256 JWT auth middleware in gateway
- [x] Build proposal CRUD endpoints with department-scoped RBAC
- [x] Build escalation and analytics endpoints
- [x] Build services/sync-back/ (FastAPI, /process-approved endpoint, openpyxl writer)
- [x] Build services/email-notifier/ (JWT generation, SMTP sender, 4 HTML templates)
- [x] Build 24h reminder APScheduler job in email-notifier
- [x] Create departments.json as single source of truth (replaces dept_channels.json + hod_emails.json)
- [x] Migration 003: Add dept columns to staging_proposals, escalations, approval_decisions
- [x] Docker Compose: approval-ui, sync-back, email-notifier services with JWT secrets
- [x] Vitest frontend tests (auth, proposal components, deep-link flow)
- [x] Integration tests: E2E approval flow, dept isolation, rejection tests
- [x] Code review: TOCTOU fix, table name fix, edit persistence, gateway URL fix

**Architecture:** Next.js 15 standalone container (port 4000) calling gateway:3000 FastAPI APIs.
RS256 JWT deep-links from email-notifier. Department-scoped RBAC enforced at gateway + UI layers.
Config-driven department modularity via departments.json (single source of truth).
**Files:** 40+ new files | **Tests:** 16 new (Vitest + pytest)
**Spec:** `docs/superpowers/specs/2026-04-01-approval-ui-rbac-design.md`
**Plan:** `docs/superpowers/plans/2026-04-01-stage6-approval-ui-rbac.md`

## Stage 7 — Paperclip + Integration ✅ (2026-04-02)
- [x] Write all 11 SKILL.md files (5 shared + 5 CAC + 1 paperclip)
- [x] Build services/paperclip/ (FastAPI, port 3100, 5 subsystems)
- [x] Implement Ticket Manager (PPC-XXXX lifecycle, CRUD endpoints)
- [x] Implement Heartbeat Registry (agent health monitoring, 60s interval)
- [x] Implement Department Manager (data boundary enforcement, agent registry)
- [x] Implement Event Router (approval → sync-back + email-notifier, retry logic)
- [x] Implement Worker Manager (OpenClaw stub, pending_human status)
- [x] Migration 007: paperclip_departments, paperclip_agents, paperclip_tickets tables + CAC seed
- [x] Wire cac-orchestrator → Paperclip ticket creation (HTTP POST with heartbeat registration)
- [x] Wire approval-ui → Paperclip webhook POST on approve/reject/edit
- [x] Docker Compose: paperclip service with API key auth
- [x] Unit tests: ticket service, department service, heartbeat, worker manager, event router, routes
- [x] Integration tests: E2E golden path, escalation, rejection
- [x] Code review: ruff linting fixes

**Architecture:** Paperclip is the central audit hub and event router. 5 subsystems: Ticket Manager,
Heartbeat Registry, Department Manager, Event Router, Worker Manager. All inter-service communication
goes through Paperclip's event router with retry logic (3× exponential backoff). Department boundaries
enforce data isolation — each dept has isolated data zones, Qdrant collections, escalation rules.
OpenClaw registered as stub worker (Stage 8 wires real dispatch).
**Files:** 20+ new files | **Tests:** 30+ new (391 total suite)
**Spec:** `docs/superpowers/specs/2026-04-02-stage7-paperclip-integration-design.md`

## Stage 8 — Worker Dispatch + Obsidian + HR Department ✅ (2026-04-07)

### 8A — OpenClaw Worker Service (port 3200)
- [x] Migration 008: openclaw_executions audit trail table
- [x] Build services/openclaw/ scaffold (Dockerfile, FastAPI, Pydantic models)
- [x] Implement TaskExecutor (Claude Agent SDK wrapper — skill_draft, code_scaffold, document_generate)
- [x] Implement VaultWriter (file I/O to Obsidian vault with path traversal protection)
- [x] Implement PaperclipClient (result reporting with exponential backoff retry)
- [x] Implement task routes (POST /tasks/execute async, GET /tasks/{id}/status)
- [x] Extend Paperclip WorkerManager for HTTP dispatch (claude_sdk/claude_code → POST to worker)
- [x] Wire worker assignment routes in Paperclip (POST /workers/{agent}/assign, GET /workers/{agent}/status)
- [x] Update OpenClaw from worker_type=stub to worker_type=claude_sdk in migration 008
- [x] Docker Compose: openclaw service with Paperclip heartbeat, vault + mirror volumes

### 8B — Obsidian Vault Integration
- [x] Create vault folder structure (index.md, meeting-note template, decision-log template)
- [x] Create skills/ symlinks (junction: cac/, hr/, shared/ → repo skills/)
- [x] Update VaultWatcher for multi-collection routing (config-driven path → collection mapping)
- [x] Update obsidian_watch.json with HR/CAC/shared path prefixes
- [x] Docker volume: obsidian_vault mounted in rag-ingestion (ro) and openclaw (rw)

### 8C — HR Department (first Phase 2 expansion, port 3002)
- [x] Extract shared BaseAgent + SkillsLoader to services/shared/ (cross-department reuse)
- [x] Update cac-orchestrator base.py to re-export from shared
- [x] Write 4 HR SKILL.md files (hr-agent, recruitment, compensation, compliance)
- [x] Build services/hr-orchestrator/ scaffold (Dockerfile, FastAPI, config, state)
- [x] Implement 4 HR agents (RecruitmentAgent, CompensationAgent, ComplianceAgent, GeneralHRAgent)
- [x] Build HR LangGraph pipeline (classify → retrieve → [specialist] → escalation → synthesise → ticket)
- [x] Implement HR intent classification (keyword-based: recruitment/compensation/compliance/general)
- [x] Implement HR escalation rules (Thai labor law triggers: termination, safety, discrimination)
- [x] Migration 009: HR department + agents seeded in Paperclip
- [x] Slack bot multi-department routing (#hr-committee → hr-orchestrator, #cac-committee → cac-orchestrator)
- [x] Add HR to departments.json (data access, escalation rules, Slack channels)
- [x] Docker Compose: hr-orchestrator service with Qdrant, Postgres, Paperclip dependencies

### 8D — Cowork Plugin Packaging
- [x] Create scripts/package-cowork-plugins.sh (SKILL.md → plugin export with manifest.json)
- [x] Write docs/cowork-setup.md (installation guide for committee member laptops)

### 8E — Integration & E2E Tests
- [x] Unit tests: OpenClaw (task executor, vault writer, paperclip client, migration)
- [x] Unit tests: HR (agents, intent classification, graph compilation)
- [x] Unit tests: VaultWatcher routing (collection resolution per path prefix)
- [x] Unit tests: Paperclip worker dispatch (stub vs claude_sdk behavior)
- [x] Unit tests: Slack bot HR routing
- [x] Integration tests: OpenClaw dispatch loop (assign → execute → report)
- [x] Integration tests: Vault multi-department collection routing
- [x] E2E tests: Stage 8 golden path (OpenClaw, HR query, CAC regression)

**Architecture:** OpenClaw runs as Docker container (ADR-8.1) receiving task assignments from
Paperclip's WorkerManager via HTTP POST. Direct file I/O for vault writes (ADR-8.2) — simpler
than MCP, works headlessly. HR is query-only in Phase 1 (ADR-8.3) — no staging proposals due
to PII sensitivity. Shared BaseAgent extracted (ADR-8.4) for cross-department reuse. VaultWatcher
routes files to department-specific Qdrant collections via config-driven path mapping (ADR-8.5).
**Services:** 14 total (was 12, added openclaw + hr-orchestrator)
**Departments:** 2 (CAC + HR, was CAC only)
**Agents:** 8 specialists (4 CAC + 4 HR)
**Files:** 77 files changed, 4,644 lines added | **Tests:** 17 new test files
**Plan:** `docs/superpowers/plans/2026-04-03-stage8-worker-dispatch-hr.md`

## Stage 9 — Wiki RAG Knowledge Base

Implements Karpathy's "LLM Knowledge Base" pattern: raw data from Slack, documents, and
approval decisions is compiled by the LLM into a structured Obsidian wiki that compounds
institutional memory over time. Shifts from query-time RAG retrieval to ingestion-time
knowledge compilation. Agents get smarter automatically as committee history accumulates.
Department-scoped vault directories enforce data boundaries at 4 layers.

**Design Spec:** `docs/superpowers/specs/2026-04-07-stage9-wiki-rag-design.md`
**Plan:** `docs/superpowers/plans/2026-04-07-stage9-wiki-rag.md`
**Pattern:** [Karpathy llm-wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

### 9A — Vault Structure, Schema & Department Boundaries
- [x] Restructure obsidian-vault/ into department subdirectories (shared/, cac/, hr/, templates/)
- [x] Create per-department vault directories: cac/concepts/, decisions/, meeting-notes/, entities/, trends/
- [x] Create shared vault directory: shared/policies/, escalation-protocols/
- [x] Create per-department index.md with Dataview-compatible YAML frontmatter
- [x] Create per-department log.md with parseable entry format ([DATE] ingest|query|lint | description)
- [x] Create article templates (concept, decision, meeting-note, entity, escalation) with standard frontmatter
- [x] Create config/wiki_schema.json (article conventions, frontmatter schema, generator templates, lint schedule)
- [x] Update config/obsidian_watch.json with department-scoped folder→collection mapping (11 paths: shared + cac + hr)
- [x] Update config/departments.json: add `vaultPath` and `wikiCollection` to DataAccess
- [x] Update config/departments.schema.json with new fields

### 9B — Wiki Compiler Service (port 3007)
- [x] Build services/wiki-compiler/src/models.py (Pydantic v2: CompileEvent, WikiArticle, LintResult, LintReport, ArticleFrontmatter — 29 tests)
- [x] Build services/wiki-compiler/src/config.py (WikiSettings: VLLM_BASE_URL, VAULT_PATH, WIKI_SCHEMA_PATH, DEPARTMENTS_CONFIG)
- [x] Build services/wiki-compiler/src/compiler.py (core LLM compilation: event → structured markdown via langchain-openai — 9 tests)
- [x] Build services/wiki-compiler/src/dept_router.py (department routing + vault path resolution + path traversal guard — 8 tests)
- [x] Build services/wiki-compiler/src/index_manager.py (auto-maintain per-department index.md — 5 tests)
- [x] Build services/wiki-compiler/src/log_writer.py (append-only per-department log.md entries — 4 tests)
- [x] Build services/wiki-compiler/src/linker.py (backlink generation: intra-dept [[links]] + cross-refs — 5 tests)
- [x] Build services/wiki-compiler/src/main.py (FastAPI: /health, POST /compile, POST /lint — 6 tests)
- [x] Dockerfile + requirements.txt + docker-compose entry (vault :rw mount, host.docker.internal for vLLM)
- [x] Department boundary enforcement: compiler writes only to obsidian-vault/{dept_id}/ or obsidian-vault/shared/

### 9C — Article Generators
- [x] Build services/wiki-compiler/src/generators/decision.py (approved proposal → decision article — 3 tests)
- [x] Build services/wiki-compiler/src/generators/meeting.py (Slack thread digest → meeting-note — 3 tests)
- [x] Build services/wiki-compiler/src/generators/concept.py (multi-source topic → concept article)
- [x] Build services/wiki-compiler/src/generators/entity.py (facility/instrument/person → entity page)
- [x] Build services/wiki-compiler/src/generators/escalation.py (escalation event → article)
- [x] Build services/wiki-compiler/src/generators/source_summary.py (uploaded document → source summary)
- [x] Build services/wiki-compiler/src/generators/_common.py (shared helpers: slugify, confidence_from_float, parse_or_construct)

### 9D — Service Wiring
- [x] Update services/paperclip/src/services/event_router.py: add route_wiki_compile (fire-and-forget, single attempt, no retry)
- [x] Update services/rag-ingestion/src/main.py: POST to wiki-compiler after document ingestion (fire-and-forget)
- [x] Make VaultWatcher config-driven: reads obsidian_watch.json, resolves collection/doc_type/dept per path (15 new tests)
- [x] Add WIKI_COMPILER_URL env var to Paperclip and rag-ingestion docker-compose entries
- [x] Add wiki_compiler_url to Paperclip settings.py

### 9E — Linter & Health Checks
- [x] Build services/wiki-compiler/src/linter.py (WikiLinter class with aggregated LintReport — 9 tests)
- [x] Stale data detection (article updated date vs. threshold_days)
- [x] Orphan page detection (articles with no inbound [[backlinks]])
- [x] Missing concept detection ([[page]] references with no matching file)
- [x] Coverage scoring (high: 5+ sources, medium: 2-4, low: 0-1)
- [x] Write lint-report.md per department with findings and suggested actions
- [x] Wire /lint endpoint in main.py to real linter
- [ ] Contradiction detection (LLM-based — deferred to maintenance agent integration)

### 9F — Wiki Maintenance Agent
- [x] Create skills/shared/wiki-maintenance.md (SKILL.md: 9 sections per PRD §11)
- [x] Build services/wiki-compiler/src/maintenance_agent.py (MaintenanceAgent: lint + prune + gap report — 9 tests)
- [x] Pruning: archive articles older than configurable threshold (default: 12 months)
- [x] Heartbeat registration to Paperclip (fire-and-forget)
- [ ] Register wiki-maintenance-agent in Paperclip DB seed (migration)
- [ ] APScheduler weekly cron integration (deferred to integration testing)

### 9G — Testing & Validation
- [x] Unit tests: 90 wiki-compiler tests passing (models 29, compiler 9, dept_router 8, index 5, log 4, linker 5, linter 9, maintenance 9, main 6, generators 6)
- [x] VaultWatcher tests: 41 passing (26 existing + 15 new config-driven routing)
- [x] Ruff clean on all new code
- [x] Full unit test suite passes: 546 total (all existing + new wiki tests, 0 failures)
- [ ] Integration test: proposal → decision article → VaultWatcher → Qdrant (requires Docker)
- [ ] Docker Compose: wiki-compiler /health returns 200 (requires Docker)
- [ ] Performance test: compilation latency < 30s per article (requires vLLM)

## Phase 1 Closeout — Hardening, UAT + Go-Live (post-Stage 9)

> *Renamed from "Stage 10" on 2026-04-28 to free Stage 10 for the Phase 2 framework. Content is the Phase 1 deployment checklist and is independent of the numbered code-stage sequence.*

- [ ] UAT with 2–3 committee members (Slack side) — test queries, citations, edge cases
- [ ] UAT with HOD (email side) — receive proposal email, click link, approve from phone browser
- [ ] Populate alco_tracker.json with real Excel structure (tabs, columns, row labels)
- [ ] Populate departments.json with real HOD email addresses and Slack channel IDs
- [ ] Populate escalation_rules.json with real covenant thresholds
- [ ] Load test: 10 concurrent queries against cac-orchestrator
- [ ] Load test: HR orchestrator concurrent queries
- [ ] Configure OpenClaw with real Anthropic API key for CTO Agent tasks
- [ ] Connect Obsidian desktop app to obsidian-vault/ on DGX Spark
- [ ] Verify VaultWatcher: save .md in Obsidian → Qdrant updated within 60s
- [ ] Verify OpenClaw: assign skill_task → vault written → Qdrant ingested
- [ ] Run full PRD Section 14 UAT checklist (23 items)
- [ ] Security review: verify /data/mirror/:ro enforcement, JWT validation, API key rotation
- [ ] Production .env populated with all real credentials
- [ ] Deploy to DGX Spark: docker compose up -d (all 14 services)
- [ ] Monitor: Paperclip heartbeats healthy, all services responding
- [ ] Go-live

---

# Phase 2 — Department Expansion (Stages 10-19)

Phase 2 scales the system from 2 live departments (CAC, HR) to 11 by introducing a department-onboarding framework. Stage 10 builds the framework; Stages 11-19 each onboard one department in ~1.5 days using the framework's 12-step checklist.

**Reference documents (all artifacts committed 2026-04-28):**
- 📊 Org chart: `docs/diagrams/department-agent-map.drawio`
- 📋 Framework spec: `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
- 📋 Framework plan: `docs/superpowers/plans/2026-04-28-stage10-phase2-framework.md`
- 📋 Per-dept spec template: `docs/superpowers/specs/_per-dept-spec-template.md`
- 📋 Per-dept plan template: `docs/superpowers/plans/_per-dept-plan-template.md`

**Patterns adopted into Phase 2:**
- **Second brain** (Cole Medin) — `soul.md` / `user.md` / `memory.md` per agent + daily logs
- **Self-improving loop** (Luuk Alleman) — HOD approve/edit/reject mapped to rating signal → reflection engine → SKILL.md update proposals (HOD-gated)

## Stage 10 — Phase 2 Framework Infrastructure ✅ (2026-04-28)

### 10A — Schema & Config
- [x] Extended `config/departments.schema.json` with capabilityTier, crossReadAccess, agentTopology, heartbeat
- [x] Migrated `config/departments.json` (CAC + HR updated + 9 future depts at live=false)
- [x] Created `config/document_inventory.json` (53 corporate documents across 12 depts)
- [x] Created `config/document_inventory.schema.json`
- [x] Migration 010 — agent_knowledge_gaps, agent_skill_proposals, reflection_runs, agent_performance view
- [x] Validation scripts: `scripts/validate_config.py`, `scripts/validate_skills.py`

### 10B — Skills Cleanup + Frontmatter
- [x] Renamed `skills/invest/` → `skills/ic/`
- [x] Deleted `skills/ops/`
- [x] Moved `skills/shared/cfo-agent.md` → `skills/finance/cfo-agent.md` (with backcompat stub)
- [x] Created `skills/_template/` (orchestrator + 3 specialist placeholders)
- [x] Created `skills/{ib,cio,vcc,comms}/` directories

### 10C — Shared Library
- [x] `services/shared/load_memory.py` — LangGraph node for soul.md/user.md/memory.md triad
- [x] `services/shared/retrieve_context_crossread.py` — cross-dept read with graceful degradation
- [x] `services/shared/knowledge_gaps.py` — LLM self-report phrase detection
- [x] `services/shared/daily_log.py` — append interactions to vault daily-logs
- [x] `services/shared/permission_enforcement.py` — runtime skill permission checks
- [x] `services/shared/models_phase2.py` — SkillPermissions + SkillMeta Pydantic models

### 10D — Reflection Engine (port 3008)
- [x] Service scaffold: FastAPI + APScheduler nightly cron
- [x] Daily log reader + approval decisions joiner
- [x] LLM reflection via langchain-openai (JSON prompt + 3-retry parse)
- [x] Memory promotion: archive → overwrite cycle for memory.md/user.md
- [x] Pattern detection: >= 5 same-shape low-signal → agent_skill_proposals row

### 10E — Heartbeat (port 3009, default disabled)
- [x] Service scaffold: FastAPI + per-dept APScheduler
- [x] Config reader filters departments.json for heartbeat.enabled
- [x] Context gatherer stubs (Slack + SharePoint URI prefixes)
- [x] Orchestrator invocation client (POST /proactive)

### 10F — Templates
- [x] `services/_template-orchestrator/` — copy-and-fill skeleton from HR pattern
- [x] `skills/_template/` — 4 placeholder SKILL.md files

### 10G — Infrastructure
- [x] Docker compose: reflection-engine + heartbeat entries
- [x] 9 vault folder skeletons (finance, ib, ic, cio, vcc, comms, legal, risk, it)
- [x] Updated `config/obsidian_watch.json` with trends/ + daily-logs/ per dept
- [x] 9 skeleton plans (Stages 11-19) + per-dept-plan-template

**Architecture:** Phase 2 framework lets each downstream dept stage land in ~1.5 days. Catalog (departments.json + document_inventory.json) + templates (services/_template-orchestrator + skills/_template) + shared services (reflection-engine + heartbeat) + per-skill permission registry + agent_performance signal-strength view.
**Spec:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
**Plan:** `docs/superpowers/plans/2026-04-28-stage10-phase2-framework.md`

## Stage 11 — Finance Department 📋 (planned, scaffolded 2026-04-28)

First write-capable Phase 2 dept; stress-tests cross-dept read enforcement. CFO Agent + 3 specialists (reporting, treasury, MD&A). Cross-read INTO Finance from CAC, IC, Risk, CIO. Service port 3010.

**Posture:** write · **Cross-read targets (live):** Finance is read INTO by others · **Existing scaffold:** ❌ none · **Dependencies:** Stage 10
**Spec:** [`docs/superpowers/specs/2026-04-28-stage11-finance-design.md`](superpowers/specs/2026-04-28-stage11-finance-design.md)
**Plan:** [`docs/superpowers/plans/2026-04-28-stage11-finance.md`](superpowers/plans/2026-04-28-stage11-finance.md)

## Stage 12 — Risk Committee 📋 (planned, scaffolded 2026-04-28)

CRO Agent + 3 specialists (credit-risk, market-risk, operational-risk). Read-only with cross-read to CAC, CIO, Finance, Legal. Service port 3011.

**Posture:** read_only · **Cross-reads:** cac, cio, finance, legal · **Existing scaffold:** ✅ `skills/risk/` · **Dependencies:** Stage 10 + Stage 11 (Finance live)
**Spec:** [`docs/superpowers/specs/2026-04-28-stage12-risk-design.md`](superpowers/specs/2026-04-28-stage12-risk-design.md)
**Plan:** [`docs/superpowers/plans/2026-04-28-stage12-risk.md`](superpowers/plans/2026-04-28-stage12-risk.md)

## Stage 13 — Legal Department 📋 (planned, scaffolded 2026-04-28)

CLO Agent + 3 specialists (compliance, contract-review, regulatory). Read-only with **cross-read to all departments** — broadest read scope. Service port 3012.

**Posture:** read_only · **Cross-reads:** `["*"]` (all depts) · **Existing scaffold:** ✅ `skills/legal/` · **Dependencies:** Stage 10 + 11
**Spec:** [`docs/superpowers/specs/2026-04-28-stage13-legal-design.md`](superpowers/specs/2026-04-28-stage13-legal-design.md)
**Plan:** [`docs/superpowers/plans/2026-04-28-stage13-legal.md`](superpowers/plans/2026-04-28-stage13-legal.md)

## Stage 14 — IT Department 📋 (planned, scaffolded 2026-04-28)

CTO Agent + 3 specialists (devops, infrastructure, security). Read-only. Reuses existing CTO Agent identity from Stage 8 OpenClaw supervisor. Service port 3013.

**Posture:** read_only · **Cross-reads:** own + shared only · **Existing scaffold:** ✅ `skills/it/` · **Dependencies:** Stage 10 + identity-continuity migration
**Spec:** [`docs/superpowers/specs/2026-04-28-stage14-it-design.md`](superpowers/specs/2026-04-28-stage14-it-design.md)
**Plan:** [`docs/superpowers/plans/2026-04-28-stage14-it.md`](superpowers/plans/2026-04-28-stage14-it.md)

## Stage 15 — Communications (IR/PR) 📋 (planned, scaffolded 2026-04-28)

Comms Agent + 3 specialists (IR, PR, Branding). Read-only. Includes branding team (moved from HR per org chart update). Service port 3014.

**Posture:** read_only · **Cross-reads:** own + shared only · **Existing scaffold:** ❌ none · **Dependencies:** Stage 10 (Stage 11 helpful for IR fact-checks)
**Spec:** [`docs/superpowers/specs/2026-04-28-stage15-comms-design.md`](superpowers/specs/2026-04-28-stage15-comms-design.md)
**Plan:** [`docs/superpowers/plans/2026-04-28-stage15-comms.md`](superpowers/plans/2026-04-28-stage15-comms.md)

## Stage 16 — IC Committee 📋 (planned, scaffolded 2026-04-28)

IC Chair Agent + 3 specialists (due-diligence, portfolio, valuation). Read-only with cross-read to Finance, CIO, VCC, Legal. Service port 3015.

**Posture:** read_only · **Cross-reads:** finance, cio, vcc, legal · **Existing scaffold:** ✅ `skills/ic/` (renamed from `invest/` in Stage 10) · **Dependencies:** Stages 11 + 13 (CIO/VCC graceful-degrade until Stages 17/18)
**Spec:** [`docs/superpowers/specs/2026-04-28-stage16-ic-design.md`](superpowers/specs/2026-04-28-stage16-ic-design.md)
**Plan:** [`docs/superpowers/plans/2026-04-28-stage16-ic.md`](superpowers/plans/2026-04-28-stage16-ic.md)

## Stage 17 — CIO Office 📋 (planned, scaffolded 2026-04-28)

CIO Agent + 3 specialists (fund-performance, custody, PPM). Write-capable for NAV trackers via staging. Custody-agent has data-zone override (read-only on Zone 2). Service port 3016.

**Posture:** write · **Cross-reads:** finance, vcc, ic · **Existing scaffold:** ❌ none · **Dependencies:** Stage 11 (must); Stage 16 (recommended)
**Spec:** [`docs/superpowers/specs/2026-04-28-stage17-cio-design.md`](superpowers/specs/2026-04-28-stage17-cio-design.md)
**Plan:** [`docs/superpowers/plans/2026-04-28-stage17-cio.md`](superpowers/plans/2026-04-28-stage17-cio.md)

## Stage 18 — VCC Department 📋 (planned, scaffolded 2026-04-28)

VCC Head Agent + 3 specialists (client-relations, NAV/subscriptions, comms). Write-capable. PII guard on client-relations skill (`outbound_apis: []`). Service port 3017.

**Posture:** write · **Cross-reads:** cio, ic · **Existing scaffold:** ❌ none · **Dependencies:** Stage 17 (must); Stage 16 (recommended)
**Spec:** [`docs/superpowers/specs/2026-04-28-stage18-vcc-design.md`](superpowers/specs/2026-04-28-stage18-vcc-design.md)
**Plan:** [`docs/superpowers/plans/2026-04-28-stage18-vcc.md`](superpowers/plans/2026-04-28-stage18-vcc.md)

## Stage 19 — Investment Banking 📋 (planned, scaffolded 2026-04-28)

IB Agent + 3 specialists (deal-origination, structuring, syndication). Read-only; lowest-activity dept. Ships last in Phase 2. Service port 3018.

**Posture:** read_only · **Cross-reads:** own + shared only · **Existing scaffold:** ❌ none · **Dependencies:** Stage 10 only
**Spec:** [`docs/superpowers/specs/2026-04-28-stage19-ib-design.md`](superpowers/specs/2026-04-28-stage19-ib-design.md)
**Plan:** [`docs/superpowers/plans/2026-04-28-stage19-ib.md`](superpowers/plans/2026-04-28-stage19-ib.md)

---

## Phase 2 Closeout (post-Stage 19)

Once all 11 departments are live:

- [ ] All-dept E2E test: simulated 24h of cross-dept Slack chatter; reflection engine completes nightly cycle; no errors
- [ ] Lethal-trifecta audit: every skill's permissions verified against actual runtime behaviour
- [ ] Update `CLAUDE.md` Phase 2 status: "complete"
- [ ] Phase 2 retrospective; plan Phase 3 (Voyager-style novel skills, cross-agent learning, RL loop — deferred per framework spec §4.11)

**Estimated Phase 2 calendar:** ~6-8 weeks (per framework spec §7.4)
**Estimated total Phase 2 effort:** ~13.5 days code + ~3 days hardening = ~16.5 days focused work

---

## Decision gates (per framework spec §7.5)

- **After Stage 10:** verify framework end-to-end against CAC + HR (regression). If reflection engine breaks anything, fix before adding new depts.
- **After Stage 11:** verify cross-read enforcement actually works (CAC reading Finance's collection). Biggest architectural risk.
- **After Stage 16:** pause to evaluate. By then 6 of 9 depts live; remaining 3 (CIO/VCC/IB) are higher complexity. Decide: ship and reassess vs continue.
