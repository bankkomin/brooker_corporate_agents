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
