# Corporate AI Agent System — Product Requirements Document

**Version:** 2.2  
**Date:** March 2026  
**Tooling:** Claude Code  
**Status:** Ready for Development — Phase 1  
**Changes from v2.1:** Obsidian vault integration — human-facing knowledge UI for SKILL.md files, meeting notes, and decision log · LlamaIndex vault watcher · OpenClaw MCP write access

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Decision: Single Spark + Docker](#2-architecture-decision-single-spark--docker)
3. [Data Architecture: Mirror → Stage → Approve → Sync](#3-data-architecture-mirror--stage--approve--sync)
4. [Repository Structure](#4-repository-structure)
5. [Infrastructure Layout (Single DGX Spark)](#5-infrastructure-layout-single-dgx-spark)
6. [Tech Stack](#6-tech-stack)
7. [Phase 1 Requirements — CAC Agent](#7-phase-1-requirements--cac-agent)
8. [Service Specifications](#8-service-specifications)
9. [API Contracts](#9-api-contracts)
10. [Data Models](#10-data-models)
11. [SKILL.md Specification](#11-skillmd-specification)
12. [Environment Variables](#12-environment-variables)
13. [Development Workflow with Claude Code](#13-development-workflow-with-claude-code)
14. [Testing Requirements](#14-testing-requirements)
15. [Phase 2 & 3 Scope](#15-phase-2--3-scope)
16. [Obsidian Vault Integration](#16-obsidian-vault-integration)

---

## 1. Project Overview

### Goal
Build a multi-agent AI system that reads committee Slack channels and uploaded documents, answers questions with source citations, proposes changes to Excel trackers via a staging pipeline, and requires human approval before anything touches live corporate data.

### Starting Scope (Phase 1)
- Capital Allocation & ALCO Committee (CAC) only
- **Slack** — agent ↔ committee real-time channel + cross-dept agent coordination
- **Email** — formal HOD approval notifications and escalation alerts only
- Document upload via Slack file share
- Mirror → Stage → Approve → Sync data pipeline
- Human approval gate: HOD receives email → clicks link → reviews in browser approval-ui
- Obsidian vault for human-facing SKILL.md editing, meeting notes, and decision log
- OpenClaw as Paperclip-registered coding worker

### Non-Goals (Phase 1)
- No direct writes to any corporate file or database (all writes go through approval gate)
- No other departments (Risk, Legal, IC, Ops, HR, IT)
- No fine-tuning of models
- No autonomous scheduling without human approval
- No second DGX Spark (added in Phase 3 when scaling to all 7 departments)

---

## 2. Architecture Decision: Single Spark + Docker

### One DGX Spark handles everything in Phase 1

```
Single DGX Spark (128GB unified memory)
────────────────────────────────────────────────────
[HOST] vLLM · Qwen3.5 122B-A10B @ Q8       ~110GB
[HOST] vLLM · Qwen3.5 9B (embedding)        ~10GB
────────────────────────────────────────────────────
Remaining for Docker stack:                  ~8GB ✓

[DOCKER] slack-bot            port 3003   ~200MB
[DOCKER] rag-ingestion        port 3004   ~500MB
[DOCKER] cac-orchestrator     port 3001   ~500MB
[DOCKER] sync-mirror          internal    ~100MB
[DOCKER] sync-back            internal    ~100MB
[DOCKER] approval-ui          port 4000   ~200MB
[DOCKER] email-notifier       internal    ~100MB
[DOCKER] paperclip (Node.js)  port 3100   ~300MB
[DOCKER] postgres             port 5432   ~500MB
[DOCKER] chroma               port 8003   ~1GB
[DOCKER] minio                port 9000   ~300MB
[DOCKER] gateway              port 3000   ~200MB
────────────────────────────────────────────────────
Total Docker overhead:                    ~4.1GB ✓
KV cache + headroom:                      ~3.9GB ✓
```

### Why containers, not VMs
Each service runs in its own Docker container — not a full VM. VMs waste 2–4GB RAM per instance on OS kernel overhead. Docker containers share the host kernel — isolated but lightweight.

**Exception:** vLLM runs directly on the host (not in Docker) for maximum CUDA performance. All containers call vLLM via `host.docker.internal` HTTP.

### Network
All services communicate on a single Docker bridge network.

```
vLLM Large  → http://host.docker.internal:8000/v1
vLLM Embed  → http://host.docker.internal:8002/v1
Chroma      → http://chroma:8003
Postgres    → postgres:5432
Paperclip   → http://paperclip:3100
Approval UI → http://localhost:4000  (browser on same network)
```

### How to view agent work
- **Slack** — real-time answers, citations, alerts in-thread for committee members
- **Approval UI (port 4000)** — browser dashboard showing every pending proposed change
- **Paperclip (port 3100)** — full audit trace of every agent step, cost, decision
- **Email** — HOD receives formal notification with direct link to approval-ui

### Communication Architecture — Two Layers, Two Audiences

```
┌──────────────────────────────────────────────────────────┐
│  SLACK — Real-time · Agents + Committee Members          │
│                                                          │
│  #cac-committee   Agent answers queries, posts proposals │
│  #escalations     Cross-dept alerts, CEO Agent routing   │
│  #approvals       Team visibility on pending items       │
│  #{dept}-committee  One channel per department           │
└──────────────────────────────────────────────────────────┘
         ↑↓ cross-dept escalation routing between channels
         ↑↓ CEO Agent coordinates CFO ↔ CRO ↔ CLO etc.

┌──────────────────────────────────────────────────────────┐
│  EMAIL — Formal · HOD Approval + Escalations Only        │
│                                                          │
│  New proposal notification  → HOD inbox                 │
│  Escalation alert           → HOD + CEO inbox           │
│  24h overdue reminder       → HOD inbox                 │
│  Sync confirmation          → HOD inbox (optional)      │
└──────────────────────────────────────────────────────────┘
         ↓ HOD clicks "Review Now" link in email

┌──────────────────────────────────────────────────────────┐
│  APPROVAL UI (port 4000) — Browser, no Slack needed      │
│                                                          │
│  HOD reviews diff → approve / reject / edit              │
│  Works on phone browser (email deep-link opens it)       │
│  HOD does NOT need a Slack account                       │
└──────────────────────────────────────────────────────────┘
```

**Key design principle:** Heads of Department only need email and a browser. They are never required to use Slack. Committee members and agents operate in Slack. The two worlds connect only at the approval gate.

### Second Spark
Add in Phase 3 when scaling to all 7 departments simultaneously. Offload Qwen 35B inference to Spark B at that point.

---

## 3. Data Architecture: Mirror → Stage → Approve → Sync

Agents never touch live corporate data. All changes go through a human approval gate.

### The Five Zones

```
Zone 0: Corporate Data (source of truth — external)
    ↓  sync-mirror pulls every 15 min (read-only, one-way)
Zone 1: /data/mirror/  (read-only mount — agents read here only)
    ↓  agents read Zone 1, write proposals to Zone 2
Zone 2: /data/staging/ (agent output — proposed changes only)
    ↓  human reviews diff in approval-ui (port 4000)
Zone 3: Approval Gate  (human decides: approve / reject / edit)
    ↓  approved only → sync-back writes to Zone 0
Zone 4: /data/archive/ (permanent immutable audit record)
```

**Agents are restricted to Zones 1 and 2. Docker enforces Zone 1 as read-only at the OS level.**

### Docker Volume Enforcement

```yaml
services:
  cac-orchestrator:
    volumes:
      - mirror_data:/data/mirror:ro      # :ro = read-only, Docker-enforced
      - staging_data:/data/staging:rw

  sync-mirror:
    volumes:
      - mirror_data:/data/mirror:rw      # only this service writes to mirror

  sync-back:
    volumes:
      - staging_data:/data/staging:ro
      - archive_data:/data/archive:rw
```

### Folder Structure on Host SSD

```
/data/
├── mirror/                     ← Zone 1: read-only copy of corporate
│   ├── excel/
│   │   ├── ALCO_Tracker.xlsx
│   │   └── Capital_Plan.xlsx
│   ├── documents/
│   │   ├── ALCO_Minutes_Feb2026.pdf
│   │   └── Treasury_Policy_v4.pdf
│   └── db_snapshots/
│
├── staging/                    ← Zone 2: agent proposals
│   ├── pending/                ← awaiting human review
│   ├── approved/               ← human-approved, queued for sync
│   ├── rejected/               ← rejected proposals (audit)
│   └── metadata/
│       └── manifest.json
│
└── archive/                    ← Zone 4: permanent record
    └── chg_XXXX_approved_UserY.json
```

### Change Manifest Schema

```json
{
  "id": "chg_0142",
  "created_at": "2026-03-24T10:43:00Z",
  "agent": "funding-agent",
  "triggered_by": "app_mention",
  "slack_user": "U12345678",
  "file": "ALCO_Tracker.xlsx",
  "tab": "Funding Facilities",
  "cell": "E8",
  "old_value": null,
  "new_value": "3.15",
  "source": "Slack #cac-committee | Jane Doe | 2026-03-24T10:42",
  "source_excerpt": "current net debt/EBITDA is 3.15x",
  "confidence": 0.91,
  "reasoning": "CFO update message states ratio at 3.15x. Updates covenant ratio field for SCB facility.",
  "status": "pending",
  "paperclip_ticket_id": "PPC-0142"
}
```

### Approval UI Actions (port 4000)

| Action | What happens |
|---|---|
| **Approve** | Move to `staging/approved/`. Trigger sync-back. Log approver + timestamp. |
| **Edit then Approve** | Human corrects value. Edited value (not agent value) syncs. |
| **Reject** | Move to `staging/rejected/`. Log reason. Nothing syncs. |
| **Defer** | Stay in pending. Reminder after 24h. |

### Sync Schedule

| Service | Trigger | Direction |
|---|---|---|
| sync-mirror | Every 15 min (cron) | Corporate → /data/mirror/ |
| sync-back | Event-driven (watchdog on approved/) | /data/staging/approved/ → Corporate |
| archive | After sync-back completes | Write to /data/archive/ |

---

## 4. Repository Structure

```
corporate-ai-agents/
│
├── README.md
├── PRD.md
├── AGENTS.md                       ← Claude Code session context — always paste this first
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── .env                            ← never commit
│
├── infra/
│   └── vllm/
│       ├── start-122b.sh
│       └── start-embed.sh
│
├── services/
│   ├── gateway/
│   │   ├── Dockerfile
│   │   └── src/
│   │       ├── main.py
│   │       ├── auth.py
│   │       └── router.py
│   │
│   ├── slack-bot/
│   │   ├── Dockerfile
│   │   └── src/
│   │       ├── main.py
│   │       ├── events.py           ← message_posted, file_shared, app_mention
│   │       ├── file_handler.py
│   │       └── responder.py
│   │
│   ├── rag-ingestion/
│   │   ├── Dockerfile
│   │   └── src/
│   │       ├── main.py
│   │       ├── chunker.py
│   │       ├── embedder.py
│   │       ├── chroma_store.py
│   │       ├── chat_indexer.py
│   │       └── metadata.py
│   │
│   ├── cac-orchestrator/
│   │   ├── Dockerfile
│   │   └── src/
│   │       ├── main.py
│   │       ├── graph.py            ← LangGraph StateGraph
│   │       ├── state.py            ← AgentState TypedDict
│   │       ├── router.py
│   │       ├── synthesiser.py
│   │       ├── agents/
│   │       │   ├── liquidity.py
│   │       │   ├── capital.py
│   │       │   ├── alm.py
│   │       │   ├── funding.py
│   │       │   ├── escalation.py
│   │       │   └── excel_nav.py
│   │       ├── tools/
│   │       │   ├── rag_retrieve.py
│   │       │   ├── chat_search.py
│   │       │   ├── excel_schema.py
│   │       │   └── staging_writer.py  ← writes proposals to /data/staging/pending/
│   │       └── skills/
│   │           └── loader.py
│   │
│   ├── sync-mirror/
│   │   ├── Dockerfile
│   │   └── src/
│   │       ├── main.py             ← APScheduler cron
│   │       ├── connectors/
│   │       │   ├── sharepoint.py
│   │       │   ├── smb.py
│   │       │   └── sftp.py
│   │       └── hash_check.py
│   │
│   ├── sync-back/
│   │   ├── Dockerfile
│   │   └── src/
│   │       ├── main.py             ← watchdog watcher on approved/
│   │       ├── excel_writer.py     ← openpyxl cell writes
│   │       ├── verify.py
│   │       ├── archiver.py
│   │       └── rollback.py
│   │
│   └── approval-ui/
│       ├── Dockerfile
│       └── src/
│           ├── main.py             ← FastAPI backend
│           ├── queue.py
│           ├── decisions.py
│           ├── diff.py
│           └── static/
│               └── index.html      ← vanilla HTML/JS, no framework needed
│
│   └── email-notifier/             ← HOD email notifications
│       ├── Dockerfile
│       └── src/
│           ├── main.py             ← FastAPI, receives events from approval-ui
│           ├── sender.py           ← SMTP / SendGrid / Microsoft Graph send
│           ├── templates/
│           │   ├── proposal.html   ← "New item needs your approval" email
│           │   ├── escalation.html ← "Escalation requires attention" email
│           │   ├── reminder.html   ← "3 items overdue 24h" email
│           │   └── confirmed.html  ← "Change synced successfully" email (optional)
│           └── recipients.py       ← dept → HOD email mapping
│
├── skills/
│   ├── shared/
│   │   ├── rag-retrieval.md
│   │   ├── excel-navigation.md
│   │   ├── escalation-protocol.md
│   │   ├── chat-ingestion.md
│   │   └── citation-format.md
│   └── cac/
│       ├── cfo-agent.md            ← BUILD FIRST
│       ├── liquidity-analysis.md
│       ├── capital-allocation.md
│       ├── covenant-monitoring.md
│       ├── alm-review.md
│       └── funding-facilities.md
│
├── obsidian-vault/                 ← human-facing knowledge base (Obsidian desktop)
│   ├── .obsidian/                  ← Obsidian config (gitignored)
│   ├── skills/                     ← symlinked or synced from skills/ above
│   │   ├── shared/
│   │   └── cac/
│   ├── meeting-notes/              ← ALCO minutes, committee discussions
│   │   ├── 2026-03-24-ALCO.md
│   │   └── templates/
│   │       └── meeting-note.md     ← standard note template
│   ├── decisions/                  ← key committee decisions + rationale
│   │   ├── 2026-03-CAC-decisions.md
│   │   └── templates/
│   │       └── decision-log.md
│   ├── policies/                   ← policy reference notes linking to source docs
│   └── index.md                    ← vault home page with links to all areas
│
├── config/
│   ├── excel_schema/
│   │   └── alco_tracker.json       ← populate with your real Excel structure
│   ├── dept_channels.json
│   ├── hod_emails.json             ← dept → HOD email mapping
│   ├── obsidian_watch.json         ← vault folders watched by LlamaIndex
│   └── escalation_rules.json
│
├── migrations/
│
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
        ├── sample_alco_minutes.pdf
        └── sample_alco_tracker.xlsx
```

### AGENTS.md (place at repo root — paste into Claude Code at session start)

```markdown
# AGENTS.md

## Project
Corporate AI agent system · Capital Allocation & ALCO Committee · Phase 1
Single DGX Spark · On-premise · Slack + Email dual layer · Human approval gate

## Core Rule — Data Safety
Agents NEVER write to /data/mirror/ or any corporate system directly.
Agents write ONLY to /data/staging/pending/ via staging_writer.py.
All changes require human approval in approval-ui (port 4000) before sync.
Docker enforces /data/mirror/ as :ro (read-only) inside agent containers.

## Communication Layers
SLACK       → agents ↔ committee members, cross-dept agent coordination
EMAIL       → HOD formal approval notifications and escalation alerts ONLY
              HODs do NOT need Slack — email + browser is sufficient
APPROVAL UI → browser, HOD clicks email link → reviews diff → decides
OBSIDIAN    → human-facing knowledge UI for SKILL.md files, meeting notes,
              decision log. Desktop app on team lead laptop.
              Agents never query Obsidian — they query Chroma.
              Obsidian vault is ingested INTO Chroma by LlamaIndex watcher.

## Services
- slack-bot        port 3003  Slack Events API listener
- rag-ingestion    port 3004  Document + message ingestion
- cac-orchestrator port 3001  LangGraph CAC agent graph
- sync-mirror      internal   Pulls corporate data to /data/mirror/ every 15min
- sync-back        internal   Writes approved staging changes to corporate
- approval-ui      port 4000  Human review dashboard (browser)
- email-notifier   internal   HOD email notifications (proposals + escalations)
- paperclip        port 3100  Agent orchestration shell (Node.js)
- gateway          port 3000  API gateway

## LLM (on host, NOT in Docker)
- Qwen3.5 122B Q8: http://host.docker.internal:8000/v1  (all reasoning)
- Qwen3.5 9B embed: http://host.docker.internal:8002/v1 (embeddings only)

## Data Zones
Zone 0  Corporate (never agent-accessible)
Zone 1  /data/mirror/   read-only mount for all agent containers
Zone 2  /data/staging/  agent writes here — pending/ approved/ rejected/
Zone 3  Approval gate   human decides in approval-ui (reached via email link)
Zone 4  /data/archive/  permanent audit + sync back to corporate

## Build Order  →  See PRD.md Section 13
```

---

## 5. Infrastructure Layout (Single DGX Spark)

### vLLM Launch Scripts

**`infra/vllm/start-122b.sh`**
```bash
#!/bin/bash
vllm serve Qwen/Qwen3.5-122B-A10B \
  --port 8000 \
  --quantization fp8 \
  --tensor-parallel-size 1 \
  --max-model-len 131072 \
  --reasoning-parser qwen3 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --served-model-name qwen-large \
  --gpu-memory-utilization 0.88
```

**`infra/vllm/start-embed.sh`**
```bash
#!/bin/bash
vllm serve Qwen/Qwen3.5-9B \
  --port 8002 \
  --task embed \
  --max-model-len 8192 \
  --served-model-name qwen-embed \
  --gpu-memory-utilization 0.08
```

### docker-compose.yml (key sections)

```yaml
version: "3.9"

networks:
  agent-net:
    driver: bridge

volumes:
  mirror_data:
    driver: local
    driver_opts: { type: none, o: bind, device: /data/mirror }
  staging_data:
    driver: local
    driver_opts: { type: none, o: bind, device: /data/staging }
  archive_data:
    driver: local
    driver_opts: { type: none, o: bind, device: /data/archive }
  chroma_data:
  postgres_data:
  minio_data:

services:
  cac-orchestrator:
    build: ./services/cac-orchestrator
    ports: ["3001:3001"]
    volumes:
      - mirror_data:/data/mirror:ro      # READ-ONLY — Docker enforced
      - staging_data:/data/staging:rw
    extra_hosts: ["host.docker.internal:host-gateway"]
    networks: [agent-net]

  sync-mirror:
    build: ./services/sync-mirror
    volumes:
      - mirror_data:/data/mirror:rw      # ONLY this service writes mirror
    networks: [agent-net]

  sync-back:
    build: ./services/sync-back
    volumes:
      - staging_data:/data/staging:ro
      - archive_data:/data/archive:rw
    networks: [agent-net]

  approval-ui:
    build: ./services/approval-ui
    ports: ["4000:4000"]
    volumes:
      - staging_data:/data/staging:rw
    networks: [agent-net]
```

---

## 6. Tech Stack

| Component | Technology |
|---|---|
| LLM inference | vLLM 0.7+ (host) |
| Agent framework | LangGraph 0.2+ |
| RAG | LlamaIndex 0.11+ |
| Vector store | Chroma 0.5+ |
| Chat platform | Slack Bolt (Python) |
| Approval UI | FastAPI + vanilla HTML |
| Email notifications | smtplib / Microsoft Graph Mail API / SendGrid |
| Knowledge UI | Obsidian (desktop, team lead laptop) |
| Vault watcher | LlamaIndex FileSystemEventHandler (watchdog) |
| Mirror sync | rclone / rsync + Python (APScheduler) |
| Staging watcher | watchdog 4.0+ |
| Excel write | openpyxl 3.1+ |
| API services | FastAPI + Uvicorn |
| Database | PostgreSQL 16 |
| Document store | MinIO |
| Container orchestration | Docker Compose |
| Orchestration shell | Paperclip (Node.js 20) |
| Individual execution | Claude Cowork (desktop) |
| Coding worker | OpenClaw (Paperclip-registered) |

### Key Python Libraries
```
langgraph>=0.2.0
langgraph-checkpoint-postgres>=0.1.0
langchain-openai>=0.1.0
llama-index>=0.11.0
chromadb>=0.5.0
slack-bolt>=1.18.0
fastapi>=0.111.0
uvicorn>=0.30.0
openpyxl>=3.1.0
watchdog>=4.0.0
apscheduler>=3.10.0
jinja2>=3.1.0             # email HTML templates
sendgrid>=6.11.0          # if using SendGrid (optional — smtplib works too)
pydantic>=2.0.0
psycopg2-binary>=2.9.0
python-dotenv>=1.0.0
httpx>=0.27.0
pytest>=8.0.0
```

---

## 7. Phase 1 Requirements — CAC Agent

### Functional Requirements

#### FR-01: Slack Message Ingestion
- Listen to all messages in `#cac-committee` via Slack Events API (Bolt SDK)
- Every message stored in Chroma with metadata: `dept`, `source=slack`, `author`, `timestamp`, `channel_id`
- Ingestion latency < 5 seconds
- `file_shared` events trigger automatic file download + ingestion
- SHA-256 hash check prevents duplicate ingestion

#### FR-02: Document Ingestion
- Supported: PDF, XLSX, DOCX, TXT, MD
- Chunked at 512 tokens / 128 overlap
- Metadata: `dept`, `doc_type`, `filename`, `upload_date`, `uploader_slack_id`, `page_number`
- Searchable within 60 seconds of file share

#### FR-03: Query Handling
- `@agent [question]` triggers pipeline
- ACK within 2 seconds (typing indicator)
- Thread reply within 30 seconds

#### FR-04: Response Format
- Natural language answer (≥ 2 paragraphs)
- Citations: `[Source: {filename} | {date} | p.{page}]`
- Excel navigation: `📊 ALCO Tracker → Tab: {tab} → Row {n}: {label} → Column {col}`
- Confidence: `High / Medium / Low`
- Never hallucinate — state explicitly if not found

#### FR-05: Staging Proposals
- When agent confidence ≥ 0.85 that a cell value should change, generate a staging proposal
- Write to `/data/staging/pending/` with full manifest entry
- Create Paperclip ticket
- Notify `#approvals` Slack channel

#### FR-06: Escalation Detection
- Escalation Agent checks every response for breach signals
- Configurable in `config/escalation_rules.json`
- On trigger: post to `#escalations` + create Paperclip ticket
- Default triggers: covenant ratio within 10% of threshold, capital request exceeds delegation, liquidity below minimum

#### FR-07: Approval Gate
- approval-ui shows: file, tab, cell, old value, new value, source, reasoning, confidence
- Four actions: Approve / Edit then Approve / Reject / Defer
- All decisions logged to Postgres with approver ID + timestamp

#### FR-08: Sync Back
- sync-back watches `staging/approved/` via watchdog
- Write to corporate Excel via openpyxl or SharePoint API
- Verify write, then archive
- On failure: rollback + alert to `#escalations`

#### FR-09: Mirror Sync
- sync-mirror runs every 15 min via APScheduler
- One-way pull only — never writes back to corporate
- SHA-256 hash: only download changed files

#### FR-10: Audit Trail
- All tables append-only (no DELETE in application code)
- Every `app_mention` + every staging proposal → Paperclip ticket
- `agent_interactions`, `staging_proposals`, `approval_decisions`, `sync_log` tables in Postgres

#### FR-11: Email Notifications (HOD Approval Layer)
- When a staging proposal is created, `email-notifier` MUST send an email to the mapped HOD for that department within 60 seconds
- When an escalation fires (any severity), email MUST be sent to: dept HOD + CEO email
- When a proposal has been pending > 24h with no decision, a reminder email MUST be sent
- Email MUST contain a single "Review Now" button that deep-links to `http://{APPROVAL_UI_HOST}/queue/{proposal_id}`
- Email MUST include: file name, tab, cell, proposed value, agent confidence score, source excerpt
- HODs do NOT need a Slack account — email + browser approval-ui is their complete interface
- Sync confirmation email (optional, configurable): sent to HOD after approved change is written to corporate
- All emails sent logged to `email_log` Postgres table with: recipient, event_type, proposal_id, sent_at, delivery_status

**Email trigger mapping:**

| Event | Recipients | Template |
|---|---|---|
| New staging proposal | Dept HOD | `proposal.html` |
| Escalation (any severity) | Dept HOD + CEO | `escalation.html` |
| Proposal pending > 24h | Dept HOD | `reminder.html` |
| Sync confirmed (optional) | Dept HOD | `confirmed.html` |

#### FR-12: Obsidian Vault (Knowledge Layer)
- An Obsidian vault MUST be maintained as the human-facing UI for all SKILL.md files, meeting notes, and decision logs
- The vault lives on the team lead's laptop. It is NOT hosted on the DGX Spark
- The vault folder (`obsidian-vault/`) MUST be accessible to the DGX Spark via network share or git sync so LlamaIndex can watch it
- LlamaIndex MUST watch the vault for file changes (using `watchdog` in `rag-ingestion`) and re-ingest modified `.md` files into Chroma within 60 seconds of a save
- Vault changes MUST be ingested into the `cac_knowledge` Chroma collection (separate from `cac_docs` and `cac_chat`)
- OpenClaw MUST have write access to the vault via MCP — when CTO Agent assigns a SKILL.md task, OpenClaw writes directly into the vault, not the git repo directly
- Agents NEVER query the Obsidian vault directly — they query Chroma. Obsidian is upstream of Chroma, not a replacement
- The vault MUST use bidirectional `[[links]]` between SKILL.md files so the knowledge graph is navigable (e.g. `cfo-agent.md` links to `[[covenant-monitoring]]`)
- Meeting notes written in the vault MUST follow the standard template at `obsidian-vault/meeting-notes/templates/meeting-note.md`
- Decision logs MUST follow the standard template at `obsidian-vault/decisions/templates/decision-log.md`

### Non-Functional Requirements

| Requirement | Target |
|---|---|
| Query response time p95 | < 30 seconds |
| Slack ACK time | < 2 seconds |
| Document ingestion | < 60 seconds |
| Chroma search p95 | < 500ms |
| Mirror sync | Every 15 minutes |
| Sync-back after approval | < 60 seconds |
| Uptime | 99% business hours |
| Data residency | 100% on-premise |
| Max concurrent queries | 10 |

---

## 8. Service Specifications

### 8.1 slack-bot
ACK every Slack event immediately. Process async after ACK.
```python
@app.event("message")       # index to Chroma
@app.event("file_shared")   # download → rag-ingestion
@app.event("app_mention")   # @agent → cac-orchestrator → thread reply
```

### 8.2 rag-ingestion
```
POST /ingest/document   — file_path, dept, doc_type, metadata
POST /ingest/message    — Slack message object
GET  /health
```
Pipeline: `file → LlamaIndex parse → chunk(512/128) → embed(vLLM:8002) → Chroma`

Collections:
```
cac_docs        — CAC documents (PDF/XLSX/DOCX from Slack uploads)
cac_chat        — CAC Slack messages
cac_knowledge   — Obsidian vault .md files (skills, notes, decisions)
shared_policies — cross-dept policies
```

**Obsidian vault watcher** (runs inside rag-ingestion as a background thread):
```python
# Watches the vault folder for .md file changes via watchdog
# Re-ingests changed files into cac_knowledge collection within 60s
class VaultWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.md'):
            ingest_vault_file(event.src_path, collection='cac_knowledge')

    def on_created(self, event):
        if event.src_path.endswith('.md'):
            ingest_vault_file(event.src_path, collection='cac_knowledge')
```

Vault path configured via `OBSIDIAN_VAULT_PATH` env var (network mount or local sync folder).

### 8.3 cac-orchestrator
```
POST /query       — query, user_id, channel, thread_ts
GET  /health
GET  /heartbeat   — Paperclip heartbeat endpoint
```

**LangGraph graph:**
```
START
  → classify_intent        (Qwen 122B)
  → retrieve_context       (Chroma: cac_docs + cac_chat + cac_knowledge,
                            top-8, min 0.70)
  → [parallel fan-out]
      → liquidity_agent    (conditional)
      → capital_agent      (conditional)
      → alm_agent          (conditional)
      → funding_agent      (conditional)
  → escalation_check       (always)
  → excel_navigator        (always)
  → staging_writer         (if confidence ≥ 0.85)
  → synthesise_response    (Qwen 122B)
  → create_paperclip_ticket
END
```

Checkpointer: `PostgresSaver` — state key: `(user_id, channel)`

### 8.4 sync-mirror
Cron-based, no HTTP endpoint.
```python
# Every 15 min via APScheduler
def sync_job():
    for source in config.sources:      # SharePoint / SMB / SFTP
        changed = source.diff_hashes()
        source.download(changed, MIRROR_PATH)
```

### 8.5 approval-ui (port 4000)
```
GET  /queue              — list pending proposals
GET  /queue/{id}         — single proposal + diff
POST /queue/{id}/approve — approve (optional edited_value)
POST /queue/{id}/reject  — reject with reason
POST /queue/{id}/defer   — defer 24h
GET  /history
```

On approve: move to `approved/`, update manifest, POST to sync-back trigger, log to Postgres, notify `#approvals`.

### 8.6 sync-back
watchdog watches `staging/approved/`. On new file:
```python
def on_approved(file_path):
    manifest = read_manifest(file_path)
    success = write_to_corporate(manifest)   # openpyxl or SharePoint API
    if success:
        verify_write(manifest)
        archive(manifest)
        # Trigger confirmation email (if SEND_CONFIRMATION_EMAIL=true)
        email_notifier.notify_confirmed(manifest)
    else:
        rollback(manifest)
        alert_escalations(manifest)
```

### 8.7 email-notifier

Lightweight FastAPI service. Receives event POSTs from `approval-ui` and `cac-orchestrator`. Sends formatted HTML emails via SMTP or Microsoft Graph Mail API.

```
POST /notify/proposal     — new staging proposal → email dept HOD
POST /notify/escalation   — escalation fired → email HOD + CEO
POST /notify/reminder     — 24h overdue check → reminder to HOD
POST /notify/confirmed    — sync succeeded → confirmation to HOD (optional)
GET  /health
```

**Recipient mapping** (`config/hod_emails.json`):
```json
{
  "cac":    { "hod": "cfo@company.com",   "dept_name": "Capital & ALCO" },
  "risk":   { "hod": "cro@company.com",   "dept_name": "Risk Committee" },
  "legal":  { "hod": "clo@company.com",   "dept_name": "Legal & Compliance" },
  "invest": { "hod": "cio@company.com",   "dept_name": "Investment Committee" },
  "ceo":    { "hod": "ceo@company.com",   "dept_name": "Executive" }
}
```

**Email template — proposal.html (key content):**
```
Subject: [Action Required] New AI Proposal — {file} · {dept_name}

{agent_name} has proposed a change that requires your approval.

File:       ALCO_Tracker.xlsx
Tab:        Funding Facilities
Cell:       E8
Old value:  (empty)
New value:  3.15
Confidence: 91%

Source: "current net debt/EBITDA is 3.15x"
— Jane Doe · #cac-committee · 10:42 today

[ Review Now → ]   http://{APPROVAL_UI_HOST}/queue/{proposal_id}

This link opens the review dashboard in your browser.
No Slack account required.
```

**24h reminder job** runs via APScheduler inside email-notifier:
```python
# Every hour, check for proposals pending > 24h
def reminder_job():
    overdue = db.query_overdue_proposals(hours=24)
    for proposal in overdue:
        if not already_reminded_today(proposal.id):
            send_reminder(proposal)
```

**Delivery:** All sent emails logged to `email_log` table. On SMTP failure: retry 3× with exponential backoff, then log error and alert `#escalations` Slack channel.

### 8.8 Paperclip
Port 3100. Register:
```
CFO Agent  → http://localhost:3001/heartbeat
OpenClaw   → Paperclip worker, CTO Agent supervisor
```

Post ticket on every query completion + every staging proposal.

On approve in `approval-ui`: trigger both sync-back AND `email-notifier POST /notify/confirmed`.  
On escalation in `cac-orchestrator`: trigger both Slack `#escalations` AND `email-notifier POST /notify/escalation`.

### 8.9 Claude Cowork (per committee member laptop)
Not a Docker service — installed on individual macOS/Windows laptops.

Uses: Update ALCO Excel from agent navigation pointer · Draft pre-brief Word doc · Format board paper · Generate PDF summaries.

Package `skills/cac/*.md` as Cowork plugins so CAC knowledge is auto-injected.

### 8.10 OpenClaw (Paperclip worker)
Not a Docker service — registered via Paperclip HTTP heartbeat under CTO Agent.

Uses: Build new SKILL.md files · Maintain LangGraph codebase · Write pipeline scripts · Scaffold Phase 2 department agents.

IT/dev team only. Committee members do not interact with it.

---

## 9. API Contracts

### Query Response
```json
{
  "answer": "Based on the ALCO minutes from 12 February 2026...",
  "sources": [
    {
      "type": "document",
      "filename": "ALCO_Minutes_Feb2026.pdf",
      "page": 4,
      "date": "2026-02-12",
      "uploader": "John Smith",
      "excerpt": "covenant threshold agreed at 3.5x",
      "relevance_score": 0.94
    }
  ],
  "excel_nav": "ALCO Tracker → Tab: Funding Facilities → Row 8 → Column E: Covenant Threshold",
  "staging_proposal_id": "chg_0142",
  "escalation_triggered": false,
  "confidence": "High",
  "processing_time_ms": 4231
}
```

---

## 10. Data Models

### Postgres Schema
```sql
CREATE TABLE agent_interactions (
  id                   BIGSERIAL PRIMARY KEY,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  user_id              VARCHAR(50) NOT NULL,
  channel              VARCHAR(100) NOT NULL,
  thread_ts            VARCHAR(50),
  query                TEXT NOT NULL,
  intent               VARCHAR(50),
  response             TEXT,
  sources_count        INT,
  escalation           BOOLEAN DEFAULT FALSE,
  staging_proposal_id  VARCHAR(50),
  confidence           VARCHAR(10),
  processing_ms        INT,
  paperclip_ticket_id  VARCHAR(50)
);

CREATE TABLE staging_proposals (
  id              VARCHAR(50) PRIMARY KEY,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  agent           VARCHAR(100),
  file            VARCHAR(500),
  tab             VARCHAR(100),
  cell            VARCHAR(20),
  old_value       TEXT,
  new_value       TEXT,
  source          TEXT,
  confidence      NUMERIC(4,2),
  reasoning       TEXT,
  status          VARCHAR(20) DEFAULT 'pending',
  interaction_id  BIGINT REFERENCES agent_interactions(id)
);

CREATE TABLE approval_decisions (
  id               BIGSERIAL PRIMARY KEY,
  decided_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  proposal_id      VARCHAR(50) REFERENCES staging_proposals(id),
  decision         VARCHAR(20) NOT NULL,
  decided_by       VARCHAR(100) NOT NULL,
  edited_value     TEXT,
  rejection_reason TEXT,
  synced_at        TIMESTAMPTZ,
  sync_verified    BOOLEAN
);

CREATE TABLE sync_log (
  id              BIGSERIAL PRIMARY KEY,
  synced_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  direction       VARCHAR(10) NOT NULL,
  files_updated   INT,
  files_checked   INT,
  duration_ms     INT,
  status          VARCHAR(20),
  error           TEXT
);

CREATE TABLE ingested_documents (
  id                BIGSERIAL PRIMARY KEY,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  filename          VARCHAR(500) NOT NULL,
  dept              VARCHAR(50),
  doc_type          VARCHAR(100),
  uploader_id       VARCHAR(50),
  channel           VARCHAR(100),
  chunks_count      INT,
  chroma_collection VARCHAR(100),
  file_hash         VARCHAR(64) UNIQUE
);

CREATE TABLE escalations (
  id                  BIGSERIAL PRIMARY KEY,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  interaction_id      BIGINT REFERENCES agent_interactions(id),
  severity            VARCHAR(20),
  trigger_type        VARCHAR(100),
  detail              TEXT,
  paperclip_ticket_id VARCHAR(50),
  resolved_at         TIMESTAMPTZ,
  resolved_by         VARCHAR(50)
);

CREATE TABLE email_log (
  id              BIGSERIAL PRIMARY KEY,
  sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  recipient       VARCHAR(200) NOT NULL,
  event_type      VARCHAR(50) NOT NULL,  -- proposal/escalation/reminder/confirmed
  proposal_id     VARCHAR(50),
  dept            VARCHAR(50),
  subject         TEXT,
  delivery_status VARCHAR(20),           -- sent/failed/retrying
  error           TEXT,
  retry_count     INT DEFAULT 0
);
```

---

## 11. SKILL.md Specification

### Format Standard
```markdown
---
name: [skill-name]
agent: [agent-name]
dept: [department]
version: 1.0
---

## Mandate
[What this agent owns. What it does NOT own.]

## Tone & Style
[Formal. Cite sources. Never speculate. Max length. Format.]

## Domain Knowledge
[Key terms, thresholds, ratios, policy refs. Quantitative and specific.]

## Retrieval Instructions
[Collections to search. Metadata filters. Min relevance score.]

## Staging Proposal Rules
[When to propose. Minimum confidence: 0.85. Evidence requirements.]

## Excel Navigation
[Tabs, rows, columns. Navigation format template.]

## Escalation Triggers
[Quantitative: "ratio > 3.2x" not "ratio is high".]

## Output Format
[Required sections in every response.]

## Hard Rules
[What this agent must NEVER do.]
```

### Build Priority
1. `skills/shared/escalation-protocol.md`
2. `skills/shared/citation-format.md`
3. `skills/cac/cfo-agent.md` ← start here
4. `skills/cac/covenant-monitoring.md`
5. `skills/cac/liquidity-analysis.md`
6. `skills/cac/capital-allocation.md`
7. `skills/cac/alm-review.md`
8. `skills/cac/funding-facilities.md`
9. `skills/shared/excel-navigation.md`
10. `skills/shared/rag-retrieval.md`

---

## 12. Environment Variables

### `.env.example`
```bash
# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
CAC_CHANNEL_ID=C0123456789
APPROVALS_CHANNEL_ID=C1111111111
ESCALATIONS_CHANNEL_ID=C9876543210

# vLLM (on host)
VLLM_LARGE_URL=http://host.docker.internal:8000/v1
VLLM_EMBED_URL=http://host.docker.internal:8002/v1
VLLM_LARGE_MODEL=qwen-large
VLLM_EMBED_MODEL=qwen-embed

# Chroma
CHROMA_HOST=chroma
CHROMA_PORT=8003

# Postgres
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=corporate_agents
POSTGRES_USER=agents
POSTGRES_PASSWORD=changeme

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=changeme
MINIO_BUCKET=raw-documents

# Paperclip
PAPERCLIP_URL=http://paperclip:3100
PAPERCLIP_API_KEY=...

# Mirror sync — choose one source
MIRROR_SOURCE=sharepoint              # sharepoint | smb | sftp
MIRROR_SYNC_INTERVAL_MINUTES=15

# SharePoint
SHAREPOINT_TENANT_ID=...
SHAREPOINT_CLIENT_ID=...
SHAREPOINT_CLIENT_SECRET=...
SHAREPOINT_SITE_URL=https://yourcompany.sharepoint.com/sites/cac

# SMB (if using network share)
SMB_HOST=192.168.1.50
SMB_SHARE=FinanceData
SMB_USERNAME=svc_mirror
SMB_PASSWORD=...

# Obsidian Vault
OBSIDIAN_VAULT_PATH=/mnt/obsidian-vault       # network mount path on DGX Spark
OBSIDIAN_WATCH_ENABLED=true
OBSIDIAN_CHROMA_COLLECTION=cac_knowledge
OBSIDIAN_INGEST_DELAY_SECONDS=5               # debounce: wait 5s after last save before ingesting

# Email Notifier
EMAIL_PROVIDER=smtp                   # smtp | sendgrid | msgraph
APPROVAL_UI_HOST=http://192.168.1.10:4000  # used in email deep-links

# SMTP (Exchange / any SMTP server)
SMTP_HOST=mail.company.com
SMTP_PORT=587
SMTP_USER=noreply@company.com
SMTP_PASSWORD=...
SMTP_USE_TLS=true
EMAIL_FROM=CAC AI Agent <noreply@company.com>

# SendGrid (alternative)
SENDGRID_API_KEY=SG....

# Microsoft Graph Mail API (alternative — uses same app reg as SharePoint)
# Reuses SHAREPOINT_TENANT_ID + SHAREPOINT_CLIENT_ID + SHAREPOINT_CLIENT_SECRET
MSGRAPH_SENDER_EMAIL=noreply@company.com

# HOD email config (also in config/hod_emails.json)
CEO_EMAIL=ceo@company.com
CAC_HOD_EMAIL=cfo@company.com

# Email feature flags
SEND_PROPOSAL_EMAIL=true
SEND_ESCALATION_EMAIL=true
SEND_REMINDER_EMAIL=true
SEND_CONFIRMATION_EMAIL=false         # optional — set true if HODs want it
REMINDER_AFTER_HOURS=24

# Staging paths
STAGING_PATH=/data/staging
MIRROR_PATH=/data/mirror
ARCHIVE_PATH=/data/archive
PROPOSAL_CONFIDENCE_THRESHOLD=0.85

# Agent config
RAG_TOP_K=8
RAG_MIN_RELEVANCE=0.70
CHUNK_SIZE=512
CHUNK_OVERLAP=128
MAX_QUERY_TOKENS=32768
RESPONSE_TIMEOUT_SECONDS=30
SKILLS_DIR=/app/skills

# Environment
ENV=production
LOG_LEVEL=INFO
```

---

## 13. Development Workflow with Claude Code

### Build Order

```
Week 1 — Infrastructure
  □ Run infra/vllm/start-122b.sh on DGX Spark host
  □ Run infra/vllm/start-embed.sh
  □ curl http://localhost:8000/v1/models — verify both endpoints
  □ Create /data/mirror/ /data/staging/ /data/archive/ on host SSD
  □ Write docker-compose.yml — start with postgres + chroma + minio
  □ docker compose up postgres chroma minio — verify healthy

Week 2 — Mirror + RAG
  □ Build sync-mirror (start with SMB or SFTP connector)
  □ Test: run sync manually, verify /data/mirror/ populated
  □ Build rag-ingestion (chunker + embedder + chroma_store)
  □ Test: ingest a PDF, verify chunks in Chroma
  □ Build chat_indexer
  □ Test: index a fake message, verify searchable
  □ Confirm: try writing to /data/mirror/ from inside container — must fail (:ro)

Week 3 — Slack Bot
  □ Create Slack App (permissions: channels:history, files:read,
    chat:write, app_mentions:read)
  □ Add bot to #cac-committee test channel
  □ Build slack-bot (events + file_handler + responder)
  □ Test: post message → Chroma indexed
  □ Test: share file → ingestion triggers
  □ Test: @agent hello → threaded reply

Week 4 — CAC Orchestrator (core graph)
  □ Write AgentState
  □ Build graph.py skeleton — stub all nodes
  □ Implement classify_intent (Qwen 122B)
  □ Implement retrieve_context (Chroma)
  □ Implement funding_agent (first specialist)
  □ Implement synthesise_response
  □ Wire end-to-end: POST /query → structured response
  □ Load SKILL.md via skills/loader.py

Week 5 — All Agents + Staging Writer
  □ Implement liquidity, capital, alm agents
  □ Implement escalation_check + Slack #escalations post
  □ Implement excel_navigator (load alco_tracker.json)
  □ Build staging_writer.py — write proposals to /data/staging/pending/
  □ Write manifest.json with correct schema
  □ Connect escalation_check → POST email-notifier /notify/escalation (stub ok for now)

Week 6 — Approval UI + Sync Back + Email Notifier + Obsidian
  □ Build approval-ui (FastAPI + index.html diff view)
  □ Build sync-back (watchdog + openpyxl writer + archiver)
  □ Test full loop: agent proposes → UI diff → approve → Excel updated
  □ Test rejection: verify staging/rejected/ populated, nothing syncs
  □ Test rollback: simulate write failure → verify alert fires
  □ Build email-notifier service (sender.py + 4 HTML templates)
  □ Configure hod_emails.json with real HOD email addresses
  □ Connect approval-ui → POST email-notifier /notify/proposal on new pending item
  □ Connect approval-ui → POST email-notifier /notify/confirmed on approval
  □ Test: create a staging proposal → verify HOD receives email within 60s
  □ Test: click "Review Now" link in email → verify opens correct proposal in approval-ui
  □ Test: approve from email link → verify sync fires + confirmation email (if enabled)
  □ Test: trigger escalation → verify HOD + CEO both receive email
  □ Build 24h reminder APScheduler job in email-notifier
  □ Test: manually age a proposal > 24h → verify reminder fires
  □ Test: SMTP failure → verify retry logic + #escalations Slack alert
  □ Set up Obsidian on team lead laptop — install app, point at obsidian-vault/ folder
  □ Mount obsidian-vault/ as network share accessible to DGX Spark at OBSIDIAN_VAULT_PATH
  □ Build VaultWatcher in rag-ingestion — watchdog on OBSIDIAN_VAULT_PATH
  □ Test: save a .md file in Obsidian → verify chunk appears in Chroma cac_knowledge within 60s
  □ Configure OpenClaw MCP connection to Obsidian vault
  □ Test: ask CTO Agent to draft a skill file → OpenClaw writes to vault → Chroma updated
  □ Create meeting note and decision log templates in vault
  □ Write index.md vault home page with links to all skill areas

Week 7 — Paperclip + Integration
  □ Install Paperclip, configure Postgres
  □ Register CFO Agent + OpenClaw
  □ Connect cac-orchestrator to post Paperclip tickets
  □ Full end-to-end: @agent → answer → staging proposal → HOD email → approve → sync → archive
  □ Verify email deep-link opens correct proposal (not just the queue root)
  □ Write all 10 SKILL.md files
  □ Write integration tests

Week 8 — UAT + Go-Live
  □ UAT with 2–3 committee members (Slack side)
  □ UAT with HOD (email side): receive proposal email, click link, approve from phone browser
  □ Populate alco_tracker.json with real Excel structure
  □ Populate hod_emails.json with all real HOD addresses
  □ Load test: 10 concurrent queries
  □ Package Cowork plugins from SKILL.md files
  □ Configure OpenClaw in Paperclip for CTO Agent
  □ Go-live
```

### Claude Code Tips

1. **Always start sessions by pasting AGENTS.md** — gives Claude Code full context without repeating the PRD
2. **Build one service per session** — do not mix `sync-mirror` and `sync-back` in the same session
3. **`staging_writer.py` is the critical path** — build and test it before connecting approval-ui; a malformed manifest breaks the whole approval flow
4. **Populate `alco_tracker.json` before Week 5** — without real tab/column names the Excel Navigator gives useless output. Provide Claude Code with a screenshot or list of your actual tracker structure
5. **Test the `:ro` volume mount early** — confirm agents cannot write to `/data/mirror/` before building Week 5 staging logic
6. **`hod_emails.json` must have real addresses before Week 6** — ask Claude Code to build `email-notifier` with a dev mode flag (`EMAIL_DRY_RUN=true`) that logs emails to console instead of sending, so you can test the full flow without spamming HODs
7. **Test the email deep-link on mobile** — HODs will often open approval emails on their phone. Make sure the approval-ui renders correctly on a small screen before go-live. Ask Claude Code to add basic responsive CSS to `index.html`
8. **Obsidian vault watcher needs debounce** — Obsidian saves files frequently as you type. Set `OBSIDIAN_INGEST_DELAY_SECONDS=5` so the watcher waits 5 seconds after the last write event before triggering ingestion, otherwise you'll create duplicate partial chunks mid-sentence
9. **OpenClaw + Obsidian MCP: test on a dummy vault first** — before pointing OpenClaw at the real skills vault, test write access on a throwaway folder to confirm MCP permissions are scoped correctly
10. **Ask Claude Code to write tests alongside each component** — not at the end

---

## 14. Testing Requirements

### Unit Tests
```
test_chunker.py           — correct chunk size + overlap
test_embedder.py          — correct vector dimensions
test_router.py            — intent classification routes correctly
test_excel_nav.py         — maps to correct tab/row/col
test_escalation.py        — breach keywords trigger flag
test_staging_writer.py    — valid manifest.json written to pending/
test_approval_queue.py    — pending proposals load correctly
test_sync_back.py         — approved file triggers Excel write
test_hash_check.py        — duplicate file not re-ingested
test_rollback.py          — failed write triggers alert, no archive
test_email_sender.py      — correct template rendered per event type
test_email_recipients.py  — hod_emails.json routes to correct HOD per dept
test_email_reminder.py    — overdue proposals trigger reminder after 24h
test_email_deeplink.py    — deep-link URL in email resolves to correct proposal_id
test_vault_watcher.py     — .md file save → chunk in Chroma cac_knowledge within 60s
test_vault_debounce.py    — rapid saves trigger only one ingest (not one per keystroke)
test_vault_dedup.py       — unchanged .md file re-save does not create duplicate chunks
```

### Integration Tests
```
test_rag_pipeline.py      — upload PDF → Chroma → searchable
test_cac_graph.py         — POST /query → structured response
test_slack_bot.py         — mock Slack event → thread reply
test_staging_flow.py      — query → pending/ → approve → approved/
test_sync_loop.py         — approve → Excel updated → archive entry
test_mirror_sync.py       — sync runs → /data/mirror/ updated
test_escalation_flow.py   — breach → #escalations Slack + HOD email
test_email_proposal.py    — staging proposal created → HOD email sent within 60s
test_email_approval.py    — HOD clicks link → opens approval-ui → approves → sync fires
test_email_retry.py       — SMTP failure → retry 3× → #escalations alert on final fail
test_vault_ingest.py      — write meeting note in vault → ingested → agent can retrieve it
```

### UAT Checklist (before go-live)
- [ ] Upload ALCO minutes PDF. Ask question it answers. Verify correct citation.
- [ ] Ask about topic with no matching docs. Verify "not found" — no hallucination.
- [ ] Ask question that triggers a staging proposal (confidence ≥ 0.85). Verify diff in approval UI.
- [ ] Verify HOD receives proposal email within 60 seconds of proposal creation.
- [ ] Click "Review Now" link in email on desktop. Verify correct proposal opens.
- [ ] Click "Review Now" link in email on mobile phone. Verify UI is usable on small screen.
- [ ] Approve a proposal from the email link. Verify corporate Excel file updated correctly.
- [ ] Edit value before approving. Verify edited (not agent) value written.
- [ ] Reject a proposal. Verify nothing syncs. staging/rejected/ entry created.
- [ ] Trigger a covenant breach message. Verify escalation fires to #escalations Slack + HOD + CEO email.
- [ ] Manually age a proposal past 24h (or set reminder to 1min in dev). Verify reminder email fires.
- [ ] Simulate SMTP failure (wrong password). Verify retry logic + #escalations alert.
- [ ] Upload same document twice. Verify hash deduplication.
- [ ] Ask multi-turn follow-up. Verify Postgres checkpointer maintains context.
- [ ] Verify every interaction creates Paperclip ticket.
- [ ] Verify Excel navigation matches real tracker for 3 query types.
- [ ] Try writing to /data/mirror/ from inside cac-orchestrator container — must fail.
- [ ] Restart DGX Spark. Verify all containers restore cleanly.
- [ ] Verify email_log table populated with correct delivery_status after each send.
- [ ] Write a meeting note in Obsidian. Save it. Ask @agent a question it answers. Verify vault content cited in response.
- [ ] Edit an existing SKILL.md file in Obsidian. Save. Ask a question that hits that skill. Verify updated content is returned (not cached stale version).
- [ ] Ask CTO Agent via Paperclip to draft a new skill file. Verify OpenClaw writes it to the vault. Verify it is ingested into Chroma within 60 seconds.
- [ ] Open the vault knowledge graph in Obsidian. Verify SKILL.md files link to each other correctly via [[links]].

---

## 15. Phase 2 & 3 Scope

### Phase 2 — Additional Departments
When Phase 1 has 4 weeks clean production:

For each new department repeat:
1. `services/{dept}-orchestrator/` (copy cac-orchestrator, swap agents)
2. New private Slack channel `#{dept}-committee`
3. Add to `config/dept_channels.json`
4. Write `skills/{dept}/*.md`
5. Add `config/excel_schema/{dept}_tracker.json`
6. Register CXO Agent in Paperclip under CEO Agent
7. Add Chroma collection to rag-ingestion
8. Add dept HOD email to `config/hod_emails.json`
9. Create `obsidian-vault/skills/{dept}/` folder — OpenClaw seeds with initial skill files
10. Add `{dept}_knowledge` Chroma collection to vault watcher config

**Order:** Risk Committee → Legal & Compliance → Investment Committee

### Phase 3 — Autonomous + Scale
- Add second DGX Spark (Qwen 35B on Spark B for multi-dept concurrent load)
- Ops, HR, IT department agents
- Auto-sync for pre-approved low-risk categories (Paperclip governance gate, no per-change approval)
- Scheduled ALCO pre-brief (Paperclip heartbeat, daily 07:00)
- Board-level weekly summary auto-generation
- Qwen3.5 397B upgrade path (requires both Sparks)
- OpenClaw scaffolds new dept agents on CTO Agent instruction
- Cowork plugins for all 7 departments
- Obsidian vault expanded: dedicated sections per department, cross-dept [[links]] in knowledge graph

---

## 16. Obsidian Vault Integration

### Role in the Architecture

Obsidian is the **human-facing knowledge UI**. It is not an agent tool, not a database, and not a service on the DGX Spark. It is a desktop app that makes SKILL.md files, meeting notes, and decision logs editable and navigable by non-technical team members.

```
Obsidian (team lead laptop — desktop app)
    ↓  human edits .md files, adds [[links]], browses knowledge graph
obsidian-vault/ folder
    ↓  network-mounted to DGX Spark at OBSIDIAN_VAULT_PATH
LlamaIndex VaultWatcher (inside rag-ingestion container)
    ↓  watchdog detects .md file save → debounce 5s → re-ingest
Chroma DB — cac_knowledge collection
    ↓  agents query cac_docs + cac_chat + cac_knowledge together
LangGraph retrieve_context node
    ↓
Agent answers cite vault content alongside document + chat sources

OpenClaw (Paperclip worker, MCP write access)
    ↓  CTO Agent assigns SKILL.md authoring task via Paperclip ticket
    ↓  OpenClaw reads source docs from /data/mirror/ (read-only)
    ↓  writes new skill file to vault via MCP
    ↓  VaultWatcher auto-ingests into Chroma
```

**Hard rule: Agents never query Obsidian directly. They query Chroma.**
Obsidian is upstream of Chroma, not a replacement.

---

### Vault Folder Structure

```
obsidian-vault/
│
├── .obsidian/                      ← Obsidian app config (.gitignore this)
│   ├── app.json
│   ├── graph.json                  ← knowledge graph display settings
│   └── plugins/
│       └── mcp-tools/              ← Obsidian MCP plugin for OpenClaw write access
│
├── index.md                        ← vault home page — links to all areas
│
├── skills/                         ← SKILL.md files (symlinked from repo skills/)
│   ├── shared/
│   │   ├── rag-retrieval.md
│   │   ├── excel-navigation.md
│   │   ├── escalation-protocol.md
│   │   ├── chat-ingestion.md
│   │   └── citation-format.md
│   └── cac/
│       ├── cfo-agent.md            ← links to all other CAC skills via [[]]
│       ├── liquidity-analysis.md
│       ├── capital-allocation.md
│       ├── covenant-monitoring.md
│       ├── alm-review.md
│       └── funding-facilities.md
│
├── meeting-notes/
│   ├── templates/
│   │   └── meeting-note.md
│   ├── 2026-03-24-ALCO.md
│   └── ...
│
├── decisions/
│   ├── templates/
│   │   └── decision-log.md
│   ├── 2026-03-CAC-decisions.md
│   └── ...
│
└── policies/
    ├── stay-liquid-doctrine.md
    ├── capital-delegation-matrix.md
    └── covenant-reference.md
```

---

### Standard Templates

**`meeting-notes/templates/meeting-note.md`**
```markdown
---
date: {{date}}
type: meeting-note
committee: CAC
tags: [meeting, cac]
---

# ALCO Meeting — {{date}}

## Agenda Items
-

## Decisions Made
- (link to [[decisions/2026-03-CAC-decisions]])

## Action Items
| Action | Owner | Due |
|---|---|---|
| | | |

## Key Numbers Discussed
- Liquidity buffer:
- SCB covenant ratio:
- Capital utilisation:

## Related Skills
- [[skills/cac/funding-facilities]]
- [[skills/cac/liquidity-analysis]]
```

**`decisions/templates/decision-log.md`**
```markdown
---
date: {{date}}
type: decision
committee: CAC
decision-id: CAC-{{date}}-001
status: active
tags: [decision, cac]
---

# Decision: {{title}}

## Context
What situation or question prompted this decision.

## Decision
The specific decision made. Quantitative where relevant (e.g. "threshold set at 3.5×").

## Rationale
Why this decision was made. Links to supporting [[skills/]] or [[policies/]].

## Approved By
- Name · Role · Date

## Related Skills
- [[skills/cac/cfo-agent]]
- [[skills/cac/covenant-monitoring]]

## Review Date
{{review_date}}
```

---

### Sync Strategy: Vault ↔ Git Repo

The `skills/` folder in the vault and `skills/` in the git repo must stay in sync.

**Option A — Symlink (recommended for Phase 1):**
```bash
# Replace skills/ in repo with a symlink to the vault folder
cd corporate-ai-agents/
rm -rf skills/
ln -s /path/to/obsidian-vault/skills ./skills
```
One source of truth. Git and Obsidian read the same files on disk. No sync needed.

**Option B — Git submodule (if vault is a separate repo):**
```bash
git submodule add git@yourrepo:obsidian-vault.git obsidian-vault
```
Vault has its own Git history. Use if the vault is managed by a separate team.

---

### LlamaIndex Vault Watcher Config

**`config/obsidian_watch.json`**
```json
{
  "vault_path": "${OBSIDIAN_VAULT_PATH}",
  "watch_folders": [
    { "path": "skills/",        "collection": "cac_knowledge", "doc_type": "skill" },
    { "path": "meeting-notes/", "collection": "cac_knowledge", "doc_type": "meeting_note" },
    { "path": "decisions/",     "collection": "cac_knowledge", "doc_type": "decision_log" },
    { "path": "policies/",      "collection": "cac_knowledge", "doc_type": "policy_note" }
  ],
  "ignore_folders": [".obsidian", "templates"],
  "ignore_files":   ["index.md"],
  "debounce_seconds": 5,
  "chunk_size": 512,
  "chunk_overlap": 128
}
```

Files in `templates/` and `.obsidian/` are excluded from ingestion — not content.

The watcher runs as a background thread inside the `rag-ingestion` container. The vault folder is network-mounted into the container read-only.

---

### OpenClaw MCP Workflow

OpenClaw (registered in Paperclip under CTO Agent) gets write access to the vault via the Obsidian MCP plugin. This creates a closed loop: CTO Agent assigns a task → OpenClaw researches → writes skill → vault updates → Chroma updates → agents get smarter.

```
Paperclip ticket (CTO Agent assigns):
  "Draft covenant-monitoring.md for CAC based on
   /data/mirror/documents/SCB_Facility_Agreement.pdf"
       ↓
OpenClaw:
  1. Reads SCB_Facility_Agreement.pdf via /data/mirror/ (read-only)
  2. Reads existing cfo-agent.md from vault via MCP for context
  3. Drafts covenant-monitoring.md per SKILL.md format standard
  4. Writes to obsidian-vault/skills/cac/covenant-monitoring.md via MCP
  5. VaultWatcher detects change → 5s debounce → ingests into Chroma
  6. Marks Paperclip ticket complete with link to new file
       ↓
Human (team lead opens Obsidian):
  Reviews covenant-monitoring.md in vault
  Adds [[links]] to related skills manually if missing
  Saves → VaultWatcher re-ingests final version
```

---

### What Obsidian Does NOT Do

| Claim | Reality |
|---|---|
| Replaces Chroma | ❌ Agents never query Obsidian. Chroma is always the search layer. |
| Replaces LangGraph | ❌ No orchestration capability. |
| Replaces Slack | ❌ Different audience. Obsidian is for knowledge workers. Slack is for real-time comms. |
| Replaces git for SKILL.md | ❌ Git is still source control. Obsidian is just a nice editor UI over the same files. |
| Needs to be on the DGX Spark | ❌ Desktop app only. Lives on a laptop. Vault folder is network-shared to the Spark. |
| Requires Obsidian Sync (paid) | ❌ Not needed. Plain folder + network share is sufficient. |

---

*End of PRD v2.2*

*Single DGX Spark · Slack (agents + committee) · Email (HOD approvals + escalations) · Obsidian (knowledge UI) · Cowork + OpenClaw · Mirror → Stage → Approve → Sync · Phase 1: CAC Committee*
