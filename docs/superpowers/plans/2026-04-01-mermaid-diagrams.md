# Mermaid Diagrams — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add HOD-readable Mermaid flowcharts and sequence diagrams to all 5 plan documents, plus create a new system-flow-summary file with stage progression, end-to-end flow, and decision table.

**Architecture:** Pure documentation task — no code changes. Insert a `## System Overview` section (flowchart + sequence diagram) after the header block in each plan doc. Create one new summary file. All diagrams use `classDef`/`class` color coding with per-diagram legends.

**Tech Stack:** Mermaid markdown syntax (compatible with GitHub, VS Code, Obsidian)

**Spec:** `docs/superpowers/specs/2026-04-01-mermaid-diagrams-design.md`

---

## File Map

### Modified Files (insert `## System Overview` section after header `---`)

| File | Insert After Line | Content |
|------|-------------------|---------|
| `docs/superpowers/plans/2026-03-25-stage1-infrastructure.md` | Line 14 (`---`) | Infrastructure runtime flowchart + startup sequence diagram |
| `docs/superpowers/plans/2026-03-30-stage2-4-rag-orchestrator.md` | Line 9 (`---`) | RAG + query pipeline flowchart + query flow sequence diagram |
| `docs/superpowers/plans/2026-03-30-stage3-slack-bot.md` | Line 13 (`---`) | Event routing flowchart + message lifecycle sequence diagram |
| `docs/superpowers/plans/2026-03-30-stage4-cac-orchestrator.md` | Line 15 (`---`) | LangGraph pipeline flowchart + query graph sequence diagram |
| `docs/superpowers/plans/2026-03-31-stage5-agents-staging.md` | Line 15 (`---`) | Agent + staging flowchart + proposal flow sequence diagram |

### New File

| File | Content |
|------|---------|
| `docs/superpowers/system-flow-summary.md` | Stage progression flowchart + master end-to-end flowchart + decision table |

---

## Dependency DAG

```
Tasks 1-5 are fully independent (different files) → can run in parallel
Task 6 (summary file) depends on Tasks 1-5 being complete (needs all diagrams finalized)
Task 7 (verification) depends on Task 6
```

---

## Task Breakdown

### Task 1: Stage 1 — Infrastructure Diagrams

**Files:**
- Modify: `docs/superpowers/plans/2026-03-25-stage1-infrastructure.md` — insert after line 14

- [ ] **Step 1: Insert `## System Overview` section with flowchart and sequence diagram**

Insert the following block immediately after the first `---` (line 14), before `## File Map`:

````markdown

## System Overview

> *For the static architecture layout, see [Architecture Design Spec](../specs/2026-03-25-architecture-design.md).*
> *These diagrams show runtime connectivity and startup sequence.*

### Infrastructure Runtime

```mermaid
flowchart TD
    subgraph EXT["External Systems"]
        VLLM_R["vLLM 122B<br/>Reasoning Model"]
        VLLM_E["vLLM 9B<br/>Embedding Model"]
        CORP["Corporate<br/>Data Sources"]
    end

    subgraph DOCKER["Docker Network (agent-net)"]
        GW["Gateway<br/>API Entry Point<br/>Port 3000"]
        NGINX["nginx<br/>Load Balancer"]
        PG[("PostgreSQL<br/>State & Checkpoints")]
        QD[("Qdrant<br/>Vector Search")]
        MINIO[("MinIO<br/>Document Storage")]
    end

    subgraph ZONES["Data Zones"]
        Z1[("Zone 1: /data/mirror/<br/>Read-Only to Agents")]
        Z2[("Zone 2: /data/staging/<br/>Agent Proposals")]
        Z4[("Zone 4: /data/archive/<br/>Permanent Audit")]
    end

    CORP -->|"Sync every 15 min"| Z1
    GW --> PG
    GW --> QD
    GW --> MINIO
    NGINX --> VLLM_R
    NGINX --> VLLM_E
    GW --> NGINX

    classDef automated fill:#e1f0ff,stroke:#4a90d9,color:#333
    classDef external fill:#fff3e0,stroke:#ff9800,color:#333
    classDef storage fill:#f3e5f5,stroke:#9c27b0,color:#333

    class GW,NGINX,PG,QD,MINIO automated
    class VLLM_R,VLLM_E,CORP external
    class Z1,Z2,Z4 storage
```

> **Legend:** 🔵 Blue = Automated services · 🟣 Purple = Data zones (storage) · 🟠 Orange = External systems

### System Startup Sequence

```mermaid
sequenceDiagram
    participant DC as Docker Compose
    participant PG as PostgreSQL
    participant QD as Qdrant
    participant MI as MinIO
    participant NX as nginx
    participant GW as Gateway

    DC->>PG: 1. Start database
    activate PG
    PG-->>DC: Ready (schema migrated)
    deactivate PG

    DC->>QD: 2. Start vector store
    activate QD
    QD-->>DC: Ready
    deactivate QD

    DC->>MI: 3. Start document store
    activate MI
    MI-->>DC: Ready
    deactivate MI

    DC->>NX: 4. Start load balancer
    activate NX
    NX->>NX: Check vLLM health
    alt vLLM reachable
        NX-->>DC: Healthy
    else vLLM unreachable
        NX-->>DC: Unhealthy (dev mode continues)
    end
    deactivate NX

    DC->>GW: 5. Start gateway
    activate GW
    GW->>PG: Verify connection
    GW->>QD: Verify connection
    GW-->>DC: Ready on port 3000
    deactivate GW

    Note over DC,GW: Health check script verifies all services
```

````

- [ ] **Step 2: Verify Mermaid renders correctly**

Open the file in VS Code with Mermaid preview extension or Obsidian. Verify both diagrams render without syntax errors.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-03-25-stage1-infrastructure.md
git commit -m "docs: add Mermaid diagrams to Stage 1 infrastructure plan"
```

---

### Task 2: Stage 2+4 — RAG & Orchestrator Diagrams

**Files:**
- Modify: `docs/superpowers/plans/2026-03-30-stage2-4-rag-orchestrator.md` — insert after line 9

- [ ] **Step 1: Insert `## System Overview` section with flowchart and sequence diagram**

Insert the following block immediately after the first `---` (line 9), before `## Overview`:

````markdown

## System Overview

### Document Ingestion & Query Pipeline

```mermaid
flowchart TD
    subgraph INGEST["Document Ingestion"]
        DOC["Document Uploaded<br/>(PDF, DOCX, XLSX, MD)"]
        CHAT["Chat Message<br/>from Slack"]
        DUP{{"Duplicate<br/>detected?"}}
        CHUNK["Chunker<br/>Split by file type"]
        EMBED["Embedder<br/>Qwen 9B model"]
        CIDX["Chat Indexer"]
    end

    subgraph STORE["Vector Storage"]
        QD_D[("Qdrant<br/>cac_docs collection")]
        QD_C[("Qdrant<br/>cac_chat collection")]
    end

    subgraph QUERY["Query Pipeline"]
        QUEST["User Question"]
        CLASSIFY{{"Classify Intent<br/>(AI determines domain)"}}
        RETRIEVE["Retrieve Relevant<br/>Documents from Qdrant"]
        FUND["Funding Agent"]
        LIQ["Liquidity Agent"]
        CAP["Capital Agent"]
        ALM["ALM Agent"]
        GEN["General Handler"]
        ESC{{"Escalation<br/>check"}}
        SYNTH["Synthesize Response<br/>with Citations"]
    end

    DOC --> DUP
    DUP -->|"No"| CHUNK
    DUP -->|"Yes: skip"| SKIP(("Skip"))
    CHUNK --> EMBED --> QD_D
    CHAT --> CIDX --> QD_C

    QUEST --> CLASSIFY
    CLASSIFY --> RETRIEVE
    RETRIEVE -->|"Funding"| FUND
    RETRIEVE -->|"Liquidity"| LIQ
    RETRIEVE -->|"Capital"| CAP
    RETRIEVE -->|"ALM"| ALM
    RETRIEVE -->|"General"| GEN
    FUND & LIQ & CAP & ALM & GEN --> ESC
    ESC -->|"No breach"| SYNTH
    ESC -->|"Breach detected"| HOD["Flag for HOD"]
    HOD --> SYNTH

    classDef automated fill:#e1f0ff,stroke:#4a90d9,color:#333
    classDef human fill:#e1f5e1,stroke:#4caf50,color:#333
    classDef external fill:#fff3e0,stroke:#ff9800,color:#333

    class DOC,CHAT,QUEST external
    class DUP,CHUNK,EMBED,CIDX,CLASSIFY,RETRIEVE,FUND,LIQ,CAP,ALM,GEN,ESC,SYNTH automated
    class HOD human
```

> **Legend:** 🔵 Blue = Automated services · 🟢 Green = Human actions · 🟠 Orange = External inputs

### End-to-End Query Flow

```mermaid
sequenceDiagram
    participant U as User (Slack)
    participant SB as Slack Bot
    participant ORC as Orchestrator
    participant LLM as LLM (Qwen 122B)
    participant QD as Qdrant
    participant AGT as Specialist Agent

    U->>SB: 1. Ask question in #cac-committee
    SB->>ORC: 2. Forward query

    activate ORC
    ORC->>LLM: 3. Classify intent
    LLM-->>ORC: Domain tag (e.g. "funding")

    ORC->>QD: 4. Retrieve relevant documents
    QD-->>ORC: Matching chunks + scores

    ORC->>AGT: 5. Route to specialist agent
    activate AGT
    AGT->>LLM: 6. Analyze with skill context
    LLM-->>AGT: Analysis + optional proposal
    AGT-->>ORC: 7. Response + citations
    deactivate AGT

    ORC-->>SB: 8. Synthesized response
    deactivate ORC

    SB-->>U: 9. Threaded reply with citations

    alt LLM timeout
        ORC-->>SB: Retry once, then "unable to process"
    end
```

````

- [ ] **Step 2: Verify Mermaid renders correctly**

Open the file in VS Code with Mermaid preview or Obsidian. Verify both diagrams render without syntax errors.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-03-30-stage2-4-rag-orchestrator.md
git commit -m "docs: add Mermaid diagrams to Stage 2+4 RAG & orchestrator plan"
```

---

### Task 3: Stage 3 — Slack Bot Diagrams

**Files:**
- Modify: `docs/superpowers/plans/2026-03-30-stage3-slack-bot.md` — insert after line 13

- [ ] **Step 1: Insert `## System Overview` section with flowchart and sequence diagram**

Insert the following block immediately after the first `---` (line 13), before `## File Map`:

````markdown

## System Overview

### Slack Event Routing

```mermaid
flowchart TD
    START(["Slack Event Received"])
    CHAN{{"Monitored<br/>channel?"}}
    BOT{{"From a<br/>bot?"}}
    TYPE{{"Event type?"}}
    MSG["Index message<br/>via RAG Ingestion"]
    FILE_DL["Download<br/>shared file"]
    FILE_OK{{"Supported<br/>file type?"}}
    FILE_FWD["Forward to RAG<br/>for ingestion"]
    FILE_SKIP(("Skip &<br/>log"))
    MENTION["Forward question<br/>to Orchestrator"]
    REPLY["Post threaded<br/>reply in Slack"]
    IGNORE1(("Ignore"))
    IGNORE2(("Ignore"))

    START --> CHAN
    CHAN -->|"No"| IGNORE1
    CHAN -->|"Yes"| BOT
    BOT -->|"Yes"| IGNORE2
    BOT -->|"No"| TYPE
    TYPE -->|"Message"| MSG
    TYPE -->|"File shared"| FILE_DL
    TYPE -->|"@agent mention"| MENTION
    FILE_DL --> FILE_OK
    FILE_OK -->|"Yes"| FILE_FWD
    FILE_OK -->|"No"| FILE_SKIP
    MSG --> REPLY
    FILE_FWD --> REPLY
    MENTION --> REPLY

    classDef automated fill:#e1f0ff,stroke:#4a90d9,color:#333
    classDef human fill:#e1f5e1,stroke:#4caf50,color:#333
    classDef external fill:#fff3e0,stroke:#ff9800,color:#333

    class MSG,FILE_DL,FILE_FWD,MENTION,REPLY automated
    class START external
    class CHAN,BOT,TYPE,FILE_OK automated
```

> **Legend:** 🔵 Blue = Automated processing · 🟠 Orange = External input (Slack)

### Message Processing Lifecycle

```mermaid
sequenceDiagram
    participant SA as Slack API
    participant SB as Slack Bot
    participant RAG as RAG Ingestion
    participant ORC as CAC Orchestrator

    SA->>SB: 1. Send event
    SB-->>SA: 2. ACK (within 3 seconds)

    Note over SB: Spawn background task

    alt @agent mention
        SB->>ORC: 3a. Forward question
        activate ORC
        ORC-->>SB: Response + citations
        deactivate ORC
        SB->>SA: 4a. Post threaded reply
    else Regular message
        SB->>RAG: 3b. Index message
        RAG-->>SB: Indexed OK
    else File shared
        SB->>SB: 3c. Download file
        SB->>RAG: Forward file for ingestion
        RAG-->>SB: Ingested OK
    end

    alt Service unreachable
        SB->>SA: Post "service unavailable" reply
    end
```

````

- [ ] **Step 2: Verify Mermaid renders correctly**

Open the file in VS Code with Mermaid preview or Obsidian. Verify both diagrams render without syntax errors.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-03-30-stage3-slack-bot.md
git commit -m "docs: add Mermaid diagrams to Stage 3 slack-bot plan"
```

---

### Task 4: Stage 4 — CAC Orchestrator Diagrams

**Files:**
- Modify: `docs/superpowers/plans/2026-03-30-stage4-cac-orchestrator.md` — insert after line 15

- [ ] **Step 1: Insert `## System Overview` section with flowchart and sequence diagram**

Insert the following block immediately after the first `---` (line 15), before `## CRITICAL Review Fixes`:

````markdown

## System Overview

### LangGraph Pipeline

```mermaid
flowchart TD
    START(["Query Received"])
    CLASSIFY{{"Classify Intent<br/>(LLM determines domain)"}}
    FUND["Funding Agent<br/>(fully implemented)"]
    LIQ["Liquidity Agent<br/>(stub → Stage 5)"]
    CAP["Capital Agent<br/>(stub → Stage 5)"]
    ALM_A["ALM Agent<br/>(stub → Stage 5)"]
    GEN["General Handler"]
    ESC{{"Escalation<br/>check"}}
    NOTIFY["Flag for<br/>HOD notification"]
    SYNTH["Synthesize Response<br/>(answer + citations)"]
    DONE(["Return to Caller"])

    subgraph FUTURE["Completed in Stage 5-6"]
        STG["Staging Writer"]
        STG_P[("Staging<br/>pending/")]
        EMAIL["Email Notifier"]
        HOD_R{{"HOD<br/>Decision?"}}
        APPROVE["Sync-back<br/>to corporate"]
        EDIT["Edit then<br/>approve"]
        REJECT["Move to<br/>rejected/"]
    end

    START --> CLASSIFY
    CLASSIFY -->|"Funding"| FUND
    CLASSIFY -->|"Liquidity"| LIQ
    CLASSIFY -->|"Capital"| CAP
    CLASSIFY -->|"ALM"| ALM_A
    CLASSIFY -->|"General"| GEN

    FUND & LIQ & CAP & ALM_A & GEN --> ESC
    ESC -->|"No breach"| SYNTH
    ESC -->|"Breach detected"| NOTIFY --> SYNTH
    SYNTH --> DONE

    FUND -.->|"Optional proposal"| STG
    STG --> STG_P --> EMAIL --> HOD_R
    HOD_R -->|"Approve"| APPROVE
    HOD_R -->|"Edit"| EDIT
    HOD_R -->|"Reject"| REJECT

    classDef automated fill:#e1f0ff,stroke:#4a90d9,color:#333
    classDef human fill:#e1f5e1,stroke:#4caf50,color:#333
    classDef external fill:#fff3e0,stroke:#ff9800,color:#333
    classDef future fill:#f5f5f5,stroke:#bbb,color:#888,stroke-dasharray: 5 5

    class CLASSIFY,FUND,LIQ,CAP,ALM_A,GEN,ESC,SYNTH automated
    class NOTIFY,HOD_R,APPROVE,EDIT,REJECT human
    class STG,STG_P,EMAIL future
```

> **Legend:** 🔵 Blue = Automated pipeline · 🟢 Green = Human actions · ⬜ Dashed = Future stages (5-6)

### Query Through the Graph

```mermaid
sequenceDiagram
    participant SB as Slack Bot
    participant API as FastAPI
    participant LG as LangGraph
    participant LLM as LLM (Qwen 122B)
    participant QD as Qdrant
    participant AGT as Specialist Agent

    SB->>API: 1. POST /query
    activate API
    API->>LG: 2. Invoke compiled graph

    activate LG
    LG->>LLM: 3. Classify intent
    LLM-->>LG: Domain tag

    LG->>QD: 4. Retrieve relevant context
    QD-->>LG: Relevant chunks

    LG->>AGT: 5. Route to specialist
    activate AGT
    AGT->>LLM: 6. Generate response (skill + context)
    LLM-->>AGT: Analysis
    AGT-->>LG: 7. Response + optional proposal
    deactivate AGT

    LG->>LG: 8. Check escalation rules
    LG->>LG: 9. Build response with citations
    LG-->>API: Final response
    deactivate LG

    API-->>SB: 10. JSON response
    deactivate API
```

````

- [ ] **Step 2: Verify Mermaid renders correctly**

Open the file in VS Code with Mermaid preview or Obsidian. Verify both diagrams render without syntax errors.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-03-30-stage4-cac-orchestrator.md
git commit -m "docs: add Mermaid diagrams to Stage 4 CAC orchestrator plan"
```

---

### Task 5: Stage 5 — Agents & Staging Diagrams

**Files:**
- Modify: `docs/superpowers/plans/2026-03-31-stage5-agents-staging.md` — insert after line 15

- [ ] **Step 1: Insert `## System Overview` section with flowchart and sequence diagram**

Insert the following block immediately after the first `---` (line 15), before `## File Structure`:

````markdown

## System Overview

### Specialist Agents & Staging Pipeline

```mermaid
flowchart TD
    subgraph SKILLS["Skill Loading"]
        SL["Skills Loader<br/>reads SKILL.md files"]
        SK_F["funding-facilities.md"]
        SK_L["liquidity-analysis.md"]
        SK_C["capital-allocation.md"]
        SK_A["alm-review.md"]
    end

    subgraph AGENTS["Agent Processing"]
        BA["Base Agent<br/>(loads domain knowledge)"]
        FUND["Funding Agent"]
        LIQ["Liquidity Agent"]
        CAP["Capital Agent"]
        ALM_A["ALM Agent"]
        ANALYZE["Analyze with<br/>LLM + skill context"]
        PROPOSE{{"Proposes Excel<br/>change?"}}
    end

    subgraph VALIDATE["Proposal Validation"]
        CONF{{"Confidence ><br/>threshold?"}}
        VALID{{"Validation<br/>passes?"}}
        WRITE["Write to<br/>/data/staging/pending/"]
        BLOCK(("Block proposal<br/>(fail-closed)"))
        CAVEAT["Include caveat<br/>in response"]
    end

    subgraph ESCALATION["Escalation"]
        ESC_CHK{{"Breach<br/>detected?"}}
        NOTIFY["Notify HOD<br/>via email-notifier"]
    end

    subgraph APPROVAL["Approval (Stage 6)"]
        EMAIL["Email HOD<br/>with approval link"]
        HOD_UI["HOD opens<br/>Approval UI"]
        DECIDE{{"HOD<br/>Decision?"}}
        SYNC["Sync-back<br/>to corporate"]
        EDIT["Edit then<br/>approve"]
        REJ["Move to<br/>rejected/"]
    end

    RESP(["Return response<br/>with citations"])

    SL --> SK_F & SK_L & SK_C & SK_A
    SK_F --> FUND
    SK_L --> LIQ
    SK_C --> CAP
    SK_A --> ALM_A
    BA --> FUND & LIQ & CAP & ALM_A
    FUND & LIQ & CAP & ALM_A --> ANALYZE
    ANALYZE --> PROPOSE
    PROPOSE -->|"No"| RESP
    PROPOSE -->|"Yes"| CONF
    CONF -->|"Low"| CAVEAT --> RESP
    CONF -->|"High"| VALID
    VALID -->|"Fail"| BLOCK
    VALID -->|"Pass"| WRITE

    WRITE --> EMAIL --> HOD_UI --> DECIDE
    DECIDE -->|"Approve"| SYNC
    DECIDE -->|"Edit"| EDIT
    DECIDE -->|"Reject"| REJ

    ANALYZE --> ESC_CHK
    ESC_CHK -->|"No"| RESP
    ESC_CHK -->|"Yes"| NOTIFY --> RESP

    classDef automated fill:#e1f0ff,stroke:#4a90d9,color:#333
    classDef human fill:#e1f5e1,stroke:#4caf50,color:#333
    classDef external fill:#fff3e0,stroke:#ff9800,color:#333

    class SL,SK_F,SK_L,SK_C,SK_A,BA,FUND,LIQ,CAP,ALM_A,ANALYZE,CONF,VALID,WRITE automated
    class PROPOSE,ESC_CHK automated
    class NOTIFY,EMAIL,HOD_UI,DECIDE,SYNC,EDIT,REJ human
```

> **Legend:** 🔵 Blue = Automated processing · 🟢 Green = Human actions / approval gates

### Agent Skill Loading → Proposal → Approval

```mermaid
sequenceDiagram
    participant ORC as Orchestrator
    participant SL as Skills Loader
    participant AGT as Specialist Agent
    participant LLM as LLM (Qwen 122B)
    participant SW as Staging Writer
    participant EN as Email Notifier
    participant HOD as HOD (Human)

    ORC->>AGT: 1. Route query to specialist
    AGT->>SL: 2. Load SKILL.md domain knowledge
    SL-->>AGT: Skill content

    AGT->>LLM: 3. Build prompt (skill + context)
    activate LLM
    LLM-->>AGT: 4. Analysis result
    deactivate LLM

    alt Excel change proposed
        AGT->>AGT: 5. Validate proposal (fail-closed)
        alt Valid + confident
            AGT->>SW: 6. Save to /data/staging/pending/
            SW-->>AGT: Saved (interaction_id linked)
            SW->>EN: 7. Trigger approval email
            EN->>HOD: 8. Send approval link
            HOD->>HOD: 9. Review in Approval UI
            alt Approve
                HOD-->>EN: Approved → sync-back
            else Edit
                HOD-->>EN: Edit → modify → approve
            else Reject
                HOD-->>EN: Rejected → archive
            end
        else Invalid or low confidence
            AGT->>AGT: Block proposal, add caveat
        end
    end

    AGT-->>ORC: 10. Response + citations
```

````

- [ ] **Step 2: Verify Mermaid renders correctly**

Open the file in VS Code with Mermaid preview or Obsidian. Verify both diagrams render without syntax errors.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-03-31-stage5-agents-staging.md
git commit -m "docs: add Mermaid diagrams to Stage 5 agents & staging plan"
```

---

### Task 6: System Flow Summary (New File)

**Files:**
- Create: `docs/superpowers/system-flow-summary.md`

- [ ] **Step 1: Create the summary file with all 3 sections**

Create the file with the following content:

````markdown
# System Flow Summary — Corporate AI Agent

> **Audience:** Department Heads (HODs) — non-technical overview of system logic, data flow, and decision points.
> **Last updated:** 2026-04-01

---

## Stage Build Progression

Each stage builds on the previous one. This shows what each stage produces and what the next stage needs from it.

```mermaid
flowchart TD
    S1["<b>Stage 1: Infrastructure</b><br/>Docker, Postgres, Qdrant, MinIO,<br/>Gateway, data zones, configs"]
    S2["<b>Stage 2: RAG Ingestion</b><br/>Document chunking, embedding,<br/>vector storage, chat indexing"]
    S3["<b>Stage 3: Slack Bot</b><br/>Slack event processing,<br/>file forwarding, thread replies"]
    S4["<b>Stage 4: CAC Orchestrator</b><br/>Intent classification, agent routing,<br/>staging writer stub, response synthesis"]
    S5["<b>Stage 5: Agents + Staging</b><br/>Real specialist agents, validated<br/>staging proposals, escalation wiring"]
    S6["<b>Stage 6+: Approval & Integration</b><br/>Approval UI, sync-back,<br/>email notifier, Obsidian, Paperclip"]

    S1 -->|"Provides: databases,<br/>storage, networking"| S2
    S2 -->|"Provides: vector<br/>search API"| S3
    S3 -->|"Provides: Slack<br/>event bridge"| S4
    S4 -->|"Provides: agent<br/>graph framework"| S5
    S5 -->|"Provides: validated<br/>proposals"| S6

    classDef stage fill:#e1f0ff,stroke:#4a90d9,color:#333
    class S1,S2,S3,S4,S5,S6 stage
```

---

## Master End-to-End System Flow

This shows how data moves through the entire system — from corporate data sources to final approved changes.

```mermaid
flowchart TD
    CORP["Corporate<br/>Data Sources"]
    MIRROR[("Zone 1: /data/mirror/<br/>Read-Only")]
    SLACK["User posts in<br/>Slack #cac-committee"]

    CHAN{{"Monitored<br/>channel?"}}
    BOT_CHK{{"From a<br/>bot?"}}
    EVT{{"Event<br/>type?"}}

    IDX["Index message<br/>in Qdrant"]
    FILE_DL["Download file"]
    DUP{{"Duplicate?"}}
    CHUNK["Chunk → Embed<br/>→ Store in Qdrant"]
    SKIP1(("Skip"))

    CLASSIFY{{"Classify intent<br/>(AI)"}}
    RETRIEVE["Retrieve context<br/>from Qdrant"]
    AGENT["Specialist Agent<br/>analyzes with skills"]

    PROPOSE{{"Proposes Excel<br/>change?"}}
    VALIDATE{{"Valid +<br/>confident?"}}
    STAGE[("Zone 2: /data/staging/<br/>pending/")]
    CAVEAT["Include caveat<br/>no proposal"]

    ESC{{"Escalation<br/>triggered?"}}
    ESC_NOTIFY["Notify HOD<br/>via email"]

    EMAIL["Email HOD<br/>approval link"]
    HOD_UI["HOD reviews in<br/>Approval UI<br/>(port 4000)"]
    DECIDE{{"HOD<br/>Decision?"}}
    SYNC["Sync-back to<br/>corporate"]
    EDIT_A["Edit then<br/>approve"]
    REJ["Move to<br/>rejected/"]
    ARCHIVE[("Zone 4: /data/archive/<br/>Permanent Audit")]

    SYNTH["Synthesize response<br/>with citations"]
    REPLY["Post threaded<br/>reply in Slack"]

    IGNORE1(("Ignore"))
    IGNORE2(("Ignore"))

    CORP -->|"Sync every 15 min"| MIRROR
    SLACK --> CHAN
    CHAN -->|"No"| IGNORE1
    CHAN -->|"Yes"| BOT_CHK
    BOT_CHK -->|"Yes"| IGNORE2
    BOT_CHK -->|"No"| EVT

    EVT -->|"Message"| IDX --> REPLY
    EVT -->|"File"| FILE_DL --> DUP
    DUP -->|"Yes"| SKIP1
    DUP -->|"No"| CHUNK --> REPLY

    EVT -->|"@mention"| CLASSIFY
    CLASSIFY --> RETRIEVE --> AGENT

    AGENT --> PROPOSE
    PROPOSE -->|"No"| ESC
    PROPOSE -->|"Yes"| VALIDATE
    VALIDATE -->|"No"| CAVEAT --> ESC
    VALIDATE -->|"Yes"| STAGE
    STAGE --> EMAIL --> HOD_UI --> DECIDE
    DECIDE -->|"Approve"| SYNC --> ARCHIVE
    DECIDE -->|"Edit"| EDIT_A --> SYNC
    DECIDE -->|"Reject"| REJ --> ARCHIVE

    ESC -->|"Yes"| ESC_NOTIFY
    ESC -->|"No"| SYNTH
    ESC_NOTIFY --> SYNTH
    SYNTH --> REPLY

    classDef automated fill:#e1f0ff,stroke:#4a90d9,color:#333
    classDef human fill:#e1f5e1,stroke:#4caf50,color:#333
    classDef external fill:#fff3e0,stroke:#ff9800,color:#333

    class CORP,SLACK external
    class MIRROR,STAGE,ARCHIVE automated
    class IDX,FILE_DL,CHUNK,CLASSIFY,RETRIEVE,AGENT,SYNTH,REPLY automated
    class CHAN,BOT_CHK,EVT,DUP,PROPOSE,VALIDATE,ESC automated
    class EMAIL,HOD_UI,DECIDE,SYNC,EDIT_A,REJ,ESC_NOTIFY human
```

> **Legend:** 🔵 Blue = Automated processing · 🟢 Green = Human actions / approval gates · 🟠 Orange = External systems

---

## Decision Table

Every point where the system makes a choice or requires human input:

| # | Decision Point | Who Decides | Inputs | Possible Outcomes |
|---|---------------|-------------|--------|-------------------|
| 1 | **Channel monitoring** | Slack Bot (rule-based) | Channel ID vs. `dept_channels.json` | Monitored → process / Unmonitored → ignore |
| 2 | **Bot message filtering** | Slack Bot (rule-based) | Event sender | Human → process / Bot → ignore (prevent loops) |
| 3 | **Event type routing** | Slack Bot (rule-based) | Slack event type | Message / File / @mention |
| 4 | **File type validation** | Slack Bot (rule-based) | File extension | Supported → ingest / Unsupported → skip |
| 5 | **Duplicate check** | RAG Ingestion (hash-based) | Document content hash | New → ingest / Duplicate → skip |
| 6 | **Intent classification** | AI (Qwen 122B LLM) | User question text | Funding / Liquidity / Capital / ALM / General |
| 7 | **Agent routing** | Orchestrator (rule-based) | Classified intent | Route to matched specialist agent |
| 8 | **Staging proposal** | AI (specialist agent) | Query + context + skill knowledge | Propose Excel change / Response only |
| 9 | **Confidence threshold** | AI (specialist agent) | Evidence quality score | High → propose / Low → caveat in response |
| 10 | **Proposal validation** | Rule engine (fail-closed) | Proposal schema + cell reference | Valid → stage / Invalid → block |
| 11 | **Escalation check** | Rule engine | Breach rules from `escalation_rules.json` | Escalate to HOD / Continue normally |
| 12 | **Change approval** | **Human (HOD)** | Diff view in Approval UI | **Approve** / **Edit** / **Reject** |
````

- [ ] **Step 2: Verify Mermaid renders correctly**

Open the file in VS Code with Mermaid preview or Obsidian. Verify all 3 diagrams render without syntax errors.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/system-flow-summary.md
git commit -m "docs: create system flow summary with Mermaid diagrams and decision table"
```

---

### Task 7: Final Verification

- [ ] **Step 1: Verify all 6 files have correct diagrams**

```bash
# Count mermaid code blocks in each file
grep -c '```mermaid' docs/superpowers/plans/2026-03-25-stage1-infrastructure.md
# Expected: 2

grep -c '```mermaid' docs/superpowers/plans/2026-03-30-stage2-4-rag-orchestrator.md
# Expected: 2

grep -c '```mermaid' docs/superpowers/plans/2026-03-30-stage3-slack-bot.md
# Expected: 2

grep -c '```mermaid' docs/superpowers/plans/2026-03-30-stage4-cac-orchestrator.md
# Expected: 2

grep -c '```mermaid' docs/superpowers/plans/2026-03-31-stage5-agents-staging.md
# Expected: 2

grep -c '```mermaid' docs/superpowers/system-flow-summary.md
# Expected: 3
```

- [ ] **Step 2: Verify no code-level labels leaked into diagrams**

```bash
# Should return 0 results — no function names in mermaid blocks
grep -A 100 '```mermaid' docs/superpowers/plans/*.md docs/superpowers/system-flow-summary.md | grep -E '\.(py|js|ts)|def |class |import |async '
# Expected: no matches
```

- [ ] **Step 3: Verify existing plan content unchanged**

```bash
# Check that only the System Overview section was added — no other lines modified
git diff --stat docs/superpowers/plans/
# Expected: 5 files changed, only insertions (no deletions)
```

---

## Summary

| Task | File | Diagrams | Parallelizable |
|------|------|----------|----------------|
| 1 | Stage 1 infrastructure plan | Flowchart + Sequence | Yes (with 2-5) |
| 2 | Stage 2+4 RAG & orchestrator plan | Flowchart + Sequence | Yes (with 1,3-5) |
| 3 | Stage 3 slack-bot plan | Flowchart + Sequence | Yes (with 1-2,4-5) |
| 4 | Stage 4 CAC orchestrator plan | Flowchart + Sequence | Yes (with 1-3,5) |
| 5 | Stage 5 agents & staging plan | Flowchart + Sequence | Yes (with 1-4) |
| 6 | System flow summary (new) | 2 Flowcharts + Decision table | After 1-5 |
| 7 | Final verification | — | After 6 |
