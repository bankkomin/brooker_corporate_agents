# Stage 7: Paperclip + Integration — Design Spec

**Date:** 2026-04-02
**Stage:** 7 of 8 (Week 7 — Paperclip + Integration)
**Status:** Approved design, pending implementation
**PRD Reference:** PRD.md v2.2, Section 8.8, 8.10, 13 (Week 7)

---

## 1. Overview

Stage 7 builds the Paperclip service (audit/orchestration hub), wires it into the existing cac-orchestrator graph, implements the full end-to-end flow, and validates everything with Docker Compose integration tests.

### Scope

| In Scope | Out of Scope |
|----------|-------------|
| Paperclip FastAPI service (port 3100) | OpenClaw actual execution (stubbed) |
| Department/agent registry with boundaries | Phase 2 department creation |
| Ticket lifecycle (create/update/query) | Paperclip dashboard UI |
| Heartbeat registration and monitoring | Production SMTP configuration |
| Webhook routing (approval → sync-back + email) | Load testing |
| cac-orchestrator integration (real HTTP) | |
| Full E2E integration tests (Docker Compose) | |
| OpenClaw worker interface (stub execution) | |

### Key Decisions

1. **Paperclip as Python FastAPI** — consistent with all other services (not Node.js as PRD originally stated). See ADR-1 below.
2. **Event-driven architecture** — HTTP calls between services, Paperclip as central hub
3. **OpenClaw stubbed** — interface designed for Claude Code/Agent SDK, execution deferred
4. **Docker Compose full stack** for integration tests
5. **Modular department boundaries** — data, staging, skills, escalation all scoped per department
6. **Vector store: Qdrant** — project migrated from Chroma to Qdrant in Stage 2. See ADR-2 below.
7. **CFO Agent = cac-orchestrator** — the PRD's "CFO Agent" is implemented as the cac-orchestrator service. See ADR-3 below.

### Architecture Decision Records

**ADR-1: Paperclip runtime — Python FastAPI instead of Node.js**

The PRD specifies Paperclip as Node.js 20. This project uses Python FastAPI for all other services (cac-orchestrator, rag-ingestion, slack-bot, email-notifier, sync-back, gateway). Introducing Node.js for one service would:
- Add a second runtime to maintain, test, and deploy
- Fragment team expertise across two ecosystems
- Complicate shared utilities (DB connection, structured logging, Pydantic models)
- Provide no meaningful benefit — Paperclip's ticket/audit workload is well-served by FastAPI

**Decision:** Build Paperclip in Python FastAPI. Update PRD tech stack table accordingly.

**ADR-2: Vector store — Qdrant instead of Chroma**

The PRD v2.2 references Chroma 0.5+ as the vector store. During Stage 2 implementation, the project migrated to **Qdrant 1.12+** because:
- Qdrant provides native gRPC support (port 6334) for high-throughput embedding operations
- Better production-readiness with built-in persistence and replication
- Already deployed and operational with 4 collections (cac_docs, cac_chat, cac_knowledge, shared_policies)

**Decision:** Qdrant is the authoritative vector store. PRD should be updated to reflect this. All references in this spec use Qdrant.

**ADR-3: CFO Agent naming — "cac-orchestrator" is the CFO Agent**

The PRD references "CFO Agent" as the primary agent registered with Paperclip. In implementation, this is the `cac-orchestrator` service — a LangGraph graph that coordinates 5 specialist agents. The naming difference exists because:
- "CFO Agent" is the business-facing name (what committee members see)
- "cac-orchestrator" is the service-facing name (what Docker/code uses)
- The `skills/shared/cfo-agent.md` SKILL.md file defines the CFO Agent's persona and behavior, loaded by cac-orchestrator

**Decision:** Use "cac-orchestrator" in all technical contexts. Register with Paperclip as `agent_name: "cfo-agent"` (display name) with `endpoint_url` pointing to cac-orchestrator. The SKILL.md file `cfo-agent.md` remains the persona definition.

---

## 1b. Visual Overview (Mermaid Diagrams)

### System Architecture — How Services Connect

```mermaid
graph TB
    subgraph "User Interaction"
        SLACK["Slack Channel<br/>#cac-committee"]
        EMAIL["HOD Email<br/>(approval link)"]
        BROWSER["Approval UI<br/>(browser, port 4000)"]
    end

    subgraph "Core Services"
        SB["Slack Bot<br/>port 3003"]
        CAC["CAC Orchestrator<br/>port 3001<br/>(AI agents)"]
        PPC["Paperclip<br/>port 3100<br/>(audit & routing hub)"]
        RAG["RAG Ingestion<br/>port 3004<br/>(document search)"]
    end

    subgraph "Action Services"
        EN["Email Notifier<br/>port 3005"]
        SYN["Sync Back<br/>port 3006"]
        AUI["Approval UI<br/>port 4000"]
    end

    subgraph "Data Layer"
        PG[(PostgreSQL<br/>database)]
        QD[(Qdrant<br/>vector search)]
        MIRROR["/data/mirror/<br/>(read-only)"]
        STAGING["/data/staging/<br/>(proposals)"]
        ARCHIVE["/data/archive/<br/>(permanent)"]
    end

    SLACK -->|"@agent question"| SB
    SB -->|"forward query"| CAC
    CAC -->|"search docs"| RAG
    RAG --> QD
    CAC -->|"read Excel"| MIRROR
    CAC -->|"create ticket"| PPC
    CAC -->|"write proposal"| STAGING
    PPC -->|"send email"| EN
    EN -->|"approval link"| EMAIL
    EMAIL -->|"HOD clicks link"| BROWSER
    BROWSER --> AUI
    AUI -->|"approve/reject"| PPC
    PPC -->|"on approve"| SYN
    SYN -->|"update Excel"| ARCHIVE
    PPC -->|"confirm email"| EN
    PPC --> PG
    CAC --> PG

    style PPC fill:#f9a825,stroke:#f57f17,stroke-width:3px,color:#000
    style SLACK fill:#4a154b,stroke:#4a154b,color:#fff
    style EMAIL fill:#1565c0,stroke:#0d47a1,color:#fff
    style BROWSER fill:#2e7d32,stroke:#1b5e20,color:#fff
```

### The Golden Path — How a Question Becomes an Approved Change

```mermaid
sequenceDiagram
    participant U as Committee Member
    participant S as Slack
    participant SB as Slack Bot
    participant CAC as CAC Orchestrator
    participant RAG as RAG Search
    participant PPC as Paperclip
    participant EN as Email Notifier
    participant HOD as Head of Department
    participant AUI as Approval UI
    participant SYN as Sync Back

    U->>S: @cac-agent What's our current<br/>liquidity ratio?
    S->>SB: Event received
    SB->>CAC: Forward query
    CAC->>RAG: Search documents
    RAG-->>CAC: Relevant context found
    CAC->>CAC: AI agents analyze & draft answer
    CAC->>PPC: Create query ticket (PPC-0001)
    CAC-->>SB: Answer with citations
    SB-->>S: Thread reply to user

    Note over CAC: If answer requires Excel change...

    CAC->>CAC: Write staging proposal (chg_0142)
    CAC->>PPC: Create proposal ticket (PPC-0002)
    PPC->>EN: Send approval email
    EN->>HOD: Email with review link

    HOD->>AUI: Click link in email
    AUI-->>HOD: Show proposal diff (before/after)
    HOD->>AUI: Click "Approve"
    AUI->>PPC: Webhook: approved

    PPC->>SYN: Process approved change
    SYN->>SYN: Update Excel + archive
    PPC->>EN: Send confirmation email
    EN->>HOD: Confirmation: change applied
```

### Department Boundaries — How Data Is Isolated

```mermaid
graph LR
    subgraph "CAC Department"
        direction TB
        CAC_O["CAC Orchestrator"]
        CAC_LIQ["Liquidity Agent"]
        CAC_CAP["Capital Agent"]
        CAC_ALM["ALM Agent"]
        CAC_FUN["Funding Agent"]
        CAC_ESC["Escalation Agent"]
        CAC_OC["OpenClaw (stub)"]

        CAC_O --> CAC_LIQ
        CAC_O --> CAC_CAP
        CAC_O --> CAC_ALM
        CAC_O --> CAC_FUN
        CAC_O --> CAC_ESC
        CAC_O -.->|"future"| CAC_OC
    end

    subgraph "CAC Data Zone"
        direction TB
        CAC_MIRROR["/data/mirror/cac/<br/>(read-only)"]
        CAC_STAGE["/data/staging/cac/<br/>(proposals)"]
        CAC_QDRANT["Qdrant: cac_docs<br/>cac_chat, cac_knowledge"]
        CAC_SKILLS["skills/cac/<br/>SKILL.md files"]
    end

    subgraph "Future: Treasury Dept"
        direction TB
        TRES_O["Treasury Orchestrator"]
        TRES_FX["FX Hedging Agent"]
        TRES_CASH["Cash Flow Agent"]
    end

    subgraph "Treasury Data Zone"
        direction TB
        TRES_MIRROR["/data/mirror/treasury/"]
        TRES_STAGE["/data/staging/treasury/"]
        TRES_QDRANT["Qdrant: treasury_docs<br/>treasury_chat"]
        TRES_SKILLS["skills/treasury/"]
    end

    CAC_O --> CAC_MIRROR
    CAC_O --> CAC_STAGE
    CAC_O --> CAC_QDRANT
    CAC_O --> CAC_SKILLS

    TRES_O --> TRES_MIRROR
    TRES_O --> TRES_STAGE
    TRES_O --> TRES_QDRANT
    TRES_O --> TRES_SKILLS

    CAC_O -.-x|"blocked"| TRES_MIRROR
    TRES_O -.-x|"blocked"| CAC_MIRROR

    style CAC_O fill:#f9a825,stroke:#f57f17,color:#000
    style TRES_O fill:#42a5f5,stroke:#1565c0,color:#000
```

### Paperclip Ticket Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Open: Ticket created
    Open --> InProgress: Agent starts processing
    InProgress --> PendingApproval: Staging proposal created
    PendingApproval --> Completed: HOD approves
    PendingApproval --> Rejected: HOD rejects
    InProgress --> Completed: Query answered (no proposal)
    InProgress --> Escalated: Breach detected
    Escalated --> Completed: Escalation resolved
    Open --> PendingHuman: Assigned to OpenClaw (stub)
    PendingHuman --> Completed: Human completes task
    InProgress --> Failed: Unrecoverable error
    Completed --> [*]
    Rejected --> [*]
    Failed --> [*]
```

### Data Flow — The Safety Pipeline

```mermaid
graph LR
    subgraph "Zone 0: Corporate"
        CORP["Corporate Excel<br/>(source of truth)"]
    end

    subgraph "Zone 1: Mirror (READ ONLY)"
        MIRROR["Agent reads<br/>current data"]
    end

    subgraph "Zone 2: Staging"
        PEND["pending/<br/>(agent writes here)"]
        APP["approved/"]
        REJ["rejected/"]
    end

    subgraph "Zone 3: Human Gate"
        APPR{"HOD reviews<br/>in browser"}
    end

    subgraph "Zone 4: Archive"
        ARC["Permanent<br/>audit trail"]
    end

    CORP -->|"sync every 15min"| MIRROR
    MIRROR -->|"agent reads"| PEND
    PEND --> APPR
    APPR -->|"approve"| APP
    APPR -->|"reject"| REJ
    APP -->|"sync back"| CORP
    APP --> ARC

    style CORP fill:#ef5350,stroke:#c62828,color:#fff
    style MIRROR fill:#ff9800,stroke:#e65100,color:#000
    style APPR fill:#66bb6a,stroke:#2e7d32,color:#000
    style ARC fill:#42a5f5,stroke:#1565c0,color:#fff
```

---

## 2. Paperclip Service Architecture

### 2.1 Service Structure

```
services/paperclip/
  Dockerfile
  requirements.txt
  src/
    main.py           -- FastAPI app with lifespan, /health
    models.py          -- Pydantic v2 models
    routes/
      tickets.py       -- Ticket CRUD endpoints
      heartbeat.py     -- Agent heartbeat registration
      departments.py   -- Department/agent registry
      webhooks.py      -- Approval-ui webhook receiver
    services/
      ticket_service.py    -- Ticket business logic
      heartbeat_service.py -- Heartbeat monitoring
      event_router.py      -- Routes events to downstream services
      worker_manager.py    -- OpenClaw worker interface (stub)
    db/
      connection.py    -- asyncpg pool management
      queries.py       -- SQL queries
```

### 2.2 API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Docker healthcheck |
| POST | `/tickets` | Create ticket (from cac-orchestrator) |
| PATCH | `/tickets/{id}` | Update ticket status |
| GET | `/tickets/{id}` | Get ticket details |
| GET | `/tickets` | List/filter tickets (query params: department, type, status, agent) |
| POST | `/heartbeat` | Register/renew agent heartbeat |
| GET | `/heartbeats` | List registered agents with health status |
| POST | `/webhooks/approval` | Receive approval-ui approve/reject events |
| POST | `/departments` | Register a new department |
| GET | `/departments` | List all departments |
| POST | `/departments/{dept}/agents` | Register agent to department |
| GET | `/departments/{dept}/agents` | List agents in department |
| DELETE | `/departments/{dept}/agents/{name}` | Deregister agent |
| POST | `/workers/{agent}/assign` | Assign ticket to worker (OpenClaw stub) |
| GET | `/workers/{agent}/status` | Worker status and assigned tickets |

### 2.3 Pydantic Models

```python
class TicketCreate(BaseModel):
    type: Literal["query", "proposal", "escalation", "skill_task"]
    department: str = "cac"
    agent: str
    interaction_id: str | None = None
    payload: dict  # Flexible payload per ticket type

class TicketResponse(BaseModel):
    ticket_id: str  # "PPC-0001"
    type: str
    department: str
    agent: str
    status: Literal[
        "open", "in_progress", "pending_approval",
        "completed", "rejected", "escalated",
        "pending_human", "failed"
    ]
    payload: dict
    created_at: datetime
    updated_at: datetime

class HeartbeatRequest(BaseModel):
    agent_name: str
    department: str = "cac"
    agent_role: Literal["orchestrator", "specialist", "worker"]
    endpoint_url: str | None = None
    skills: list[str] = []
    data_scope: dict = {}
    permissions: dict = {}

class ApprovalWebhook(BaseModel):
    proposal_id: str
    decision: Literal["approved", "rejected", "deferred"]
    reviewer: str
    timestamp: datetime
    notes: str | None = None
    edited_values: dict | None = None  # For "edit then approve" flow

class DepartmentCreate(BaseModel):
    name: str  # "cac", "treasury"
    display_name: str
    slack_channel: str
    hod_email: str
    escalation_rules: dict = {}
    data_zone: dict  # {"mirror": "...", "staging": "...", "qdrant_prefix": "..."}
    config: dict = {}
```

---

## 3. Database Schema

### 3.1 New Tables

**`paperclip_departments`**

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() |
| name | VARCHAR(50) | UNIQUE, NOT NULL |
| display_name | VARCHAR(200) | NOT NULL |
| slack_channel | VARCHAR(100) | NOT NULL |
| hod_email | VARCHAR(200) | NOT NULL |
| escalation_rules | JSONB | DEFAULT '{}' |
| data_zone | JSONB | NOT NULL |
| config | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

**`paperclip_agents`**

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() |
| department_id | UUID | FK → paperclip_departments(id) |
| agent_name | VARCHAR(100) | NOT NULL |
| agent_role | VARCHAR(20) | NOT NULL (orchestrator/specialist/worker) |
| worker_type | VARCHAR(20) | NULL (claude_code/claude_sdk/human/stub) |
| endpoint_url | VARCHAR(500) | NULL |
| skills | JSONB | DEFAULT '[]' |
| data_scope | JSONB | DEFAULT '{}' |
| permissions | JSONB | DEFAULT '{}' |
| status | VARCHAR(20) | DEFAULT 'active' |
| registered_at | TIMESTAMPTZ | DEFAULT NOW() |
| last_heartbeat | TIMESTAMPTZ | NULL |
| UNIQUE(department_id, agent_name) | | |

**`paperclip_tickets`**

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() |
| ticket_id | VARCHAR(20) | UNIQUE, NOT NULL (PPC-XXXX) |
| type | VARCHAR(20) | NOT NULL (query/proposal/escalation/skill_task) |
| department | VARCHAR(50) | NOT NULL, FK → paperclip_departments(name) |
| agent | VARCHAR(100) | NOT NULL |
| interaction_id | UUID | NULL, FK → agent_interactions(id) |
| status | VARCHAR(20) | DEFAULT 'open' |
| payload | JSONB | NOT NULL |
| result | JSONB | NULL |
| assigned_worker | VARCHAR(100) | NULL |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

### 3.2 Migration

File: `migrations/007_paperclip_tables.sql`

Adds all three tables plus:
- Index on `paperclip_tickets(department, status)`
- Index on `paperclip_tickets(type, created_at)`
- Index on `paperclip_agents(department_id, status)`
- Seed CAC department record
- Seed CAC agent registrations (cac-orchestrator + 5 specialists + openclaw stub)

---

## 4. Integration Wiring

### 4.1 cac-orchestrator → Paperclip (ticket creation)

**Current state:** `create_paperclip_ticket` node returns fake `PPC-XXXX` IDs.

**Target state:** Real HTTP POST to `http://paperclip:3100/tickets`.

```python
# services/cac-orchestrator/src/nodes/paperclip_ticket.py
async def create_paperclip_ticket(state: CACState) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.PAPERCLIP_URL}/tickets",
            json={
                "type": determine_ticket_type(state),
                "department": "cac",
                "agent": "cac-orchestrator",
                "interaction_id": str(state.get("interaction_id")),
                "payload": build_ticket_payload(state),
            },
            timeout=10.0,
        )
        response.raise_for_status()
        ticket = response.json()
    return {"paperclip_ticket_id": ticket["ticket_id"]}
```

**Fallback:** If Paperclip is unreachable, log warning and return stub ID. Never block the user response.

### 4.2 cac-orchestrator heartbeat registration

On startup (in FastAPI lifespan), register with Paperclip:

```python
async def register_with_paperclip():
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{settings.PAPERCLIP_URL}/heartbeat",
            json={
                "agent_name": "cfo-agent",  # Business-facing name (see ADR-3)
                "department": "cac",
                "agent_role": "orchestrator",
                "endpoint_url": "http://cac-orchestrator:3001/health",
                "skills": ["shared/escalation-protocol", "shared/citation-format", ...],
            },
            timeout=10.0,
        )
```

Background task renews heartbeat every 60 seconds.

### 4.3 approval-ui → Paperclip (webhook)

**Routing change from PRD:** The PRD (Section 8.5) has approval-ui POST directly to sync-back on approve. With Paperclip, this changes:

- **Before (PRD):** approval-ui → sync-back (direct)
- **After (with Paperclip):** approval-ui → Paperclip → sync-back + email-notifier

Paperclip becomes the single routing hub. approval-ui now POSTs **ONLY** to Paperclip, which then fans out to sync-back and email-notifier. This centralizes audit logging and event routing.

When HOD approves/rejects/defers in approval-ui, it POSTs to Paperclip:

```
POST http://paperclip:3100/webhooks/approval
{
  "proposal_id": "chg_0142",
  "decision": "approved",
  "reviewer": "jane.doe@company.com",
  "timestamp": "2026-04-02T10:30:00Z"
}
```

**Paperclip event router actions:**

On **approved**:
1. Update ticket status → "completed"
2. POST `http://sync-back:3006/process-approved` with `{ "proposal_id": "chg_0142" }`
3. POST `http://email-notifier:3005/notify/confirmed` with `{ "proposal_id": "chg_0142", "event": "approved" }`

On **rejected**:
1. Update ticket status → "rejected"
2. POST `http://email-notifier:3005/notify/confirmed` with `{ "proposal_id": "chg_0142", "event": "rejected" }`
3. Move staging file to `/data/staging/rejected/`

On **deferred**:
1. Update ticket status → "pending_approval" (remains in queue)
2. Log deferral with reviewer notes
3. No downstream action — proposal stays in pending/ for future review

On **edit then approve** (decision="approved" with `edited_values` populated):
1. Update staging manifest with edited values before proceeding
2. Then follow the standard "approved" flow above

### 4.4 Escalation flow

When `escalation_check` node fires in cac-orchestrator:
1. Creates escalation ticket via `POST /tickets` with `type: "escalation"`
2. Paperclip event router:
   - POST `http://email-notifier:3005/notify/escalation` with escalation details
   - POST to Slack `#escalations` channel (via slack-bot or direct Slack API)

### 4.5 OpenClaw worker interface (stub)

Paperclip exposes worker management endpoints:
- `POST /workers/openclaw/assign` — assigns a ticket to OpenClaw
- `GET /workers/openclaw/status` — returns current assignments

In stub mode, assigned tickets get status `"pending_human"` and a log entry:
```
"OpenClaw worker stubbed — ticket PPC-0042 requires manual execution"
```

The `worker_type` field on `paperclip_agents` supports future values:
- `"stub"` — current behavior, logs and waits
- `"claude_code"` — invoke Claude Code CLI subprocess
- `"claude_sdk"` — invoke Claude Agent SDK Python API
- `"human"` — create notification for human execution

---

## 5. Department Boundary Enforcement

### 5.1 Data Boundaries

Each department's `data_zone` config defines:
```json
{
  "mirror": "/data/mirror/cac/",
  "staging": "/data/staging/cac/",
  "qdrant_prefix": "cac_",
  "qdrant_collections": ["cac_docs", "cac_chat", "cac_knowledge"]
}
```

**Enforcement points:**
- Paperclip validates ticket `department` matches agent's registered department
- staging_writer validates output path matches department's staging zone
- RAG queries scoped to department's Qdrant collections

### 5.2 Skill Boundaries

Skills are namespaced: `skills/{department}/{skill-name}.md`
- `skills/shared/` — cross-department (escalation-protocol, citation-format, etc.)
- `skills/cac/` — CAC-specific (liquidity-analysis, capital-allocation, etc.)

Agent's `skills` field in `paperclip_agents` lists allowed skills:
```json
["cac/liquidity-analysis", "shared/escalation-protocol", "shared/citation-format"]
```

### 5.3 Agent Hierarchy

```
Department: CAC
├── Orchestrator: cac-orchestrator
│   ├── Specialist: liquidity-agent (skills: cac/liquidity-analysis, shared/*)
│   ├── Specialist: capital-agent (skills: cac/capital-allocation, shared/*)
│   ├── Specialist: alm-agent (skills: cac/alm-review, shared/*)
│   ├── Specialist: funding-agent (skills: cac/funding-facilities, shared/*)
│   └── Specialist: escalation-agent (skills: shared/escalation-protocol)
└── Worker: openclaw (worker_type: stub, skills: shared/*)
```

### 5.4 Expansion Pattern

Adding a new department requires:
1. `POST /departments` with department config
2. `POST /departments/{name}/agents` for each agent
3. Create `skills/{name}/` directory with SKILL.md files
4. Create Qdrant collections (`{name}_docs`, `{name}_chat`)
5. Add Docker service for department's orchestrator
6. Update `config/departments.json`

No Paperclip code changes needed — configuration only.

---

## 6. Docker & Infrastructure

### 6.1 New Docker Compose Entry

```yaml
paperclip:
  build:
    context: ./services/paperclip
    dockerfile: Dockerfile
  container_name: cac-paperclip
  ports:
    - "3100:3100"
  environment:
    - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
    - PAPERCLIP_API_KEY=${PAPERCLIP_API_KEY}
    - SYNC_BACK_URL=http://sync-back:3006
    - EMAIL_NOTIFIER_URL=http://email-notifier:3005
    - SLACK_BOT_URL=http://slack-bot:3003
    - LOG_LEVEL=info
  depends_on:
    postgres:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3100/health"]
    interval: 30s
    timeout: 5s
    retries: 3
  networks:
    - cac-network
  volumes:
    - ./data/staging:/data/staging
```

### 6.2 Updated Service Dependencies

```
postgres (healthy) ──┬── qdrant ── minio
                     ├── paperclip (healthy)
                     │     ↑ cac-orchestrator registers heartbeat
                     │     ↑ approval-ui sends webhooks
                     ├── rag-ingestion
                     ├── cac-orchestrator
                     ├── email-notifier
                     ├── sync-back
                     ├── approval-ui
                     ├── slack-bot
                     └── gateway (nginx)
```

### 6.3 Environment Variables

New in `.env.example`:
```
PAPERCLIP_URL=http://paperclip:3100
PAPERCLIP_API_KEY=dev-paperclip-key
```

Updated in cac-orchestrator's environment:
```
PAPERCLIP_URL=http://paperclip:3100
```

### 6.4 Migration

File: `migrations/007_paperclip_tables.sql`

Includes CREATE TABLE statements, indexes, and seed data for CAC department and agents.

---

## 7. End-to-End Integration Tests

### 7.1 Test Infrastructure

- **docker-compose.test.yml** — override with test env vars, MailHog for email capture
- **conftest.py** — fixtures for service clients, health check waiter, test data factories
- Tests use `httpx.AsyncClient` against real service endpoints

### 7.2 Test Files

| File | Validates |
|------|-----------|
| `tests/integration/test_paperclip_service.py` | Ticket CRUD, heartbeat, department/agent registration |
| `tests/integration/test_e2e_golden_path.py` | Full flow: mention → answer → stage → email → approve → sync → archive |
| `tests/integration/test_e2e_escalation.py` | Breach → escalation ticket → Slack + HOD email |
| `tests/integration/test_e2e_deep_link.py` | Email link → correct proposal in approval-ui |
| `tests/integration/test_e2e_rejection.py` | HOD rejects → rejected/ → notification |
| `tests/integration/test_paperclip_heartbeat.py` | Registration, renewal, stale detection |
| `tests/unit/paperclip/test_ticket_service.py` | Ticket business logic |
| `tests/unit/paperclip/test_event_router.py` | Event routing logic |
| `tests/unit/paperclip/test_models.py` | Pydantic model validation |
| `tests/unit/paperclip/test_department_service.py` | Department boundary enforcement |

### 7.3 Golden Path Test Assertions

1. Slack mock event processed within 3s
2. Paperclip has query ticket (type: "query") with correct interaction_id
3. Paperclip has proposal ticket (type: "proposal") with proposal_id
4. `/data/staging/pending/chg_XXXX.json` exists with valid manifest schema
5. Email notification sent within 60s of staging proposal
6. Deep-link URL in email contains `?proposal_id=chg_XXXX` (not generic queue)
7. After HOD approval: proposal moved to `/data/staging/approved/`
8. After sync-back: archive entry in `/data/archive/`
9. Paperclip ticket status updated to "completed"
10. email-notifier sent confirmation email

---

## 8. Changes to Existing Services

### 8.1 cac-orchestrator

- **`nodes/paperclip_ticket.py`** — Replace stub with real HTTP POST to Paperclip
- **`main.py` lifespan** — Add heartbeat registration + background renewal task
- **`settings.py`** — Add `PAPERCLIP_URL` config
- **`requirements.txt`** — httpx already present, no changes needed

### 8.2 approval-ui

- **Add webhook POST** — After approve/reject action, POST to `http://paperclip:3100/webhooks/approval`
- **Environment** — Add `PAPERCLIP_URL` env var

### 8.3 config/departments.json

- Add CAC department seed with all boundary definitions
- Schema: matches `DepartmentCreate` Pydantic model

### 8.4 docker-compose.yml

- Add `paperclip` service block
- Add `PAPERCLIP_URL` to cac-orchestrator and approval-ui environments
- Update `depends_on` for cac-orchestrator to include paperclip

---

## 9. Error Handling & Resilience

### 9.1 Paperclip Unavailable

- cac-orchestrator: Log warning, return stub ticket ID, continue serving user
- approval-ui: Retry webhook 3x with exponential backoff, alert on failure
- Never block user-facing operations due to Paperclip outage

### 9.2 Downstream Service Unavailable

- sync-back unreachable: Paperclip retries 3x, creates alert ticket
- email-notifier unreachable: Paperclip retries 3x, logs to `#escalations`
- All retries use exponential backoff with jitter

### 9.3 Heartbeat Monitoring

- Agents with no heartbeat for >120s marked "stale"
- Stale agents logged but not removed (manual cleanup)
- Health endpoint reports stale agent count

---

## 10. SKILL.md Validation (PRD Week 7 Requirement)

The PRD requires "Write all 10 SKILL.md files" in Week 7. Per Implementation.md, all 10 were completed in Stage 5:

| # | File | Status | Agent |
|---|------|--------|-------|
| 1 | `skills/shared/escalation-protocol.md` | Done (Stage 5) | All agents |
| 2 | `skills/shared/citation-format.md` | Done (Stage 5) | All agents |
| 3 | `skills/shared/cfo-agent.md` | Done (Stage 5) | cac-orchestrator persona |
| 4 | `skills/cac/covenant-monitoring.md` | Done (Stage 5) | capital-agent |
| 5 | `skills/cac/liquidity-analysis.md` | Done (Stage 5) | liquidity-agent |
| 6 | `skills/cac/capital-allocation.md` | Done (Stage 5) | capital-agent |
| 7 | `skills/cac/alm-review.md` | Done (Stage 5) | alm-agent |
| 8 | `skills/cac/funding-facilities.md` | Done (Stage 5) | funding-agent |
| 9 | `skills/shared/excel-navigation.md` | Done (Stage 5) | excel_navigator node |
| 10 | `skills/shared/rag-retrieval.md` | Done (Stage 5) | retrieve_context node |

**Stage 7 task:** Validate all 10 files conform to PRD Section 11 format standard (Mandate, Tone & Style, Domain Knowledge, Retrieval Instructions, Staging Proposal Rules, Excel Navigation, Escalation Triggers, Output Format, Hard Rules). Fix any gaps.

**`chat-ingestion.md` scope:** Listed in PRD Section 4 project structure but NOT in the Section 11 build priority list of 10 files. This is a Phase 2 item — not required for Stage 7. It would be needed when chat history indexing becomes a standalone skill (currently handled by rag-ingestion's chat_indexer module).

---

## 11. Data Relationships

### How Paperclip tables relate to existing tables

```
agent_interactions (existing)
  ├── id (UUID) ←── paperclip_tickets.interaction_id (FK)
  └── proposal_id ──→ staging_proposals.id (existing)

staging_proposals (existing)
  ├── id (proposal_id like "chg_0142")
  └── status ← Updated by approval-ui, NOT by Paperclip
       (Paperclip tracks its own ticket status independently)

paperclip_tickets (new)
  ├── interaction_id → agent_interactions.id
  ├── department → paperclip_departments.name
  └── payload.proposal_id → staging_proposals.id (JSONB reference, not FK)

approval_decisions (existing)
  └── proposal_id → staging_proposals.id
       (approval-ui writes here AND sends webhook to Paperclip)
```

**Key principle:** Paperclip tracks ticket lifecycle (open → completed). The staging pipeline tracks proposal lifecycle (pending → approved). These are parallel but linked via `interaction_id` and `proposal_id` in the ticket payload.

---

## 12. Network & Port Clarification

### Port mapping strategy

| Service | Container Port | Host-Mapped | Notes |
|---------|---------------|-------------|-------|
| paperclip | 3100 | Yes (3100) | Exposed for dev/debug access |
| email-notifier | 3005 | No | Docker-network-only, internal service |
| sync-back | 3006 | No | Docker-network-only, internal service |
| approval-ui | 4000 | Yes (4000) | HOD accesses via browser |
| gateway | 3000 | Yes (8080 via nginx) | External API gateway |

Email-notifier and sync-back are internal services — they listen on ports within the Docker network but are NOT exposed to the host. Only services that need direct browser or external access get host port mapping.

### Gateway routing

In Phase 1, Paperclip endpoints are Docker-network-only. Services call Paperclip directly at `http://paperclip:3100`. No gateway routing needed for Paperclip in Stage 7.

In Phase 2, if an external audit dashboard is built, Paperclip's read endpoints (`GET /tickets`, `GET /departments`) would be added to the nginx gateway config.

---

## 13. Security Considerations

- Paperclip API key required for all non-health endpoints
- Department boundary enforcement prevents cross-department data access
- Webhook signature validation for approval-ui events (JWT-based, reuse existing auth)
- No PII in ticket payloads — reference interaction_ids, not raw user data
- Staging path validation prevents directory traversal
