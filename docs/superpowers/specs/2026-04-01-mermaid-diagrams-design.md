# Mermaid Diagram Design Spec — Plan Document Visualizations

**Date:** 2026-04-01
**Audience:** Department Heads (HODs) — mid-level detail, business language, light technical labels
**Deliverables:** 12 Mermaid diagrams across 6 files

---

## Scope

### Inline Diagrams (10 diagrams — 2 per plan doc)

Each plan document gets a new `## System Overview` section inserted immediately after the header/overview block, containing:

1. **Architecture flowchart** (flowchart TD) — services, data flow, decision points
2. **Sequence diagram** — time-ordered interactions for the main workflow

| Plan Document (full filename) | Flowchart Shows | Sequence Shows |
|-------------------------------|----------------|----------------|
| `2026-03-25-stage1-infrastructure.md` | Docker services, data zones, network topology | System startup → health checks → services online |
| `2026-03-30-stage2-4-rag-orchestrator.md` | RAG ingestion pipeline + LangGraph query flow | Document ingestion + query-to-response flow |
| `2026-03-30-stage3-slack-bot.md` | Slack event routing (message/file/@mention) | Event → ACK → process → reply lifecycle |
| `2026-03-30-stage4-cac-orchestrator.md` | LangGraph StateGraph nodes and routing | Query → classify → retrieve → agent → synthesize |
| `2026-03-31-stage5-agents-staging.md` | Specialist agents + staging proposal + escalation pipeline | Agent skill loading → proposal → validation → approval flow |

**Note:** `2026-03-30-stage2-rag-ingestion.md` is a subset of `stage2-4-rag-orchestrator.md` and does NOT get its own diagrams — the combined doc covers both.

### Relationship to Existing Architecture Diagrams

The architecture spec (`docs/superpowers/specs/2026-03-25-architecture-design.md`) already contains a management-view flowchart and data zone diagram showing the **static system architecture**. The Stage 1 inline diagram takes a **different perspective**: it shows the **startup sequence and runtime connectivity** rather than repeating the static layout. Each diagram should reference the architecture spec for the full static view: *"For the full architecture diagram, see the Architecture Design Spec."*

### Summary File (2 diagrams + decision table)

**New file:** `docs/superpowers/system-flow-summary.md`

Contents:
1. **Stage progression flowchart** — build order showing Stage 1 → 2 → 3 → 4 → 5 dependencies, what each stage produces, and what the next stage consumes
2. **Master end-to-end flowchart** — full system data flow: corporate data → mirror → Slack → Bot → Orchestrator → Agent → staging → approval → sync-back
3. **Decision table** (Markdown table) — every branch point listing: decision name, who decides (AI or human), inputs, possible outcomes

---

## Style Guide

All diagrams follow these conventions for HOD readability:

### Language
- Business language only: "Download shared file" not `file_handler.download()`
- No function names, class names, or code references
- Plain Yes/No on decision branches

### Color-Coded Subgraphs

Uses Mermaid `classDef` and `class` syntax for broad compatibility:

```mermaid
%% Define color classes
classDef automated fill:#e1f0ff,stroke:#4a90d9,color:#333
classDef human fill:#e1f5e1,stroke:#4caf50,color:#333
classDef external fill:#fff3e0,stroke:#ff9800,color:#333

%% Apply to nodes
class ServiceA,ServiceB automated
class HODApproval human
class SlackAPI,CorporateData external
```

**Legend (included at bottom of every diagram):**
- Blue nodes = Automated services
- Green nodes = Human actions / approval gates
- Orange nodes = External systems (Slack, corporate data, email)

**Note:** The architecture design spec uses a different color scheme (green = corporate, blue = mirror, orange = AI). Each document includes its own legend to avoid confusion.

### Flowchart Conventions
- `[Rectangle]` for processes/services
- `{Diamond}` for decisions
- `([Stadium])` for start/end points
- `[(Cylinder)]` for databases/stores
- Subgraph labels identify data zones (Zone 1: Read-Only Mirror, Zone 2: Staging, Zone 3: Approval)

### Sequence Diagram Conventions
- Numbered steps (1., 2., 3.) in messages
- Participant aliases use service names: "Slack Bot", "RAG Pipeline", "Orchestrator"
- `activate`/`deactivate` for processing duration
- Notes for important context (e.g., "ACK within 3 seconds")

### Rendering Targets
Diagrams must render correctly in: GitHub Markdown preview, VS Code Mermaid extension, and Obsidian (which is part of this system's knowledge UI for HODs).

---

## Diagram Specifications

### Stage 1 — Infrastructure (`2026-03-25-stage1-infrastructure.md`)

**Perspective:** Runtime connectivity and startup sequence (NOT the static architecture — that's in the architecture design spec).

**Flowchart: Infrastructure Runtime**
```
Subgraph: External (orange)
  - vLLM on DGX Spark (122B reasoning + 9B embedding)
  - Corporate Data Sources

Subgraph: Docker Network (blue)
  - nginx Load Balancer → vLLM endpoints
  - Gateway (API entry point)
  - PostgreSQL (state + checkpoints)
  - Qdrant (vector search)
  - MinIO (document storage)

Subgraph: Data Zones
  - Zone 1: /data/mirror/ (read-only to agents)
  - Zone 2: /data/staging/ (agent proposals)
  - Zone 4: /data/archive/ (permanent audit)

Arrows: Gateway → all services, nginx → vLLM, Corporate → mirror sync
Note: "For static architecture view, see Architecture Design Spec"
```

**Sequence: System Startup**
```
Participants: Docker Compose, PostgreSQL, Qdrant, MinIO, nginx, Gateway
Flow: Docker starts → DB migrates schema → Qdrant ready → MinIO ready →
      nginx checks vLLM health → Gateway starts → health check script verifies all
Error path: If vLLM unreachable → nginx marks unhealthy → gateway still starts (dev mode)
```

### Stage 2+4 — RAG Ingestion & CAC Orchestrator (`2026-03-30-stage2-4-rag-orchestrator.md`)

**Flowchart: Document Ingestion + Query Pipeline**
```
Left side — Ingestion:
  Document Upload → Duplicate Check (hash) → Chunker (split by type) → Embedder (9B model) → Qdrant Store
  Chat Message → Chat Indexer → Qdrant Store
  Decision: Duplicate detected? → Yes: skip / No: continue

Right side — Query:
  User Question → Classify Intent → Retrieve from Qdrant →
  Route to Specialist Agent {funding/liquidity/capital/ALM} →
  Escalation Check {breach detected?} → Synthesize Response with Citations

Decision points:
  - Duplicate check (already indexed?)
  - Intent classification (which agent?)
  - Escalation check (does this need HOD attention?)
```

**Sequence: End-to-End Query Flow**
```
Participants: User, Slack Bot, Orchestrator, LLM (Qwen 122B), Qdrant, Specialist Agent
Flow:
  1. User asks question in Slack
  2. Slack Bot forwards to Orchestrator
  3. Orchestrator sends to LLM for intent classification
  4. Orchestrator queries Qdrant for relevant documents
  5. Specialist Agent processes with skill context
  6. Agent optionally creates staging proposal
  7. Orchestrator synthesizes final response with citations
  8. Response returned to Slack Bot → threaded reply
Error path: If LLM timeout → retry once → return "unable to process" message
```

### Stage 3 — Slack Bot (`2026-03-30-stage3-slack-bot.md`)

**Flowchart: Event Routing**
```
Entry: Slack Event Received

Decision: Is it from a monitored channel? → No: ignore
Decision: Is it from a bot? → Yes: ignore (prevent loops)

Decision: What type of event?
  → Message: Index via RAG Ingestion
  → File Shared: Download → validate type → forward to RAG Ingestion
  → @agent Mention: Forward question to CAC Orchestrator → post threaded reply

Decision: Is file type supported? → No: skip with log

All paths end at: Response posted to Slack thread
```

**Sequence: Message Processing Lifecycle**
```
Participants: Slack API, Slack Bot, RAG Ingestion, CAC Orchestrator
Flow:
  1. Slack sends event to Bot
  2. Bot ACKs immediately (within 3 seconds)
  3. Bot spawns background task
  4. If @mention: Bot calls Orchestrator → gets response → posts thread reply
  5. If message: Bot calls RAG to index message
  6. If file: Bot downloads file → POSTs to RAG for ingestion
Error path: If RAG/Orchestrator unreachable → log error, post "service unavailable" reply
```

### Stage 4 — CAC Orchestrator (`2026-03-30-stage4-cac-orchestrator.md`)

**Flowchart: LangGraph Pipeline**
```
START → Classify Intent (LLM determines domain)
  → {Which domain?}
    → Funding Agent (fully implemented)
    → Liquidity Agent (stub — replaced in Stage 5)
    → Capital Agent (stub — replaced in Stage 5)
    → ALM Agent (stub — replaced in Stage 5)
    → General Handler (no specialist match)

Each agent → Escalation Check
  → {Breach detected?}
    → Yes: Flag for HOD notification
    → No: Continue

→ Synthesize Response (combine answer + citations)
→ END (return to caller)

Side flow (labelled "Completed in Stage 5-6"):
  Agent → Staging Writer → /data/staging/pending/
  → Email Notifier → HOD
  → Approval UI → {HOD Decision?}
    → Approve: Sync-back to corporate
    → Edit: Modify then approve
    → Reject: Move to rejected/
```

**Sequence: Query Through the Graph**
```
Participants: Slack Bot, FastAPI, LangGraph, LLM, Qdrant, Agent, Staging Writer
Flow:
  1. Slack Bot POSTs query to Orchestrator /query
  2. FastAPI invokes compiled LangGraph
  3. classify_intent node calls LLM → returns domain tag
  4. retrieve_context node queries Qdrant → returns relevant chunks
  5. Router sends state to matched specialist agent
  6. Agent generates response using skill + retrieved context
  7. Agent optionally writes staging proposal (Excel change)
  8. escalation_check evaluates breach rules
  9. synthesise_response assembles final answer with citations
  10. Response returned to Slack Bot
```

### Stage 5 — Agents + Staging Writer (`2026-03-31-stage5-agents-staging.md`)

**Flowchart: Specialist Agents & Staging Pipeline**
```
Subgraph: Agent Processing (blue)
  Skills Loader reads SKILL.md files →
  Base Agent loads domain knowledge →
  {Which specialist?}
    → Funding Agent (skills: funding-facilities.md)
    → Liquidity Agent (skills: liquidity-analysis.md)
    → Capital Agent (skills: capital-allocation.md)
    → ALM Agent (skills: alm-review.md)

Each agent:
  → Analyze with LLM + skills context
  → {Proposes Excel change?}
    → Yes: Validate Proposal
      → {Confidence > threshold?}
        → Yes: Write to staging
        → No: Include caveat in response, no proposal
      → {Validation passes?}
        → Yes: Write to /data/staging/pending/ with audit trail
        → No: Block proposal (fail-closed)
    → No: Return answer only

Subgraph: Escalation (green)
  → Escalation Check evaluates breach rules
  → {Breach detected?}
    → Yes: Notify email-notifier → HOD alerted
    → No: Continue

Subgraph: Approval (green — completed in Stage 6)
  → Staging proposal → Email HOD
  → HOD opens Approval UI
  → {HOD Decision?}
    → Approve → sync-back to corporate → archive
    → Edit → modify then approve
    → Reject → move to rejected/ → archive
```

**Sequence: Agent Skill Loading → Proposal → Approval**
```
Participants: Orchestrator, Skills Loader, Specialist Agent, LLM, Staging Writer, Email Notifier, HOD
Flow:
  1. Orchestrator routes query to specialist agent
  2. Skills Loader reads SKILL.md domain knowledge
  3. Agent builds prompt from skill + retrieved context
  4. Agent calls LLM for analysis
  5. Agent determines if Excel change needed
  6. If yes: Validate proposal (fail-closed on parse error)
  7. If valid + confident: Staging Writer saves to /data/staging/pending/
  8. Audit trail linked via interaction_id
  9. Email Notifier sends approval link to HOD
  10. HOD reviews in Approval UI → approve/edit/reject
Error path: If proposal validation fails → block proposal, log, continue with text-only response
```

---

## Summary File — `docs/superpowers/system-flow-summary.md`

### Flowchart 1: Stage Build Progression
```
Stage 1: Infrastructure
  Produces: Docker network, Postgres, Qdrant, MinIO, Gateway, data zones, configs
  ↓
Stage 2: RAG Ingestion
  Consumes: Qdrant, MinIO, vLLM embeddings
  Produces: Document/chat indexing pipeline, vector collections
  ↓
Stage 3: Slack Bot
  Consumes: RAG Ingestion API
  Produces: Slack event processing, file forwarding, thread replies
  ↓
Stage 4: CAC Orchestrator
  Consumes: Qdrant (via RAG), vLLM reasoning, Slack Bot queries
  Produces: Intent classification, agent routing (stubs), staging writer (stub), synthesized responses
  ↓
Stage 5: Agents + Staging Writer
  Consumes: Skills (SKILL.md files), LLM, staging pipeline
  Produces: Real specialist agents, validated staging proposals, escalation wiring, audit trails
  ↓
Stage 6+ (future): Approval UI, Sync-back, Email Notifier, Obsidian, Paperclip
```

### Flowchart 2: Master End-to-End System Flow
```
Corporate Data → Sync Mirror (every 15 min) → /data/mirror/ (read-only)

User posts in Slack #cac-committee
  → Slack Bot receives event
  → Decision: Is it from a monitored channel? → No: ignore
  → Decision: Is it from a bot? → Yes: ignore
  → If question (@mention):
      → CAC Orchestrator classifies intent
      → Retrieves context from Qdrant
      → Routes to specialist agent
      → Agent reads mirror data + skills
      → Agent generates response
      → {Proposes Excel change?}
        → Yes: Validate proposal
          → {Valid + confident?}
            → Yes: Write to /data/staging/pending/
              → Email HOD with approval link
              → HOD opens Approval UI (port 4000)
              → {HOD Decision?}
                → Approve: Sync-back writes to corporate → archive
                → Edit: Modify then approve → sync-back → archive
                → Reject: Move to rejected/ → archive
            → No: Include caveat, no proposal
        → No: Return response only
      → {Escalation triggered?}
        → Yes: Notify HOD via email
        → No: Continue
      → Synthesize response with citations
      → Post threaded reply in Slack
  → If message: Index in Qdrant for future retrieval
  → If file: Download → duplicate check → chunk → embed → store in Qdrant
```

### Decision Table

| # | Decision Point | Who Decides | Inputs | Outcomes |
|---|---------------|-------------|--------|----------|
| 1 | Channel monitoring | Slack Bot (rule-based) | Channel ID vs. `dept_channels.json` | Monitored → process / unmonitored → ignore |
| 2 | Bot message filtering | Slack Bot (rule-based) | Event sender | Human → process / bot → ignore (prevent loops) |
| 3 | Event type routing | Slack Bot (rule-based) | Slack event type | message / file / @mention |
| 4 | File type validation | Slack Bot (rule-based) | File extension | Supported → ingest / unsupported → skip |
| 5 | Duplicate check | RAG Ingestion (hash-based) | Document content hash | New → ingest / duplicate → skip |
| 6 | Intent classification | AI (Qwen 122B) | User question text | funding / liquidity / capital / ALM / general |
| 7 | Agent routing | Orchestrator (rule-based) | Classified intent | Route to matched specialist agent |
| 8 | Staging proposal | AI (specialist agent) | Query + context + skill knowledge | Propose Excel change / response only |
| 9 | Confidence threshold | AI (specialist agent) | Evidence quality score | High → propose / low → caveat in response |
| 10 | Proposal validation | Rule engine (fail-closed) | Proposal schema + cell reference | Valid → stage / invalid → block |
| 11 | Escalation check | Rule engine | Breach rules from `escalation_rules.json` | Escalate to HOD / continue normally |
| 12 | Change approval | Human (HOD) | Diff view in Approval UI | Approve / edit / reject |

---

## Implementation Approach

**Execution:** Use team agents in parallel across the 5 plan docs, then create the summary file.

**Parallelizable work:**
- All 5 inline diagram insertions are independent (different files)
- Summary file depends on understanding all 5 stages (do last)

**Estimated tasks:** 6 file edits (5 plan docs + 1 new summary file)

---

## Acceptance Criteria

1. Each of the 5 plan docs has a `## System Overview` section after the header with 2 Mermaid diagrams
2. All diagrams render correctly in GitHub Markdown, VS Code Mermaid extension, and Obsidian
3. No code-level labels — all business language
4. Color classes defined via `classDef`/`class` with legend at bottom of each diagram
5. `docs/superpowers/system-flow-summary.md` contains stage progression, master end-to-end flow, and decision table
6. Existing plan content is unchanged (diagrams are additive only)
7. Stage 4 diagram labels future-stage components as "(Completed in Stage 5-6)"
8. Each diagram includes a color legend
9. Stage 1 references the architecture design spec for the static view
10. HOD approval outcomes include approve/edit/reject (3 options, not 2)
