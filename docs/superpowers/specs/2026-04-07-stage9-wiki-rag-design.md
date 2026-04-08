# Stage 9 Design Spec: Wiki RAG Knowledge Base

**Date:** 2026-04-07
**Stage:** 9 (Post Go-Live — Week 9+)
**Status:** Approved design, pending implementation
**PRD Reference:** PRD.md v2.2, Section 16 (Obsidian Vault Integration), FR-12
**Pattern:** [Karpathy LLM Knowledge Bases](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
**Plan:** `docs/superpowers/plans/2026-04-07-stage9-wiki-rag.md`

---

## Visual Overview

### How the LLM Wiki Pattern Works (Big Picture)

```mermaid
flowchart TD
    subgraph SOURCES["Raw Sources (Human Adds)"]
        S1[Slack Messages]
        S2[Uploaded Documents]
        S3[Excel Trackers]
        S4[Meeting Discussions]
        S5[Policy Documents]
    end

    subgraph COMPILER["Wiki Compiler (AI Does This)"]
        C1[Read New Source]
        C2[Identify Key Concepts]
        C3[Write Wiki Articles]
        C4[Update Index & Links]
        C5[Flag Contradictions]
    end

    subgraph WIKI["Obsidian Wiki (AI Maintains)"]
        W1[index.md\nMaster Catalog]
        W2[concepts/\nTopic Articles]
        W3[decisions/\nApproval Records]
        W4[meeting-notes/\nDiscussion Summaries]
        W5[trends/\nPeriodic Analysis]
        W6[log.md\nActivity Record]
    end

    subgraph USERS["Who Benefits"]
        U1[Committee Members\nBrowse in Obsidian]
        U2[AI Agents\nAnswer Questions Better]
        U3[HODs\nReview Decisions]
        U4[Auditors\nCompliance Review]
    end

    S1 & S2 & S3 & S4 & S5 --> C1
    C1 --> C2 --> C3 --> C4 --> C5
    C3 --> W2 & W3 & W4 & W5
    C4 --> W1
    C5 --> W6
    W1 & W2 & W3 & W4 & W5 --> U1 & U2 & U3 & U4

    style SOURCES fill:#e1f5fe,stroke:#01579b
    style COMPILER fill:#fff3e0,stroke:#e65100
    style WIKI fill:#e8f5e9,stroke:#1b5e20
    style USERS fill:#f3e5f5,stroke:#4a148c
```

### RAG (Current) vs. Wiki Pattern (Proposed)

```mermaid
flowchart LR
    subgraph CURRENT["Current: RAG Approach"]
        direction TB
        R1[User Asks Question] --> R2[Search Vector Database]
        R2 --> R3[Retrieve Raw Chunks]
        R3 --> R4[AI Synthesizes Answer\nfrom Scratch Every Time]
        R4 --> R5[Answer Sent]
        R5 -.->|Knowledge Lost| R1
    end

    subgraph PROPOSED["Proposed: Wiki Pattern"]
        direction TB
        P1[New Data Arrives] --> P2[AI Compiles\ninto Wiki Article]
        P2 --> P3[Knowledge Stored\nin Obsidian]
        P3 --> P4[User Asks Question]
        P4 --> P5[AI Reads Pre-Built\nWiki Articles]
        P5 --> P6[Better Answer\nwith Full Context]
        P6 -.->|Knowledge Compounds| P3
    end

    style CURRENT fill:#ffebee,stroke:#b71c1c
    style PROPOSED fill:#e8f5e9,stroke:#1b5e20
```

### Three-Layer Architecture

```mermaid
flowchart TB
    subgraph L1["Layer 1: Raw Sources (Read-Only)"]
        direction LR
        R1["/data/mirror/\nCorporate Excel & Docs"]
        R2["Slack Messages\n#cac-committee"]
        R3["Uploaded Files\nPDF, XLSX, DOCX"]
        R4["Postgres Tables\nProposals & Decisions"]
    end

    subgraph L2["Layer 2: Wiki (AI-Maintained)"]
        direction LR
        W1["index.md\nMaster Catalog"]
        W2["concepts/\nLCR, CAR, Covenants..."]
        W3["decisions/\nApproval Records"]
        W4["meeting-notes/\nSlack Digests"]
        W5["entities/\nFacilities, People"]
        W6["log.md\nAll Operations"]
    end

    subgraph L3["Layer 3: Schema (Rules)"]
        direction LR
        S1["CLAUDE.md\nProject Rules"]
        S2["obsidian_watch.json\nWhat to Watch"]
        S3["wiki_schema.json\nArticle Format Rules"]
    end

    L1 -->|"AI reads\n(never writes)"| L2
    L3 -->|"Rules guide\nhow AI writes"| L2

    style L1 fill:#e3f2fd,stroke:#1565c0
    style L2 fill:#e8f5e9,stroke:#2e7d32
    style L3 fill:#fff8e1,stroke:#f57f17
```

### How Knowledge Compounds Over Time

```mermaid
flowchart LR
    subgraph M1["Month 1"]
        A1["~20 Articles\nSkill docs +\ninitial decisions"]
    end

    subgraph M3["Month 3"]
        A3["~100 Articles\n+ Meeting notes\n+ Trend analysis"]
    end

    subgraph M6["Month 6"]
        A6["~300 Articles\nFull institutional\nmemory forming"]
    end

    subgraph M12["Month 12"]
        A12["~500+ Articles\nComplete committee\nknowledge base"]
    end

    M1 -->|"Decisions +\nMeetings"| M3
    M3 -->|"Patterns +\nTrends"| M6
    M6 -->|"Deep Context +\nHistory"| M12

    style M1 fill:#e8eaf6,stroke:#283593
    style M3 fill:#c5cae9,stroke:#283593
    style M6 fill:#9fa8da,stroke:#283593
    style M12 fill:#7986cb,stroke:#283593,color:#fff
```

### Integration with Existing Brooker System

```mermaid
flowchart TD
    subgraph EXISTING["Already Built (No Changes)"]
        SB[Slack Bot\nPort 3003]
        RAG[RAG Ingestion\nPort 3004]
        VW[VaultWatcher\nWatches Obsidian Vault]
        QD[(Qdrant\nVector Store)]
        CO[CAC Orchestrator\nPort 3001]
        PG[(Postgres\nAudit Tables)]
        PP[Paperclip\nPort 3100]
    end

    subgraph NEW["New Component (Phase 2)"]
        WC[Wiki Compiler\nService]
    end

    subgraph VAULT["Obsidian Vault"]
        OV[Wiki Articles\n.md Files]
    end

    SB -->|"Slack messages"| WC
    PG -->|"Approved proposals\n& decisions"| WC
    RAG -->|"New documents"| WC
    PP -->|"Events"| WC

    WC -->|"Writes articles"| OV
    OV -->|"VaultWatcher\nauto-detects changes"| VW
    VW -->|"Embeds to\ncac_knowledge"| QD
    QD -->|"Richer context\nfor queries"| CO

    OV -->|"Browsable in\nObsidian app"| USERS[Committee\nMembers & HODs]

    style EXISTING fill:#e8f5e9,stroke:#2e7d32
    style NEW fill:#fff3e0,stroke:#e65100
    style VAULT fill:#f3e5f5,stroke:#4a148c
```

### Event-to-Article Flow

```mermaid
flowchart LR
    subgraph EVENTS["Events That Trigger Wiki Updates"]
        E1["Proposal Approved\n(Paperclip event)"]
        E2["Slack Discussion\n(Daily digest)"]
        E3["Document Uploaded\n(RAG event)"]
        E4["Escalation Triggered\n(Alert event)"]
        E5["Weekly Schedule\n(Cron job)"]
    end

    subgraph ARTICLES["Wiki Articles Created"]
        A1["decisions/\n2026-04-07-funding-update.md"]
        A2["meeting-notes/\n2026-04-07-cac-weekly.md"]
        A3["concepts/\nliquidity-coverage-ratio.md"]
        A4["decisions/\n2026-04-07-escalation-lcr.md"]
        A5["trends/\n2026-Q2-liquidity-trends.md"]
    end

    E1 --> A1
    E2 --> A2
    E3 --> A3
    E4 --> A4
    E5 --> A5

    style EVENTS fill:#e3f2fd,stroke:#1565c0
    style ARTICLES fill:#e8f5e9,stroke:#2e7d32
```

### Phased Implementation Plan

```mermaid
flowchart TD
    subgraph PHASE1["Phase 1: Now (Pre Go-Live)"]
        P1A["Symlink SKILL.md\nfiles into vault"]
        P1B["Create seed\nconcept articles"]
        P1C["Install Obsidian\non team lead laptop"]
        P1D["Document wiki\narchitecture"]
    end

    subgraph PHASE2["Phase 2: Post Go-Live"]
        P2A["Build Wiki\nCompiler Service"]
        P2B["Auto-generate\ndecision articles"]
        P2C["Auto-generate\nmeeting summaries"]
        P2D["Add lint/health\ncheck workflow"]
        P2E["Install Dataview\n& Marp plugins"]
    end

    subgraph PHASE3["Phase 3: Scale"]
        P3A["Add QMD hybrid\nsearch if needed"]
        P3B["Trend analysis\n& reporting"]
        P3C["Committee briefing\nslide generation"]
    end

    PHASE1 --> PHASE2 --> PHASE3

    style PHASE1 fill:#e8f5e9,stroke:#2e7d32
    style PHASE2 fill:#fff3e0,stroke:#e65100
    style PHASE3 fill:#e3f2fd,stroke:#1565c0
```

### Department Boundary Architecture

```mermaid
flowchart TD
    subgraph VAULT["Obsidian Vault (Single Vault, Department Subdirectories)"]
        subgraph SHARED["shared/ — All Departments Can Read"]
            SI[index.md]
            SL[log.md]
            SS[skills/\nEscalation Protocol\nCitation Format\nRAG Retrieval\nExcel Navigation]
            SP[policies/\nCorporate Policies]
        end

        subgraph CAC["cac/ — CAC Department Only"]
            CI[index.md]
            CL[log.md]
            CS[skills/\nLiquidity Analysis\nCapital Allocation\nALM Review\nFunding Facilities]
            CC[concepts/\nLCR, CAR, NSFR\nCovenants, Duration Gap]
            CD[decisions/\nApproval Records]
            CM[meeting-notes/\nSlack Digests]
            CE[entities/\nFacilities, People]
            CT[trends/\nQuarterly Analysis]
        end

        subgraph RISK["risk/ — Risk Dept Only (Phase 2)"]
            RI[index.md]
            RC[concepts/]
            RD[decisions/]
        end
    end

    style SHARED fill:#e8f5e9,stroke:#2e7d32
    style CAC fill:#e3f2fd,stroke:#1565c0
    style RISK fill:#fff3e0,stroke:#e65100,stroke-dasharray: 5 5
```

### 4-Layer Department Boundary Enforcement

```mermaid
flowchart TD
    EVENT["Incoming Event\n(e.g. CAC Proposal Approved)"]

    subgraph LAYER1["Layer 1: Wiki Compiler\n(dept_router.py)"]
        L1["Routes event to\nobsidian-vault/cac/ only\n\nRejects writes to risk/\nor other dept folders"]
    end

    subgraph LAYER2["Layer 2: VaultWatcher\n(obsidian_watch.json)"]
        L2["Maps cac/* folders\nto cac_knowledge collection\n\nMaps shared/* folders\nto shared_policies collection"]
    end

    subgraph LAYER3["Layer 3: Qdrant\n(departments.json)"]
        L3["CAC agents can only query:\ncac_docs, cac_chat,\ncac_knowledge, shared_policies\n\nCannot access risk_* collections"]
    end

    subgraph LAYER4["Layer 4: Paperclip\n(Department Boundaries)"]
        L4["Ticket creation requires\nvalid dept_id\n\nEvent routing scoped\nto department agents"]
    end

    EVENT --> L1
    L1 -->|"Writes .md to\ncac/ folder"| L2
    L2 -->|"Embeds to\ncac_knowledge"| L3
    L3 -->|"CAC agents\nquery scoped data"| L4

    style LAYER1 fill:#e8f5e9,stroke:#2e7d32
    style LAYER2 fill:#e3f2fd,stroke:#1565c0
    style LAYER3 fill:#fff3e0,stroke:#e65100
    style LAYER4 fill:#f3e5f5,stroke:#4a148c
```

### Data Flow with Department Scoping

```mermaid
flowchart LR
    subgraph SOURCES["Data Sources"]
        S1["#cac-committee\nSlack Channel"]
        S2["CAC Documents\nPDF, XLSX"]
        S3["CAC Proposals\nApproved/Rejected"]
        S4["#risk-committee\nSlack Channel\n(Phase 2)"]
    end

    subgraph COMPILER["Wiki Compiler Service"]
        R1["dept_router.py\nIdentifies department\nfrom event metadata"]
    end

    subgraph VAULT["Obsidian Vault"]
        V1["cac/concepts/\ncac/decisions/\ncac/meeting-notes/"]
        V2["shared/policies/\nshared/skills/"]
        V3["risk/concepts/\nrisk/decisions/\n(Phase 2)"]
    end

    subgraph QDRANT["Qdrant Collections"]
        Q1["cac_knowledge\n(CAC articles)"]
        Q2["shared_policies\n(Shared articles)"]
        Q3["risk_knowledge\n(Phase 2)"]
    end

    subgraph AGENTS["AI Agents"]
        A1["Liquidity Agent\nReads: cac_knowledge\n+ shared_policies"]
        A2["Capital Agent\nReads: cac_knowledge\n+ shared_policies"]
        A3["Risk Agent\nReads: risk_knowledge\n+ shared_policies\n(Phase 2)"]
    end

    S1 & S2 & S3 --> R1
    S4 -.-> R1

    R1 -->|"dept=cac"| V1
    R1 -->|"dept=shared"| V2
    R1 -.->|"dept=risk"| V3

    V1 -->|VaultWatcher| Q1
    V2 -->|VaultWatcher| Q2
    V3 -.->|VaultWatcher| Q3

    Q1 & Q2 --> A1 & A2
    Q2 & Q3 -.-> A3

    style SOURCES fill:#e1f5fe,stroke:#01579b
    style COMPILER fill:#fff3e0,stroke:#e65100
    style VAULT fill:#e8f5e9,stroke:#1b5e20
    style QDRANT fill:#fce4ec,stroke:#880e4f
    style AGENTS fill:#f3e5f5,stroke:#4a148c
```

### Wiki Maintenance Agent Workflow

```mermaid
flowchart TD
    subgraph TRIGGER["Trigger"]
        T1["Weekly Cron\n(APScheduler)"]
        T2["Manual\n/lint Command"]
    end

    subgraph MAINTENANCE["Wiki Maintenance Agent"]
        M1["Read All Articles\nin Department Vault"]
        M2{"Run Checks"}
        M3["Contradiction\nDetection"]
        M4["Stale Data\nDetection"]
        M5["Orphan Page\nDetection"]
        M6["Missing Concept\nDetection"]
        M7["Coverage\nScoring"]
    end

    subgraph OUTPUT["Outputs"]
        O1["lint-report.md\nFindings & Actions"]
        O2["Updated Articles\nFixed Links, Tags"]
        O3["New Articles\nSuggested Concepts"]
        O4["log.md Entry\nLint Results"]
    end

    T1 & T2 --> M1
    M1 --> M2
    M2 --> M3 & M4 & M5 & M6 & M7
    M3 & M4 & M5 & M6 & M7 --> O1
    M4 --> O2
    M6 --> O3
    M3 & M4 & M5 & M6 & M7 --> O4

    style TRIGGER fill:#e3f2fd,stroke:#1565c0
    style MAINTENANCE fill:#fff3e0,stroke:#e65100
    style OUTPUT fill:#e8f5e9,stroke:#2e7d32
```

### Adding a New Department (Phase 2+)

```mermaid
flowchart LR
    subgraph STEP1["Step 1\nConfig"]
        S1["Add to\ndepartments.json\n\n- Qdrant collections\n- Mirror paths\n- Agents list"]
    end

    subgraph STEP2["Step 2\nVault"]
        S2["Create directory\nobsidian-vault/risk/\n\n- concepts/\n- decisions/\n- meeting-notes/\n- entities/"]
    end

    subgraph STEP3["Step 3\nWatch"]
        S3["Add entries to\nobsidian_watch.json\n\n- Map risk/* to\n  risk_knowledge\n  collection"]
    end

    subgraph STEP4["Step 4\nSkills"]
        S4["Create SKILL.md\nin skills/risk/\n\nSymlink into\nvault/risk/skills/"]
    end

    subgraph STEP5["Step 5\nRegister"]
        S5["Register agents\nin Paperclip\n\n- risk-credit\n- risk-market\n- etc."]
    end

    subgraph RESULT["Result"]
        R1["No code changes\nneeded in:\n- Wiki Compiler\n- VaultWatcher\n- Paperclip"]
    end

    STEP1 --> STEP2 --> STEP3 --> STEP4 --> STEP5 --> RESULT

    style STEP1 fill:#e3f2fd,stroke:#1565c0
    style STEP2 fill:#e8f5e9,stroke:#2e7d32
    style STEP3 fill:#fff3e0,stroke:#e65100
    style STEP4 fill:#f3e5f5,stroke:#4a148c
    style STEP5 fill:#fce4ec,stroke:#880e4f
    style RESULT fill:#e8f5e9,stroke:#2e7d32
```

### Confidentiality: Everything Stays On-Premise

```mermaid
flowchart TD
    subgraph DGX["DGX Spark (128GB, On-Premise)"]
        subgraph HOST["Host Machine"]
            LLM["Qwen3.5 122B\nLocal vLLM\nPort 8000"]
            EMB["Qwen3.5 9B\nLocal Embeddings\nPort 8002"]
        end

        subgraph DOCKER["Docker Containers (agent-net)"]
            WC["Wiki Compiler"]
            VW["VaultWatcher"]
            QD["Qdrant"]
            PG["Postgres"]
            PP["Paperclip"]
            CO["CAC Orchestrator"]
            MA["Maintenance Agent"]
        end

        subgraph DISK["Local Disk"]
            OV["obsidian-vault/\nPlain .md Files"]
            DM["data/mirror/\nCorporate Data"]
            DS["data/staging/\nProposals"]
        end
    end

    subgraph LAPTOP["Team Lead Laptop"]
        OB["Obsidian App\n(Network Mount)"]
    end

    CLOUD["Cloud Services\nExternal APIs"]

    WC --> LLM
    VW --> EMB
    WC --> OV
    VW --> OV
    VW --> QD
    CO --> QD
    OB -.->|"Network\nMount"| OV

    CLOUD -.-x|"NO CONNECTION\nZero Cloud Dependencies"| DGX

    style DGX fill:#e8f5e9,stroke:#2e7d32
    style HOST fill:#c8e6c9,stroke:#2e7d32
    style DOCKER fill:#e3f2fd,stroke:#1565c0
    style DISK fill:#fff8e1,stroke:#f57f17
    style LAPTOP fill:#f3e5f5,stroke:#4a148c
    style CLOUD fill:#ffcdd2,stroke:#b71c1c
```

### Design Decision: Shared Vault with Department Subdirectories

**Why one vault with subdirectories (not separate vaults per department)?**
- Obsidian graph view, global search, and `[[backlinks]]` all work **within a single vault**
- Cross-department backlinks work naturally (e.g., CAC decision referencing a shared policy)
- Department isolation is enforced at the service level (Wiki Compiler, VaultWatcher, Qdrant, Paperclip) — not at the filesystem level
- Simpler operations: one vault to mount, backup, and version-control

**Vault Directory Structure:**
```
obsidian-vault/
├── shared/                          ← Cross-department (all agents can read)
│   ├── index.md                     ← Shared knowledge catalog
│   ├── log.md                       ← Shared operations log
│   ├── skills/                      ← Symlink → skills/shared/
│   ├── policies/                    ← Shared corporate policies
│   └── escalation-protocols/        ← Cross-dept escalation articles
│
├── cac/                             ← CAC department only
│   ├── index.md                     ← CAC knowledge catalog
│   ├── log.md                       ← CAC operations log
│   ├── skills/                      ← Symlink → skills/cac/
│   ├── concepts/                    ← LCR, CAR, covenants, ALM...
│   ├── decisions/                   ← Approved proposal records
│   ├── meeting-notes/               ← Slack #cac-committee digests
│   ├── entities/                    ← Facilities, instruments, people
│   └── trends/                      ← Periodic analysis
│
├── risk/                            ← (Phase 2) Risk department
│   ├── index.md
│   ├── concepts/
│   └── ...
│
└── templates/                       ← Shared article templates (ignored by VaultWatcher)
```

**4-Layer Department Boundary Enforcement:**

| Layer | Mechanism | Config File | What It Prevents |
|---|---|---|---|
| Wiki Compiler | `dept_router.py` routes events to `obsidian-vault/{dept_id}/` only | `wiki_schema.json` | CAC event writing to risk/ vault |
| VaultWatcher | Maps `cac/*` folders → `cac_knowledge` collection | `obsidian_watch.json` | CAC articles polluting shared_policies |
| Qdrant | Department-scoped collections | `departments.json` | CAC agent retrieving risk department articles |
| Paperclip | Department boundary checks on tickets and events | `departments.json` | Cross-department data leakage via API |

**Updated obsidian_watch.json (multi-department):**
```json
{
  "vault_path": "${OBSIDIAN_VAULT_PATH}",
  "watch_folders": [
    {"path": "shared/skills/",     "collection": "shared_policies", "doc_type": "skill"},
    {"path": "shared/policies/",   "collection": "shared_policies", "doc_type": "policy_note"},
    {"path": "cac/skills/",        "collection": "cac_knowledge",   "doc_type": "skill"},
    {"path": "cac/concepts/",      "collection": "cac_knowledge",   "doc_type": "concept"},
    {"path": "cac/decisions/",     "collection": "cac_knowledge",   "doc_type": "decision_log"},
    {"path": "cac/meeting-notes/", "collection": "cac_knowledge",   "doc_type": "meeting_note"},
    {"path": "cac/entities/",      "collection": "cac_knowledge",   "doc_type": "entity"},
    {"path": "cac/trends/",        "collection": "cac_knowledge",   "doc_type": "trend"}
  ],
  "ignore_folders": [".obsidian", "templates"],
  "ignore_files": ["index.md", "log.md", "lint-report.md"],
  "debounce_seconds": 5,
  "chunk_size": 512,
  "chunk_overlap": 128
}
```

**Adding a new department (Phase 2+, config-only):**
1. Add department to `departments.json` (Qdrant collections, mirror paths, agents)
2. Create `obsidian-vault/{dept}/` directory structure
3. Add `watch_folders` entries to `obsidian_watch.json` mapping to new collections
4. Create SKILL.md files in `skills/{dept}/` and symlink into vault
5. Register department agents in Paperclip
6. **No code changes needed** — `dept_router.py` reads from `departments.json`

**Wiki Maintenance Agent:**
- Registered in Paperclip as `wiki-maintenance-agent` (department: shared)
- Runs weekly lint passes per department vault
- Detects: contradictions, stale data, orphan pages, missing concepts, broken links
- Outputs: `lint-report.md` per department, updated articles, suggested new articles
- Prunes articles older than configurable threshold (default: 12 months)
- Scores coverage: high (5+ sources) / medium (2-4) / low (0-1)
- APScheduler weekly cron, configurable per department in `wiki_schema.json`

**Confidentiality guarantee:**
Everything runs on-premise on DGX Spark (128GB). No data leaves the network. The wiki is
plain markdown files on local disk. LLM inference is local (Qwen3.5 on vLLM). Qdrant,
Postgres, and all services run in Docker on the same machine. Zero cloud dependencies.
Department data boundaries enforced at 4 layers. Obsidian connects via network mount only.

---

## 1. The Pattern (Karpathy, April 2026)

Source: [Karpathy's llm-wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

### Three-Layer Architecture

**Layer 1: Raw Sources** (`raw/`)
- Immutable source documents: articles, papers, repos, datasets, images
- Organized by type: `raw/articles/`, `raw/papers/`, `raw/repos/`, `raw/data/`, `raw/images/`
- LLM reads but NEVER writes to this layer
- Sources added by human (via Obsidian Web Clipper, manual download, etc.)

**Layer 2: Wiki** (`wiki/`)
- LLM-generated and maintained markdown structure
- Key files:
  - `wiki/index.md` — content catalog with page links, summaries, metadata by category
  - `wiki/log.md` — append-only chronological record of ingests, queries, and maintenance
  - `wiki/overview.md` — high-level synthesis of all material
- Key directories:
  - `wiki/concepts/` — topic pages (e.g., attention mechanisms, scaling laws)
  - `wiki/entities/` — organization/person pages
  - `wiki/sources/` — individual source summaries
  - `wiki/comparisons/` — comparative analyses filed from queries

**Layer 3: Schema** (CLAUDE.md / AGENTS.md)
- Configuration specifying wiki structure, conventions, workflows
- Humans and LLMs co-evolve this over time
- Contains: project structure rules, page conventions, ingest/query/lint workflows

### Page Format Convention

Every wiki page requires YAML frontmatter:
```yaml
---
title: Page Title
type: concept | entity | source-summary | comparison
sources: [list of raw/ files referenced]
related: [list of wiki pages linked]
created: YYYY-MM-DD
updated: YYYY-MM-DD
confidence: high | medium | low
---
```

### Core Operations

**Ingest** (adding new source):
1. Read source file in raw/
2. Discuss key takeaways with user
3. Create/update summary page in wiki/sources/
4. Update wiki/index.md
5. Update all relevant concept and entity pages
6. Flag contradictions where new data conflicts with existing claims
7. Add/update cross-reference links throughout wiki
8. Append entry to wiki/log.md

A single source can touch 10-15 wiki pages as knowledge propagates.

**Query** (answering questions):
1. Read wiki/index.md to find relevant pages
2. Read identified pages in full
3. Synthesize answer with `[[wiki-link]]` citations
4. Optionally file valuable results as new wiki pages (compounding loop)

**Lint** (periodic health checks):
- Contradiction detection between pages
- Stale/superseded claims identification
- Orphan pages with no inbound links
- Missing pages for frequently mentioned concepts
- Cross-reference quality (broken/incomplete links)
- Investigation suggestions for new questions

### Log.md Format

```markdown
## [YYYY-MM-DD] ingest | Source Title
Source: raw/path/to/file.md
Pages created: wiki/sources/summary-name.md
Pages updated: wiki/concepts/topic.md, wiki/entities/org.md
Notes: Key findings, contradictions flagged

## [YYYY-MM-DD] query | Question Asked
Question: What did users ask?
Pages read: list of pages consulted
Output: Filed as wiki/path/new-page.md OR chat response

## [YYYY-MM-DD] lint | Health Check
Contradictions found: N
Orphan pages: N
Missing pages suggested: N
```

### Scale Considerations

| Scale | Sources | Navigation | Notes |
|-------|---------|-----------|-------|
| Small | 10-30 | index.md alone | Sufficient for navigation |
| Medium | 50-200 | qmd search useful | Add hybrid search |
| Large | 500+ | Requires taxonomy + linting | Careful organization needed |

Karpathy's own wiki: ~100 articles, ~400K words on one research topic. LLM writes and maintains everything; human rarely touches directly.

### Key Insight

Shifts work from **query-time retrieval** (RAG) to **ingestion-time compilation**. Knowledge accumulates incrementally; cross-references and synthesis are pre-built rather than re-derived on each question.

---

## 2. QMD — Local Search Engine

Source: [github.com/tobi/qmd](https://github.com/tobi/qmd)

Created by Tobi Lutke. Local search engine for markdown files.

### Architecture
Combines three search techniques, all running locally via node-llama-cpp with GGUF models:
1. **BM25 Full-Text Search** — keyword-based ranking
2. **Vector Semantic Search** — embedding-based meaning matching
3. **LLM Re-ranking** — language model ordering of results

### Search Modes
| Mode | Command | Description |
|------|---------|-------------|
| Keyword | `qmd search` | Fast BM25 only, no model needed |
| Semantic | `qmd vsearch` | Vector similarity, conceptual matching |
| Hybrid | `qmd query` | Both + LLM re-ranking, highest quality |

### Integration Options
- CLI for direct querying
- **MCP server** for AI agent integration (relevant for our project)
- JavaScript/TypeScript SDK
- HTTP transport for long-lived server instances

### Installation
```bash
npm install -g @tobilu/qmd
```

### Relevance to Our Project
- Could replace or supplement Qdrant for wiki-specific search
- MCP server mode means agents could use it as a tool
- Runs entirely local — fits our DGX Spark single-machine architecture
- However, we already have Qdrant with vector search — may be redundant

---

## 3. LLM Wiki Compiler — Existing Implementation

Source: [github.com/ussumant/llm-wiki-compiler](https://github.com/ussumant/llm-wiki-compiler)

A Claude Code plugin implementing the Karpathy pattern.

### Article Structure
Each topic article has standardized sections:
- Summary (2-3 paragraphs)
- Timeline with dated events
- Current state snapshot
- Key decisions with rationale and source links
- Experiments & results status table
- Gotchas and known issues
- Open questions
- Source backlinks to raw files

### Coverage Indicators
Sections tagged `[coverage: high/medium/low]`:
- **High (5+ sources)**: Trust wiki section directly
- **Medium (2-4 sources)**: Good overview, verify details in raw files
- **Low (0-1 sources)**: Consult original sources

### Concept Articles
Auto-detects patterns spanning 3+ topics and generates interpretive articles.

### Commands
| Command | Purpose |
|---------|---------|
| `/wiki-init` | Auto-detect directories, create config |
| `/wiki-compile` | Incremental topic compilation |
| `/wiki-lint` | Health checks (staleness, orphans, gaps) |
| `/wiki-query` | Q&A with optional answer filing |

### Adoption Modes
1. **Staging**: Wiki as reference only
2. **Recommended**: Prioritize wiki before raw files
3. **Primary**: Wiki is authoritative source

### Verified Performance
Testing on 383 markdown files (13.1 MB):
- Context reduction: 84% (47K to 7.7K tokens at startup)
- Compression: 81x files, 503x for meeting transcripts
- Break-even: First session

### Relevance to Our Project
- Validates the pattern works at scale
- The staging/recommended/primary adoption modes map well to our phased approach
- Coverage indicators would work well for committee knowledge (high-confidence vs. preliminary data)

---

## 4. CodeWiki — Codebase Variant

Source: [muhammadraza.me/2026/building-codewiki](https://muhammadraza.me/2026/building-codewiki-compiling-codebases-into-living-wikis/)

Applies the wiki pattern to codebases rather than research.

### Architecture
- Lives at `~/.codewiki/<project>/`
- Master index + architecture overview
- Module articles (one per code module)
- Concept articles (cross-cutting concerns)
- Decisions and learnings directories

### Freshness Tracking
- Tracks which git commit the wiki was compiled against
- Changed files trigger targeted updates (not full rewrites)
- Articles include `source_files` metadata

### Relevance
- The freshness tracking pattern is relevant for our wiki — we could track which Slack messages / proposals have been compiled
- Targeted updates vs. full rewrites is important for efficiency

---

## 5. Enterprise / Corporate Considerations

Source: [modemguides.com/local-llm-knowledge-base-obsidian-setup-guide](https://www.modemguides.com/blogs/ai-infrastructure/local-llm-knowledge-base-obsidian-setup-guide)

### Contamination Mitigation
Community pattern: separate "clean vault" from "messy vault" used by agents. Promotion into core vault is a controlled step — mirrors production data staging.

**Directly maps to our data zones:**
- Zone 1 (mirror) = raw/ layer (immutable corporate data)
- Zone 2 (staging) = wiki compilation staging
- Zone 3 (approval) = human review of wiki articles before promotion
- Zone 4 (archive) = finalized wiki content

### Data Sovereignty
All files remain as plain markdown on disk. No proprietary database, no vendor lock-in. Fits our on-premise DGX Spark architecture perfectly.

### Hardware Requirements
| Level | RAM | Model Size | Wiki Scale |
|-------|-----|-----------|-----------|
| Entry | 16GB | 7-8B | <50 sources |
| Mid | 32GB | 14-32B | Medium wikis |
| Power | 24GB VRAM | 70B+ | 100+ sources |

We have 128GB unified memory on DGX Spark + Qwen3.5 122B — well beyond "Power" tier.

---

## 6. Obsidian Plugin Ecosystem (Relevant)

### Dataview Plugin
- Query frontmatter metadata across all pages
- Create dynamic tables, lists, task views
- Example: "Show all decisions with confidence: low from last 30 days"
- Essential for the health-check / lint workflow

### Obsidian Web Clipper
- Browser extension converting web articles to markdown
- Adds YAML frontmatter automatically
- Downloads images locally
- Relevant for ingesting external documents

### obsidian-qmd Plugin
Source: [github.com/thirteen37/obsidian-qmd](https://github.com/thirteen37/obsidian-qmd)
- Integrates QMD hybrid search directly into Obsidian
- BM25 + vector + LLM re-ranking inside the editor

### Marp Plugin
- Renders markdown as slide presentations
- Useful for generating committee briefing slides from wiki content

---

## 7. Mapping to Brooker Corporate Agent

### What We Already Have (from current project)

| Karpathy Component | Our Equivalent | Status |
|---|---|---|
| Raw/ layer | `/data/mirror/` + Slack messages + uploaded docs | Built (Zone 1) |
| Wiki/ layer | `obsidian-vault/` | Shell only (templates, no content) |
| Schema layer | `CLAUDE.md` + `obsidian_watch.json` | Partial |
| Ingest workflow | VaultWatcher + Qdrant pipeline | Built (watches vault, embeds to cac_knowledge) |
| Query workflow | RAG retrieval in cac-orchestrator | Built (agents query Qdrant) |
| Lint workflow | None | Not built |
| index.md | Exists but static | Needs auto-maintenance |
| log.md | Not present | Needed |
| Search engine | Qdrant vector search | Built (could add qmd for BM25 hybrid) |
| Viewer | Obsidian planned, not installed | Stage 8 blocker |

### What's Missing (the gap)

1. **Wiki Compiler Service** — the component that turns events into wiki articles
2. **Structured frontmatter** on all vault files
3. **log.md** for tracking wiki operations
4. **Auto-maintained index.md**
5. **Concept / entity / decision articles** auto-generated from data
6. **Lint workflow** for health checks
7. **Obsidian plugins** (Dataview, possibly qmd)

### Natural Integration Points

| Event | Wiki Action |
|---|---|
| Staging proposal approved | Auto-generate decision article with rationale, source, cell change |
| Slack thread discussing CAC topic | Daily digest compiled into meeting-note article |
| New document uploaded | Source summary article + concept/entity updates |
| Escalation triggered | Escalation article with context and resolution tracking |
| Agent interaction with high confidence | File response as knowledge article if novel |
| Periodic (weekly) | Lint pass: contradictions, stale data, missing concepts |

### The Compounding Effect

Month 1: Wiki has ~20 articles (skill docs + initial decisions)
Month 3: Wiki has ~100 articles (decisions, meeting notes, trends)
Month 6: Wiki has ~300 articles (full institutional memory)
Month 12: Wiki has ~500+ articles (committee fully documented)

Each article makes every future agent query more informed. The liquidity agent in Month 12 knows 12 months of committee context, not just static SKILL.md content.

---

## 8. Benefit Analysis: Current RAG vs. Wiki + RAG

### Current RAG (What We Have)

**How it works**: User asks question → search Qdrant for relevant chunks → retrieve raw text fragments → LLM synthesizes answer from scratch → answer returned → knowledge forgotten.

**Pros**:
- Already built and working (VaultWatcher, Qdrant, RAG pipeline)
- Simple architecture — fewer moving parts
- No LLM cost at ingestion time (embedding is cheap)
- No risk of LLM hallucination in stored knowledge
- Raw source text preserved exactly as-is

**Cons**:
- Re-derives understanding from scratch on every query (wasteful)
- No cross-document connections — only finds chunks that happen to be retrieved together
- No contradiction detection — conflicting data can both be retrieved and confuse the LLM
- Knowledge doesn't compound — agent is equally uninformed on Day 1 and Day 365
- Qdrant is a black box — nobody browses vector embeddings
- Context window wasted re-reading raw chunks instead of pre-built summaries
- No institutional memory — decisions and rationale live only in Postgres logs

### Proposed Wiki + RAG (What We'd Add)

**How it works**: New data arrives → LLM compiles it into structured wiki articles with backlinks → VaultWatcher auto-embeds to Qdrant → User asks question → LLM reads pre-built articles → better answer with full context → valuable answers filed back into wiki.

**Pros**:
- Knowledge compounds over time (20 articles Month 1 → 500+ Month 12)
- Pre-built cross-references between concepts, decisions, and meetings
- Contradictions flagged at ingestion time, not missed at query time
- Human-browsable in Obsidian (HODs, committee members, auditors can all read it)
- Context window efficiency — compact articles vs. raw chunks (verified 84% reduction)
- Self-documenting audit trail in plain English
- Lint/health checks catch stale or inconsistent knowledge proactively
- Agents get smarter automatically as committee history accumulates

**Cons**:
- New service to build and maintain (Wiki Compiler)
- LLM cost at ingestion time (each event → LLM call to compile article)
- Risk of LLM hallucination in wiki articles (mitigated by source citations + confidence levels)
- Vault mount needs write access (currently :ro — needs architectural change)
- Circular dependency risk: wiki feeds Qdrant feeds agents feeds wiki (need loop-breaking rules)
- Not a replacement for RAG — it's an enhancement layer on top

### Comparison Table

```mermaid
quadrantChart
    title RAG vs Wiki+RAG Trade-offs
    x-axis Low Effort --> High Effort
    y-axis Low Value --> High Value
    quadrant-1 "Worth Building"
    quadrant-2 "Quick Wins"
    quadrant-3 "Avoid"
    quadrant-4 "Consider Later"
    "Current RAG": [0.2, 0.5]
    "Wiki Compiler": [0.6, 0.85]
    "Lint Workflow": [0.4, 0.7]
    "QMD Search": [0.3, 0.3]
    "Slide Generation": [0.5, 0.4]
    "Trend Analysis": [0.7, 0.75]
```

| Dimension | RAG Only | Wiki + RAG |
|---|---|---|
| Setup cost | Already done | New service needed |
| Day 1 quality | Good | Same (wiki is empty) |
| Day 365 quality | Same as Day 1 | Much better (compounded) |
| Human visibility | None (black box) | Full (Obsidian browsable) |
| Cross-document links | Ad-hoc | Pre-built |
| Contradiction handling | Missed | Detected and flagged |
| Audit/compliance | Postgres logs | Readable wiki + logs |
| Context efficiency | Raw chunks (~47K tokens) | Compiled articles (~7.7K) |
| Operational complexity | Low | Medium |
| Agent improvement | Static | Continuous |

### Key Insight

The wiki doesn't replace RAG — it makes RAG better by feeding higher-quality, pre-synthesized content into the same Qdrant pipeline. The VaultWatcher and cac_knowledge collection remain unchanged. The wiki compiler is a new data source that produces better input.

---

## 9. Summary of Sources

- [Karpathy's llm-wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — original pattern definition
- [VentureBeat: Karpathy LLM Knowledge Base](https://venturebeat.com/data/karpathy-shares-llm-knowledge-base-architecture-that-bypasses-rag-with-an) — analysis and context
- [AntiGravity: Karpathy's LLM Wiki Guide](https://antigravity.codes/blog/karpathy-llm-wiki-idea-file) — complete implementation details
- [AntiGravity: LLM Knowledge Bases](https://antigravity.codes/blog/karpathy-llm-knowledge-bases) — workflow analysis
- [GitHub: tobi/qmd](https://github.com/tobi/qmd) — local hybrid search engine
- [GitHub: ussumant/llm-wiki-compiler](https://github.com/ussumant/llm-wiki-compiler) — Claude Code plugin implementation
- [CodeWiki: Compiling Codebases](https://muhammadraza.me/2026/building-codewiki-compiling-codebases-into-living-wikis/) — codebase variant
- [ModemGuides: Local LLM KB with Obsidian](https://www.modemguides.com/blogs/ai-infrastructure/local-llm-knowledge-base-obsidian-setup-guide) — setup guide
- [MindStudio: Karpathy LLM Wiki Guide](https://www.mindstudio.ai/blog/andrej-karpathy-llm-wiki-knowledge-base-claude-code) — Claude Code implementation
- [DAIR.AI: LLM Knowledge Bases](https://academy.dair.ai/blog/llm-knowledge-bases-karpathy) — academic analysis
- [GitHub: obsidian-qmd](https://github.com/thirteen37/obsidian-qmd) — Obsidian QMD plugin
- [a2a-mcp.org: Obsidian Wiki Guide](https://a2a-mcp.org/blog/andrej-karpathy-llm-knowledge-bases-obsidian-wiki) — implementation guide
