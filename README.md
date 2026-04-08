# Corporate AI Agent System

Multi-agent AI system for Brooker Group committee operations. Phase 1 covers the Capital Allocation & ALCO Committee (CAC).

## Architecture

```
Slack --> Slack Bot --> CAC Orchestrator --> Specialist Agents
                            |                    |
                            v                    v
                        RAG Pipeline        Staging Writer
                            |                    |
                            v                    v
                        Qdrant            Approval UI --> HOD Email
                                                |
                                                v
                                          Sync Back --> Corporate Data
```

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

- **Zone 1** `/data/mirror/` - Read-only copy of corporate data (synced every 15 min)
- **Zone 2** `/data/staging/` - Agent proposals awaiting approval
- **Zone 4** `/data/archive/` - Permanent audit trail of all decisions

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

- [PRD](PRD.md) - Product Requirements Document
- [Architecture Spec](docs/superpowers/specs/2026-03-25-architecture-design.md)
- [Implementation Progress](docs/Implementation.md)
