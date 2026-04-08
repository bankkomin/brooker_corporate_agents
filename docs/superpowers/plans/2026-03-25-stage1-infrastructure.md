# Stage 1: Infrastructure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the complete repository structure, Docker infrastructure (postgres, qdrant, minio, nginx LB, gateway), database schema (7 tables), vLLM launch scripts, and all configuration skeletons so that `docker compose up` produces a running infrastructure ready for service development in Stage 2+.

**Architecture:** Microservices on Docker Compose with nginx reverse-proxy load-balancing dual DGX Spark vLLM endpoints. PostgreSQL for state, Qdrant for vectors, MinIO for documents. Three data zones (mirror/staging/archive) with Docker-enforced read-only access on mirror. All services communicate over `agent-net` bridge network.

**Tech Stack:** Docker Compose 3.9, PostgreSQL 16, Qdrant 1.12, MinIO, nginx 1.25, Python 3.11+, FastAPI, Pydantic v2, pytest, ruff

**Spec:** `docs/superpowers/specs/2026-03-25-architecture-design.md`
**PRD:** `PRD.md` v2.2

---

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

## File Map

### New Files (Stage 1 creates all of these)

```
Root:
  .gitignore                          ← Python/Docker/env ignore rules
  .env.example                        ← All env vars with safe defaults
  README.md                           ← Project overview, quickstart, architecture
  AGENTS.md                           ← Claude Code session context paste

Infrastructure:
  infra/vllm/start-122b.sh            ← vLLM launch for Qwen 122B reasoning
  infra/vllm/start-embed.sh           ← vLLM launch for Qwen 9B embeddings
  infra/nginx/nginx.conf              ← Dual-Spark LB config (port 8080)

Docker:
  docker-compose.yml                  ← Full production compose (13 services)
  docker-compose.dev.yml              ← Local dev overrides (no vLLM required)

Database:
  migrations/001_initial_schema.sql   ← 7 Postgres tables with indexes

Config Skeletons:
  config/excel_schema/alco_tracker.json   ← Excel structure mapping
  config/dept_channels.json               ← Slack channel mapping
  config/hod_emails.json                  ← HOD email addresses
  config/escalation_rules.json            ← Breach trigger rules
  config/obsidian_watch.json              ← Vault watcher config

Service Stubs (gateway only — other services in later stages):
  services/gateway/Dockerfile             ← Python 3.11 slim image
  services/gateway/requirements.txt       ← FastAPI, uvicorn, pydantic
  services/gateway/src/__init__.py
  services/gateway/src/main.py            ← FastAPI app with /health

Directory Skeletons (empty __init__.py or .gitkeep):
  services/slack-bot/src/.gitkeep
  services/rag-ingestion/src/.gitkeep
  services/cac-orchestrator/src/.gitkeep
  services/cac-orchestrator/src/agents/.gitkeep
  services/cac-orchestrator/src/tools/.gitkeep
  services/cac-orchestrator/src/skills/.gitkeep
  services/sync-mirror/src/.gitkeep
  services/sync-mirror/src/connectors/.gitkeep
  services/sync-back/src/.gitkeep
  services/approval-ui/src/.gitkeep
  services/approval-ui/src/static/.gitkeep
  services/email-notifier/src/.gitkeep
  services/email-notifier/src/templates/.gitkeep
  skills/shared/.gitkeep
  skills/cac/.gitkeep
  obsidian-vault/meeting-notes/templates/.gitkeep
  obsidian-vault/decisions/templates/.gitkeep
  obsidian-vault/policies/.gitkeep
  tests/unit/.gitkeep
  tests/integration/.gitkeep
  tests/fixtures/.gitkeep

Scripts:
  scripts/setup-data-dirs.sh              ← Creates /data zone directories
  scripts/healthcheck.sh                  ← Verifies all services healthy

Tests:
  tests/integration/test_infrastructure.py ← Docker health checks + DB schema
```

---

## Task 1: Repository Scaffold — Directory Structure

**Files:**
- Create: All `.gitkeep` files listed above
- Create: `.gitignore`

- [ ] **Step 1: Create all service directory skeletons**

```bash
# Service directories
mkdir -p services/gateway/src
mkdir -p services/slack-bot/src
mkdir -p services/rag-ingestion/src
mkdir -p services/cac-orchestrator/src/agents
mkdir -p services/cac-orchestrator/src/tools
mkdir -p services/cac-orchestrator/src/skills
mkdir -p services/sync-mirror/src/connectors
mkdir -p services/sync-back/src
mkdir -p services/approval-ui/src/static
mkdir -p services/email-notifier/src/templates

# Skills directories
mkdir -p skills/shared
mkdir -p skills/cac

# Obsidian vault
mkdir -p obsidian-vault/meeting-notes/templates
mkdir -p obsidian-vault/decisions/templates
mkdir -p obsidian-vault/policies

# Config
mkdir -p config/excel_schema

# Infrastructure
mkdir -p infra/vllm
mkdir -p infra/nginx

# Database
mkdir -p migrations

# Tests
mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p tests/fixtures

# Scripts
mkdir -p scripts
```

- [ ] **Step 2: Add .gitkeep files to empty directories**

```bash
# Add .gitkeep to all skeleton directories that won't have files yet
for dir in \
  services/slack-bot/src \
  services/rag-ingestion/src \
  services/cac-orchestrator/src \
  services/cac-orchestrator/src/agents \
  services/cac-orchestrator/src/tools \
  services/cac-orchestrator/src/skills \
  services/sync-mirror/src \
  services/sync-mirror/src/connectors \
  services/sync-back/src \
  services/approval-ui/src \
  services/approval-ui/src/static \
  services/email-notifier/src \
  services/email-notifier/src/templates \
  skills/shared \
  skills/cac \
  obsidian-vault/meeting-notes/templates \
  obsidian-vault/decisions/templates \
  obsidian-vault/policies \
  tests/unit \
  tests/integration \
  tests/fixtures; do
  touch "$dir/.gitkeep"
done
```

- [ ] **Step 3: Create .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
*.manifest
*.spec
pip-log.txt
pip-delete-this-directory.txt

# Virtual environments
.venv/
venv/
ENV/

# Testing
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Environment
.env
.env.local
.env.production

# Docker
docker-compose.override.yml

# Data zones (never commit data)
/data/
mirror_data/
staging_data/
archive_data/

# MinIO data
minio_data/

# Postgres data
postgres_data/

# Qdrant data
qdrant_data/

# Node modules (Paperclip)
node_modules/

# OS
.DS_Store
Thumbs.db
desktop.ini

# Obsidian internals
obsidian-vault/.obsidian/

# Logs
*.log
logs/

# Claude Code
.claude/worktrees/
```

- [ ] **Step 4: Commit scaffold**

```bash
git add .gitignore services/ skills/ obsidian-vault/ config/ infra/ migrations/ tests/ scripts/
git commit -m "chore: scaffold repository directory structure

Create all service, config, skills, tests, and infrastructure
directories per PRD Section 4 repository layout."
```

---

## Task 2: Environment Configuration

**Files:**
- Create: `.env.example`

- [ ] **Step 1: Create .env.example with all environment variables**

```bash
# =============================================================================
# Corporate AI Agent System — Environment Configuration
# =============================================================================
# Copy to .env and fill in real values: cp .env.example .env
# NEVER commit .env to git
# =============================================================================

# --- Slack ---
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
CAC_CHANNEL_ID=C0123456789
APPROVALS_CHANNEL_ID=C1111111111
ESCALATIONS_CHANNEL_ID=C9876543210

# --- vLLM (on DGX Spark host) ---
VLLM_LARGE_URL=http://nginx:8080/v1
VLLM_EMBED_URL=http://host.docker.internal:8002/v1
VLLM_LARGE_MODEL=qwen-large
VLLM_EMBED_MODEL=qwen-embed

# --- Qdrant ---
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# --- PostgreSQL ---
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=corporate_agents
POSTGRES_USER=agents
POSTGRES_PASSWORD=changeme

# --- MinIO ---
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=changeme
MINIO_BUCKET=raw-documents

# --- Paperclip ---
PAPERCLIP_URL=http://paperclip:3100
PAPERCLIP_API_KEY=your-paperclip-key

# --- Mirror Sync ---
MIRROR_SOURCE=smb
MIRROR_SYNC_INTERVAL_MINUTES=15

# SharePoint (if MIRROR_SOURCE=sharepoint)
SHAREPOINT_TENANT_ID=
SHAREPOINT_CLIENT_ID=
SHAREPOINT_CLIENT_SECRET=
SHAREPOINT_SITE_URL=https://yourcompany.sharepoint.com/sites/cac

# SMB (if MIRROR_SOURCE=smb)
SMB_HOST=192.168.1.50
SMB_SHARE=FinanceData
SMB_USERNAME=svc_mirror
SMB_PASSWORD=

# --- Obsidian Vault ---
OBSIDIAN_VAULT_PATH=/mnt/obsidian-vault
OBSIDIAN_WATCH_ENABLED=true
OBSIDIAN_QDRANT_COLLECTION=cac_knowledge
OBSIDIAN_INGEST_DELAY_SECONDS=5

# --- Email Notifier ---
EMAIL_PROVIDER=smtp
APPROVAL_UI_HOST=http://192.168.1.10:4000

# SMTP
SMTP_HOST=mail.company.com
SMTP_PORT=587
SMTP_USER=noreply@company.com
SMTP_PASSWORD=
SMTP_USE_TLS=true
EMAIL_FROM=CAC AI Agent <noreply@company.com>

# SendGrid (alternative)
SENDGRID_API_KEY=

# Microsoft Graph Mail API (alternative — reuses SharePoint app registration)
MSGRAPH_SENDER_EMAIL=noreply@company.com

# SFTP (if MIRROR_SOURCE=sftp)
SFTP_HOST=
SFTP_PORT=22
SFTP_USERNAME=
SFTP_PASSWORD=
SFTP_PATH=/

# HOD Emails
CEO_EMAIL=ceo@company.com
CAC_HOD_EMAIL=cfo@company.com

# Email Feature Flags
SEND_PROPOSAL_EMAIL=true
SEND_ESCALATION_EMAIL=true
SEND_REMINDER_EMAIL=true
SEND_CONFIRMATION_EMAIL=false
REMINDER_AFTER_HOURS=24

# --- Data Zones ---
STAGING_PATH=/data/staging
MIRROR_PATH=/data/mirror
ARCHIVE_PATH=/data/archive

# --- Agent Config ---
PROPOSAL_CONFIDENCE_THRESHOLD=0.85
RAG_TOP_K=8
RAG_MIN_RELEVANCE=0.70
CHUNK_SIZE=512
CHUNK_OVERLAP=128
MAX_QUERY_TOKENS=32768
RESPONSE_TIMEOUT_SECONDS=30
SKILLS_DIR=/app/skills

# --- General ---
ENV=development
LOG_LEVEL=INFO
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "chore: add .env.example with all environment variables

Complete environment configuration template covering Slack, vLLM,
Postgres, Qdrant, MinIO, email, mirror sync, and agent settings."
```

---

## Task 3: vLLM Launch Scripts

**Files:**
- Create: `infra/vllm/start-122b.sh`
- Create: `infra/vllm/start-embed.sh`

- [ ] **Step 1: Create start-122b.sh**

```bash
#!/bin/bash
# Start vLLM for Qwen3.5 122B reasoning model
# Run on DGX Spark host (not in Docker)
# Usage: bash infra/vllm/start-122b.sh
#
# NOTE: --quantization fp8 uses vLLM's native FP8 quantization.
# If using a GGUF Q8_0 model file instead, remove --quantization
# and point MODEL to the GGUF path. Adjust as needed for your setup.

set -euo pipefail

MODEL="Qwen/Qwen3.5-122B-A10B"
PORT=8000

echo "Starting vLLM for ${MODEL} on port ${PORT}..."

vllm serve "${MODEL}" \
  --port "${PORT}" \
  --quantization fp8 \
  --tensor-parallel-size 1 \
  --max-model-len 131072 \
  --reasoning-parser qwen3 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --served-model-name qwen-large \
  --gpu-memory-utilization 0.88
```

- [ ] **Step 2: Create start-embed.sh**

```bash
#!/bin/bash
# Start vLLM for Qwen3.5 9B embedding model
# Run on DGX Spark A host only (not in Docker)
# Usage: bash infra/vllm/start-embed.sh

set -euo pipefail

MODEL="Qwen/Qwen3.5-9B"
PORT=8002

echo "Starting vLLM embedding for ${MODEL} on port ${PORT}..."

vllm serve "${MODEL}" \
  --port "${PORT}" \
  --task embed \
  --max-model-len 8192 \
  --served-model-name qwen-embed \
  --gpu-memory-utilization 0.08
```

- [ ] **Step 3: Make scripts executable and commit**

```bash
chmod +x infra/vllm/start-122b.sh infra/vllm/start-embed.sh
git add infra/vllm/
git commit -m "feat(infra): add vLLM launch scripts for Qwen 122B and 9B embed

- start-122b.sh: Qwen3.5 122B-A10B with fp8, 131K context, tool calling
- start-embed.sh: Qwen3.5 9B embedding model on port 8002"
```

---

## Task 4: nginx Load Balancer Configuration

**Files:**
- Create: `infra/nginx/nginx.conf`

- [ ] **Step 1: Create nginx.conf**

```nginx
user  nginx;
worker_processes  auto;

error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent"';

    access_log /var/log/nginx/access.log main;

    sendfile        on;
    tcp_nopush      on;
    tcp_nodelay     on;
    keepalive_timeout 120;
    client_max_body_size 100M;

    # ---- vLLM upstream (dual-Spark load balancing) ----
    # Phase 1: single Spark A
    # When Spark B is ready: uncomment the second server line
    upstream vllm_backend {
        least_conn;
        server host.docker.internal:8000 max_fails=3 fail_timeout=30s;
        # server <SPARK_B_IP>:8000 max_fails=3 fail_timeout=30s;
    }

    server {
        listen 8080;
        server_name _;

        # Health check endpoint
        location = /health {
            return 200 '{"status":"healthy","service":"nginx-lb"}';
            add_header Content-Type application/json;
        }

        # Proxy all /v1/* requests to vLLM backend
        location /v1/ {
            proxy_pass http://vllm_backend/v1/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Long timeouts for LLM inference
            proxy_read_timeout 300s;
            proxy_connect_timeout 10s;
            proxy_send_timeout 60s;

            # Streaming support for vLLM completions
            proxy_buffering off;
            proxy_request_buffering off;
            chunked_transfer_encoding on;
        }
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add infra/nginx/
git commit -m "feat(infra): add nginx load balancer config for dual-Spark vLLM

- Listens on port 8080 (avoids conflict with vLLM host port 8000)
- least_conn algorithm for even distribution
- Health check at /health
- Streaming support for LLM completions
- Second Spark B server ready to uncomment"
```

---

## Task 5: PostgreSQL Schema Migration

**Files:**
- Create: `migrations/001_initial_schema.sql`

- [ ] **Step 1: Write the migration with all 7 tables**

```sql
-- migrations/001_initial_schema.sql
-- Corporate AI Agent System — Initial Schema
-- 7 tables: agent_interactions, staging_proposals, approval_decisions,
--           sync_log, ingested_documents, escalations, email_log

BEGIN;

-- 1. Agent Interactions (query log)
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
CREATE INDEX idx_agent_interactions_created_at ON agent_interactions(created_at DESC);
CREATE INDEX idx_agent_interactions_user_id ON agent_interactions(user_id);

-- 2. Staging Proposals (agent change proposals)
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
CREATE INDEX idx_staging_proposals_status ON staging_proposals(status);
CREATE INDEX idx_staging_proposals_created_at ON staging_proposals(created_at DESC);

-- 3. Approval Decisions (HOD decisions)
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
CREATE INDEX idx_approval_decisions_proposal_id ON approval_decisions(proposal_id);
CREATE INDEX idx_approval_decisions_decided_at ON approval_decisions(decided_at DESC);

-- 4. Sync Log (mirror and sync-back operations)
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
CREATE INDEX idx_sync_log_synced_at ON sync_log(synced_at DESC);
CREATE INDEX idx_sync_log_direction ON sync_log(direction);

-- 5. Ingested Documents (document registry for dedup)
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
CREATE INDEX idx_ingested_documents_file_hash ON ingested_documents(file_hash);
CREATE INDEX idx_ingested_documents_created_at ON ingested_documents(created_at DESC);

-- 6. Escalations (breach alerts)
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
CREATE INDEX idx_escalations_created_at ON escalations(created_at DESC);
CREATE INDEX idx_escalations_severity ON escalations(severity);

-- 7. Email Log (delivery tracking)
CREATE TABLE email_log (
    id              BIGSERIAL PRIMARY KEY,
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recipient       VARCHAR(200) NOT NULL,
    event_type      VARCHAR(50) NOT NULL,
    proposal_id     VARCHAR(50),
    dept            VARCHAR(50),
    subject         TEXT,
    delivery_status VARCHAR(20),
    error           TEXT,
    retry_count     INT DEFAULT 0
);
CREATE INDEX idx_email_log_sent_at ON email_log(sent_at DESC);
CREATE INDEX idx_email_log_recipient ON email_log(recipient);
CREATE INDEX idx_email_log_delivery_status ON email_log(delivery_status);

COMMIT;
```

- [ ] **Step 2: Commit**

```bash
git add migrations/
git commit -m "feat(db): add initial schema migration with 7 tables

Tables: agent_interactions, staging_proposals, approval_decisions,
sync_log, ingested_documents, escalations, email_log.
All with proper indexes and foreign key constraints."
```

---

## Task 6: Config Skeleton Files

**Files:**
- Create: `config/excel_schema/alco_tracker.json`
- Create: `config/dept_channels.json`
- Create: `config/hod_emails.json`
- Create: `config/escalation_rules.json`
- Create: `config/obsidian_watch.json`

- [ ] **Step 1: Create alco_tracker.json**

```json
{
  "filename": "ALCO_Tracker.xlsx",
  "tabs": [
    {
      "name": "Funding Facilities",
      "header_row": 7,
      "rows": [
        {
          "row": 8,
          "label": "SCB Facility",
          "columns": {
            "B": "Facility Name",
            "C": "Limit",
            "D": "Drawn Amount",
            "E": "Covenant Threshold"
          }
        }
      ]
    }
  ],
  "_comment": "Populate with real Excel structure during Stage 8 UAT"
}
```

- [ ] **Step 2: Create dept_channels.json**

```json
{
  "cac": {
    "name": "Capital & ALCO Committee",
    "slack_channel": "${CAC_CHANNEL_ID}",
    "approvals_channel": "${APPROVALS_CHANNEL_ID}",
    "escalations_channel": "${ESCALATIONS_CHANNEL_ID}"
  },
  "_comment": "Add more departments in Phase 2"
}
```

- [ ] **Step 3: Create hod_emails.json**

```json
{
  "cac": {
    "hod": "${CAC_HOD_EMAIL}",
    "dept_name": "Capital & ALCO Committee"
  },
  "ceo": {
    "hod": "${CEO_EMAIL}",
    "dept_name": "Executive"
  },
  "_comment": "Populate with real emails during Stage 8 UAT"
}
```

- [ ] **Step 4: Create escalation_rules.json**

```json
{
  "triggers": [
    {
      "type": "covenant_ratio",
      "description": "Debt covenant ratio exceeded",
      "threshold": 3.5,
      "condition": ">",
      "severity": "high",
      "notify": ["hod", "ceo"]
    },
    {
      "type": "liquidity_ratio",
      "description": "Liquidity ratio below minimum",
      "threshold": 0.5,
      "condition": "<",
      "severity": "critical",
      "notify": ["hod", "ceo"]
    }
  ],
  "_comment": "Add more rules during Stage 5 agent implementation"
}
```

- [ ] **Step 5: Create obsidian_watch.json**

```json
{
  "vault_path": "${OBSIDIAN_VAULT_PATH}",
  "watch_folders": [
    {"path": "skills/", "collection": "cac_knowledge", "doc_type": "skill"},
    {"path": "meeting-notes/", "collection": "cac_knowledge", "doc_type": "meeting_note"},
    {"path": "decisions/", "collection": "cac_knowledge", "doc_type": "decision_log"},
    {"path": "policies/", "collection": "cac_knowledge", "doc_type": "policy_note"}
  ],
  "ignore_folders": [".obsidian", "templates"],
  "ignore_files": ["index.md"],
  "debounce_seconds": 5,
  "chunk_size": 512,
  "chunk_overlap": 128
}
```

- [ ] **Step 6: Commit**

```bash
git add config/
git commit -m "chore: add config skeleton files

- alco_tracker.json: Excel structure mapping (populate in UAT)
- dept_channels.json: Slack channel mapping
- hod_emails.json: HOD email addresses
- escalation_rules.json: Breach trigger rules
- obsidian_watch.json: Vault watcher configuration"
```

---

## Task 7: Gateway Service (First Docker Service)

**Files:**
- Create: `services/gateway/Dockerfile`
- Create: `services/gateway/requirements.txt`
- Create: `services/gateway/src/__init__.py`
- Create: `services/gateway/src/main.py`
- Test: `tests/unit/test_gateway.py`

- [ ] **Step 1: Write the failing test for gateway health endpoint**

```python
# tests/unit/test_gateway.py
"""Unit tests for the gateway service health endpoint."""
import pytest
from fastapi.testclient import TestClient


def test_health_endpoint_returns_200():
    """GET /health returns 200 with service name."""
    from services.gateway.src.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "gateway"


def test_root_returns_service_info():
    """GET / returns basic service information."""
    from services.gateway.src.main import app

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "corporate-ai-agents" in data["name"].lower() or "gateway" in data["name"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:\Users\Karin\GoogleDrive\KKbot\Brooker_Corporate_Agent
python -m pytest tests/unit/test_gateway.py -v
```

Expected: FAIL — module not found

- [ ] **Step 3: Create requirements.txt**

```
fastapi>=0.111.0
uvicorn>=0.30.0
pydantic>=2.0.0
python-dotenv>=1.0.0
httpx>=0.27.0
```

- [ ] **Step 4: Create __init__.py**

```python
# services/gateway/src/__init__.py
```

- [ ] **Step 5: Create main.py**

```python
"""Gateway service — API entrypoint for the Corporate AI Agent system."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(
    title="Corporate AI Agents Gateway",
    version="0.1.0",
    docs_url="/docs",
)


@app.get("/")
async def root() -> dict:
    """Service information."""
    return {
        "name": "Corporate AI Agents Gateway",
        "version": "0.1.0",
        "environment": os.getenv("ENV", "development"),
    }


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "gateway",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
```

- [ ] **Step 6: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 3000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3000"]
```

- [ ] **Step 7: Install test dependencies and run tests**

```bash
pip install fastapi uvicorn pydantic httpx pytest
python -m pytest tests/unit/test_gateway.py -v
```

Expected: 2 passed

- [ ] **Step 8: Commit**

```bash
git add services/gateway/ tests/unit/test_gateway.py
git commit -m "feat(gateway): add gateway service with health endpoint

- FastAPI app on port 3000
- GET /health returns status + timestamp
- GET / returns service info
- Dockerfile with Python 3.11-slim
- Unit tests passing"
```

---

## Task 8: Docker Compose — Production

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Write docker-compose.yml**

```yaml
version: "3.9"

networks:
  agent-net:
    driver: bridge

volumes:
  mirror_data:
    driver: local
  staging_data:
    driver: local
  archive_data:
    driver: local
  qdrant_data:
  postgres_data:
  minio_data:

services:
  # ---- Infrastructure Services ----

  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d
    networks: [agent-net]
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-corporate_agents}
      POSTGRES_USER: ${POSTGRES_USER:-agents}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agents -d corporate_agents"]
      interval: 5s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:v1.12.1
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    networks: [agent-net]
    environment:
      QDRANT__TELEMETRY_DISABLED: "true"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    networks: [agent-net]
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY:-changeme}
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 5s
      retries: 5

  nginx:
    image: nginx:1.25-alpine
    ports: ["8080:8080"]
    volumes:
      - ./infra/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    networks: [agent-net]
    extra_hosts: ["host.docker.internal:host-gateway"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ---- Application Services ----

  gateway:
    build: ./services/gateway
    ports: ["3000:3000"]
    networks: [agent-net]
    environment:
      ENV: ${ENV:-development}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  # Services below are stubs — built in later stages
  # Uncomment as each service is implemented

  # cac-orchestrator:
  #   build: ./services/cac-orchestrator
  #   ports: ["3001:3001"]
  #   volumes:
  #     - mirror_data:/data/mirror:ro
  #     - staging_data:/data/staging:rw
  #   extra_hosts: ["host.docker.internal:host-gateway"]
  #   networks: [agent-net]
  #   environment:
  #     VLLM_LARGE_URL: http://nginx:8080/v1
  #     VLLM_EMBED_URL: http://host.docker.internal:8002/v1
  #     POSTGRES_HOST: postgres
  #     QDRANT_HOST: qdrant
  #     QDRANT_PORT: 6333
  #   depends_on:
  #     postgres: { condition: service_healthy }
  #     qdrant: { condition: service_healthy }
  #     nginx: { condition: service_healthy }

  # slack-bot:
  #   build: ./services/slack-bot
  #   ports: ["3003:3003"]
  #   networks: [agent-net]
  #   environment:
  #     SLACK_BOT_TOKEN: ${SLACK_BOT_TOKEN}
  #     SLACK_SIGNING_SECRET: ${SLACK_SIGNING_SECRET}
  #     VLLM_LARGE_URL: http://nginx:8080/v1

  # rag-ingestion:
  #   build: ./services/rag-ingestion
  #   ports: ["3004:3004"]
  #   volumes:
  #     - mirror_data:/data/mirror:ro
  #   networks: [agent-net]
  #   environment:
  #     VLLM_EMBED_URL: http://host.docker.internal:8002/v1
  #     QDRANT_HOST: qdrant
  #     QDRANT_PORT: 6333
  #     MINIO_ENDPOINT: minio:9000

  # sync-mirror:
  #   build: ./services/sync-mirror
  #   volumes:
  #     - mirror_data:/data/mirror:rw
  #   networks: [agent-net]
  #   environment:
  #     MIRROR_SOURCE: ${MIRROR_SOURCE:-smb}
  #     MIRROR_SYNC_INTERVAL_MINUTES: ${MIRROR_SYNC_INTERVAL_MINUTES:-15}
  #     POSTGRES_HOST: postgres

  # sync-back:
  #   build: ./services/sync-back
  #   volumes:
  #     - staging_data:/data/staging:ro
  #     - archive_data:/data/archive:rw
  #   networks: [agent-net]
  #   environment:
  #     POSTGRES_HOST: postgres

  # approval-ui:
  #   build: ./services/approval-ui
  #   ports: ["4000:4000"]
  #   volumes:
  #     - staging_data:/data/staging:rw
  #   networks: [agent-net]
  #   environment:
  #     POSTGRES_HOST: postgres
  #     APPROVAL_UI_HOST: ${APPROVAL_UI_HOST}

  # email-notifier:
  #   build: ./services/email-notifier
  #   networks: [agent-net]
  #   environment:
  #     POSTGRES_HOST: postgres
  #     EMAIL_PROVIDER: ${EMAIL_PROVIDER:-smtp}
  #     SMTP_HOST: ${SMTP_HOST}
  #     APPROVAL_UI_HOST: ${APPROVAL_UI_HOST}
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(docker): add production docker-compose with infrastructure services

Running services: postgres, qdrant, minio, nginx, gateway.
Remaining services commented out as stubs for later stages.
Health checks on all active services. agent-net bridge network."
```

---

## Task 9: Docker Compose — Dev Overrides

**Files:**
- Create: `docker-compose.dev.yml`

- [ ] **Step 1: Write docker-compose.dev.yml**

```yaml
# docker-compose.dev.yml
# Local development overrides — use with:
#   docker compose -f docker-compose.yml -f docker-compose.dev.yml up
#
# Changes from production:
# - No vLLM required (nginx health check relaxed)
# - Postgres port exposed for local tools
# - MinIO console port exposed
# - Debug logging enabled

version: "3.9"

services:
  postgres:
    ports:
      - "5432:5432"
    environment:
      POSTGRES_PASSWORD: devpassword

  qdrant:
    ports:
      - "6333:6333"
      - "6334:6334"

  minio:
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin

  nginx:
    # In dev mode without vLLM, nginx will return 502 for /v1/* requests
    # This is expected — services should handle LLM errors gracefully
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 10s

  gateway:
    environment:
      ENV: development
      LOG_LEVEL: DEBUG
    # Mount source for hot-reload during development
    volumes:
      - ./services/gateway/src:/app/src
    command: ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3000", "--reload"]
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.dev.yml
git commit -m "feat(docker): add dev compose overrides

- Relaxed nginx health check (no vLLM needed locally)
- Hot-reload for gateway service
- Debug logging enabled
- Simple dev passwords"
```

---

## Task 10: Documentation — README + AGENTS.md

**Files:**
- Create: `README.md`
- Create: `AGENTS.md`

- [ ] **Step 1: Create README.md**

```markdown
# Corporate AI Agent System

Multi-agent AI system for Brooker Group committee operations. Phase 1 covers the Capital Allocation & ALCO Committee (CAC).

## Architecture

```text
Slack ──> Slack Bot ──> CAC Orchestrator ──> Specialist Agents
                            │                    │
                            ▼                    ▼
                        RAG Pipeline        Staging Writer
                            │                    │
                            ▼                    ▼
                        Qdrant            Approval UI ──> HOD Email
                                                │
                                                ▼
                                          Sync Back ──> Corporate Data
```text

**Key principle:** Agents read a mirror copy of corporate data. All changes require human approval.

## Quick Start

```bash
# 1. Copy environment config
cp .env.example .env
# Edit .env with your values

# 2. Start infrastructure (local dev)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 3. Verify health
bash scripts/healthcheck.sh
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| gateway | 3000 | API gateway |
| cac-orchestrator | 3001 | LangGraph agent graph |
| slack-bot | 3003 | Slack Events API listener |
| rag-ingestion | 3004 | Document ingestion + RAG |
| approval-ui | 4000 | HOD approval dashboard |
| postgres | 5432 | Database |
| qdrant | 6333 | Vector store (REST), 6334 (gRPC) |
| nginx | 8080 | vLLM load balancer |
| minio | 9000 | Document store |

## Data Zones

- **Zone 1** `/data/mirror/` — Read-only copy of corporate data (synced every 15 min)
- **Zone 2** `/data/staging/` — Agent proposals awaiting approval
- **Zone 4** `/data/archive/` — Permanent audit trail of all decisions

## Tech Stack

- **LLM:** Qwen3.5 122B via vLLM on DGX Spark (dual-Spark load balanced)
- **Agents:** LangGraph + LlamaIndex
- **Vector Store:** Qdrant
- **API:** FastAPI
- **Database:** PostgreSQL 16
- **Containers:** Docker Compose

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Lint
ruff check .

# Type check
mypy services/
```

## Documentation

- [PRD](PRD.md) — Product Requirements Document
- [Architecture Spec](docs/superpowers/specs/2026-03-25-architecture-design.md)
- [Implementation Progress](docs/Implementation.md)
```

- [ ] **Step 2: Create AGENTS.md**

```markdown
# AGENTS.md — Session Context

Paste this into Claude Code at the start of each session for full project context.

## Project

Corporate AI Agent System for Brooker Group. Phase 1: Capital Allocation & ALCO Committee.

## Current Stage

**Stage 1: Infrastructure** — See `docs/Implementation.md` for progress.

## Key Files

- `PRD.md` — Full product requirements
- `docs/superpowers/specs/2026-03-25-architecture-design.md` — Architecture spec
- `docs/Implementation.md` — Stage progress checklist
- `docker-compose.yml` — Docker infrastructure
- `.env.example` — All environment variables

## Architecture Summary

- 12 Docker services on `agent-net` bridge network
- nginx on port 8080 load-balances dual DGX Spark vLLM (port 8000)
- Qwen3.5 122B for reasoning, Qwen3.5 9B for embeddings (port 8002)
- PostgreSQL with 7 tables, Qdrant for vectors, MinIO for documents
- Data zones: mirror (ro), staging (rw), archive (rw)
- Agents read mirror only, propose changes via staging, require HOD approval
```

- [ ] **Step 3: Commit**

```bash
git add README.md AGENTS.md
git commit -m "docs: add README and AGENTS.md

- README: architecture overview, quickstart, service table
- AGENTS.md: session context for Claude Code"
```

---

## Task 11: Data Directory Setup Script

**Files:**
- Create: `scripts/setup-data-dirs.sh`

- [ ] **Step 1: Create setup-data-dirs.sh**

```bash
#!/bin/bash
# Create data zone directories for the Corporate AI Agent system.
# Run once on the DGX Spark host before starting Docker.
# Usage: sudo bash scripts/setup-data-dirs.sh

set -euo pipefail

DATA_ROOT="${DATA_ROOT:-/data}"

echo "Creating data zone directories under ${DATA_ROOT}..."

# Zone 1: Mirror (agents read from here)
mkdir -p "${DATA_ROOT}/mirror/excel"
mkdir -p "${DATA_ROOT}/mirror/documents"
mkdir -p "${DATA_ROOT}/mirror/db_snapshots"

# Zone 2: Staging (agent proposals)
mkdir -p "${DATA_ROOT}/staging/pending"
mkdir -p "${DATA_ROOT}/staging/approved"
mkdir -p "${DATA_ROOT}/staging/rejected"
mkdir -p "${DATA_ROOT}/staging/metadata"

# Zone 4: Archive (permanent audit)
mkdir -p "${DATA_ROOT}/archive"

# Set permissions
chmod -R 755 "${DATA_ROOT}/mirror"
chmod -R 755 "${DATA_ROOT}/staging"
chmod -R 755 "${DATA_ROOT}/archive"

echo "Data directories created:"
find "${DATA_ROOT}" -type d | sort
echo ""
echo "Done. Ready for docker compose up."
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x scripts/setup-data-dirs.sh
git add scripts/setup-data-dirs.sh
git commit -m "feat(scripts): add data directory setup script

Creates /data/mirror/, /data/staging/, /data/archive/ with
subdirectories per PRD data zone architecture."
```

---

## Task 12: Health Check Script

**Files:**
- Create: `scripts/healthcheck.sh`

- [ ] **Step 1: Create healthcheck.sh**

```bash
#!/bin/bash
# Verify all Docker services are healthy.
# Usage: bash scripts/healthcheck.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

check_service() {
    local name="$1"
    local url="$2"
    local expected="${3:-200}"

    if curl -sf -o /dev/null -w "%{http_code}" "$url" | grep -q "$expected"; then
        echo -e "  ${GREEN}[PASS]${NC} $name ($url)"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}[FAIL]${NC} $name ($url)"
        FAIL=$((FAIL + 1))
    fi
}

check_postgres() {
    if docker compose exec -T postgres pg_isready -U agents -d corporate_agents > /dev/null 2>&1; then
        echo -e "  ${GREEN}[PASS]${NC} postgres (pg_isready)"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}[FAIL]${NC} postgres (pg_isready)"
        FAIL=$((FAIL + 1))
    fi
}

check_tables() {
    local count
    count=$(docker compose exec -T postgres psql -U agents -d corporate_agents -t -c \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')

    if [ "$count" = "7" ]; then
        echo -e "  ${GREEN}[PASS]${NC} postgres tables (${count}/7)"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}[FAIL]${NC} postgres tables (${count:-0}/7)"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "=== Corporate AI Agents — Health Check ==="
echo ""

echo "Infrastructure:"
check_postgres
check_tables
check_service "qdrant" "http://localhost:6333/healthz"
check_service "minio" "http://localhost:9000/minio/health/live"
check_service "nginx" "http://localhost:8080/health"

echo ""
echo "Application:"
check_service "gateway" "http://localhost:3000/health"

echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}Some checks failed!${NC}"
    exit 1
else
    echo -e "${GREEN}All checks passed!${NC}"
fi
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x scripts/healthcheck.sh
git add scripts/healthcheck.sh
git commit -m "feat(scripts): add health check verification script

Checks postgres (connection + 7 tables), qdrant, minio,
nginx, and gateway health endpoints."
```

---

## Task 13: Integration Test — Infrastructure Verification

**Files:**
- Create: `tests/integration/test_infrastructure.py`
- Create: `pyproject.toml` (project-level test config)

- [ ] **Step 1: Create pyproject.toml for test configuration**

```toml
[project]
name = "corporate-ai-agents"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: marks tests that require Docker services running",
]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
```

- [ ] **Step 2: Write integration test**

```python
# tests/integration/test_infrastructure.py
"""Integration tests for Stage 1 infrastructure.

Run with Docker services up:
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
    python -m pytest tests/integration/test_infrastructure.py -v -m integration
"""
import os

import httpx
import pytest

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "corporate_agents")
POSTGRES_USER = os.getenv("POSTGRES_USER", "agents")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "devpassword")


@pytest.fixture
def http_client():
    with httpx.Client(timeout=10.0) as client:
        yield client


@pytest.mark.integration
class TestPostgres:
    """Verify PostgreSQL is running with correct schema."""

    @pytest.fixture
    def pg_conn(self):
        import psycopg2

        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
        )
        yield conn
        conn.close()

    def test_postgres_connection(self, pg_conn):
        """Can connect to Postgres."""
        cur = pg_conn.cursor()
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1

    def test_postgres_has_7_tables(self, pg_conn):
        """All 7 tables exist."""
        cur = pg_conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        tables = [row[0] for row in cur.fetchall()]
        expected = [
            "agent_interactions",
            "approval_decisions",
            "email_log",
            "escalations",
            "ingested_documents",
            "staging_proposals",
            "sync_log",
        ]
        assert tables == expected

    def test_staging_proposals_has_correct_columns(self, pg_conn):
        """staging_proposals table has the expected columns."""
        cur = pg_conn.cursor()
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'staging_proposals' ORDER BY ordinal_position"
        )
        columns = [row[0] for row in cur.fetchall()]
        assert "id" in columns
        assert "confidence" in columns
        assert "status" in columns
        assert "interaction_id" in columns


@pytest.mark.integration
class TestQdrant:
    """Verify Qdrant vector store is running."""

    def test_qdrant_healthz(self, http_client):
        """Qdrant health endpoint responds."""
        response = http_client.get("http://localhost:6333/healthz")
        assert response.status_code == 200


@pytest.mark.integration
class TestMinIO:
    """Verify MinIO object store is running."""

    def test_minio_health(self, http_client):
        """MinIO health endpoint responds."""
        response = http_client.get("http://localhost:9000/minio/health/live")
        assert response.status_code == 200


@pytest.mark.integration
class TestNginx:
    """Verify nginx load balancer is running."""

    def test_nginx_health(self, http_client):
        """nginx health endpoint responds."""
        response = http_client.get("http://localhost:8080/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.integration
class TestGateway:
    """Verify gateway service is running."""

    def test_gateway_health(self, http_client):
        """Gateway health endpoint responds."""
        response = http_client.get("http://localhost:3000/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "gateway"

    def test_gateway_root(self, http_client):
        """Gateway root endpoint returns service info."""
        response = http_client.get("http://localhost:3000/")
        assert response.status_code == 200
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml tests/integration/test_infrastructure.py
git commit -m "test(infra): add integration tests for Stage 1 infrastructure

Tests postgres (connection + 7 tables + columns), qdrant health,
minio health, nginx LB health, and gateway health endpoint.
Also adds pyproject.toml with pytest, ruff, and mypy config."
```

---

## Task 14: Docker Build + Verification

This task validates everything works end-to-end.

- [ ] **Step 1: Copy .env.example to .env for local dev**

```bash
cp .env.example .env
# Edit POSTGRES_PASSWORD=devpassword in .env
```

- [ ] **Step 2: Build and start Docker services**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

Expected: postgres, qdrant, minio, nginx, gateway all start

- [ ] **Step 3: Wait for services to be healthy**

```bash
docker compose ps
```

Expected: All 5 services show "healthy" or "running"

- [ ] **Step 4: Run health check script**

```bash
bash scripts/healthcheck.sh
```

Expected: All checks pass (postgres connection, 7 tables, qdrant, minio, nginx, gateway)

- [ ] **Step 5: Run integration tests**

```bash
pip install psycopg2-binary httpx pytest
python -m pytest tests/integration/test_infrastructure.py -v -m integration
```

Expected: All tests pass

- [ ] **Step 6: Run unit tests**

```bash
python -m pytest tests/unit/ -v
```

Expected: 2 passed (gateway tests)

- [ ] **Step 7: Run ruff lint**

```bash
pip install ruff
ruff check .
```

Expected: No errors

- [ ] **Step 8: Stop containers**

```bash
docker compose down
```

- [ ] **Step 9: Final commit with verification notes**

```bash
# Verify .env is NOT tracked (should be in .gitignore)
git status  # Confirm .env does NOT appear in staged/untracked

# Only stage if there are any remaining unstaged files from earlier tasks
# Do NOT use git add -A — stage explicitly
git status --short
# If clean, skip the commit. If files remain:
# git add <specific-files>
git commit -m "feat: Stage 1 Infrastructure complete

All infrastructure services running and verified:
- PostgreSQL 16 with 7-table schema
- Qdrant 1.12 vector store
- MinIO object store
- nginx load balancer (port 8080, dual-Spark ready)
- Gateway service with health endpoint
- All health checks passing
- Integration and unit tests passing
- ruff lint clean"
```

---

## Task 15: Update Implementation.md

- [ ] **Step 1: Mark Stage 1 tasks as complete in docs/Implementation.md**

Check off all Stage 1 items:
```
- [x] Create repository directory structure
- [x] Create .gitignore
- [x] Create .env.example
- [x] Create README.md
- [x] Create AGENTS.md
...etc
```

- [ ] **Step 2: Commit**

```bash
git add docs/Implementation.md
git commit -m "docs: mark Stage 1 Infrastructure complete"
```

---

## Summary

| Task | Description | Files | Test |
|------|-------------|-------|------|
| 1 | Directory scaffold | 30+ .gitkeep, .gitignore | — |
| 2 | Environment config | .env.example | — |
| 3 | vLLM launch scripts | 2 shell scripts | — |
| 4 | nginx LB config | nginx.conf | — |
| 5 | DB migration | 001_initial_schema.sql | — |
| 6 | Config skeletons | 5 JSON files | — |
| 7 | Gateway service | Dockerfile, main.py, requirements.txt | test_gateway.py |
| 8 | Docker Compose prod | docker-compose.yml | — |
| 9 | Docker Compose dev | docker-compose.dev.yml | — |
| 10 | Documentation | README.md, AGENTS.md | — |
| 11 | Data dir script | setup-data-dirs.sh | — |
| 12 | Health check script | healthcheck.sh | — |
| 13 | Integration tests | test_infrastructure.py, pyproject.toml | test_infrastructure.py |
| 14 | Build + verify | — | All tests + healthcheck |
| 15 | Update progress | Implementation.md | — |

**Total: 15 tasks, ~50 steps, ~13 commits**
