# Corporate AI Agent System — Phase 1: CAC Committee

## Project Identity
Multi-agent AI system for Capital Allocation & ALCO Committee (CAC).
Reads Slack channels + uploaded documents, answers with citations, proposes Excel changes via staging pipeline, requires human approval before touching live data.

**PRD:** `PRD.md` (v2.2) — the single source of truth for all requirements.
**Progress:** `docs/Implementation.md` — checklist tracking. Read this first every session to find current task.

## CRITICAL — Data Safety Rule
```
Agents NEVER write to /data/mirror/ or any corporate system directly.
Agents write ONLY to /data/staging/pending/ via staging_writer.py.
All changes require human approval in approval-ui (port 4000) before sync.
Docker enforces /data/mirror/ as :ro (read-only) inside agent containers.
```
Violating this rule means data corruption. Every code review must verify this.

## Data Zones
```
Zone 0: Corporate Data (source of truth — external, never agent-accessible)
Zone 1: /data/mirror/   — read-only mount for all agent containers
Zone 2: /data/staging/  — agent writes here: pending/ approved/ rejected/
Zone 3: Approval Gate   — human decides in approval-ui (reached via email link)
Zone 4: /data/archive/  — permanent audit + sync back to corporate
```

## Communication Layers
- **Slack** — agents + committee members, cross-dept coordination
- **Email** — HOD formal approval notifications and escalation alerts ONLY
- **Approval UI (port 4000)** — browser, HOD clicks email link, reviews diff, decides
- **Obsidian** — human-facing knowledge UI for SKILL.md, meeting notes, decision log

## Services
| Service | Port | Purpose |
|---------|------|---------|
| gateway | 3000 | API gateway |
| cac-orchestrator | 3001 | LangGraph CAC agent graph |
| slack-bot | 3003 | Slack Events API listener |
| rag-ingestion | 3004 | Document + message + vault ingestion |
| sync-mirror | internal | Pulls corporate data to /data/mirror/ every 15min |
| sync-back | internal | Writes approved staging changes to corporate |
| approval-ui | 4000 | Human review dashboard (browser) |
| email-notifier | internal | HOD email notifications |
| paperclip | 3100 | Agent orchestration shell (Node.js) |
| postgres | 5432 | Database |
| qdrant | 6333 | Vector store (REST), 6334 (gRPC) |
| minio | 9000 | Document store |

## LLM (on host, NOT in Docker)
- **Qwen3.5 122B Q8:** `http://host.docker.internal:8000/v1` (all reasoning)
- **Qwen3.5 9B embed:** `http://host.docker.internal:8002/v1` (embeddings only)

All Docker containers call vLLM via `host.docker.internal`. Use `langchain-openai` with OpenAI-compatible API.

## Tech Stack
- **Agent framework:** LangGraph 0.2+ with PostgresSaver checkpointer
- **RAG:** LlamaIndex 0.11+ (chunking, embedding, vault watcher)
- **Vector store:** Qdrant 1.12+ (collections: cac_docs, cac_chat, cac_knowledge, shared_policies)
- **Chat platform:** Slack Bolt (Python)
- **API services:** FastAPI + Uvicorn
- **Excel:** openpyxl 3.1+
- **Database:** PostgreSQL 16
- **Validation:** Pydantic v2
- **Container orchestration:** Docker Compose
- **Testing:** pytest 8.0+
- **Linting:** ruff

## Python Standards
- Python 3.11+
- async/await for all I/O operations
- Pydantic v2 models for all data structures
- Type hints everywhere, mypy strict
- ruff for linting and formatting
- pytest for all tests
- No hardcoded secrets — use `.env` and `python-dotenv`

## Project Structure
```
services/{name}/
  Dockerfile
  src/
    main.py        — FastAPI app with /health endpoint
    ...
skills/
  shared/          — cross-department skills
  cac/             — CAC-specific SKILL.md files
config/
  excel_schema/    — Excel tracker structure definitions
  dept_channels.json
  hod_emails.json
  escalation_rules.json
  obsidian_watch.json
tests/
  unit/
  integration/
  fixtures/
```

## Build Order
Follow PRD.md Section 13. Build one service per session.
Week 1: Infrastructure (vLLM + Docker + Postgres/Qdrant/MinIO)
Week 2: Mirror + RAG
Week 3: Slack Bot
Week 4: CAC Orchestrator (core graph)
Week 5: All Agents + Staging Writer
Week 6: Approval UI + Sync Back + Email Notifier + Obsidian
Week 7: Paperclip + Integration
Week 8: UAT + Go-Live

## Testing
- Unit tests alongside every component (not at the end)
- Integration tests for cross-service flows
- See PRD Section 14 for full test file list
- Target: 80%+ coverage on business logic
- Always mock external services (Slack, vLLM, Qdrant) in unit tests
- Use real Postgres + Qdrant in integration tests

## Key Config Files
- `config/excel_schema/alco_tracker.json` — must be populated with real Excel structure before Week 5
- `config/hod_emails.json` — must have real HOD addresses before Week 6
- `config/escalation_rules.json` — configurable breach triggers
- `config/obsidian_watch.json` — vault folders watched by LlamaIndex

## SKILL.md Format (PRD Section 11)
Every agent skill file must have: Mandate, Tone & Style, Domain Knowledge, Retrieval Instructions, Staging Proposal Rules, Excel Navigation, Escalation Triggers, Output Format, Hard Rules.

## Staging Proposal Manifest Schema
```json
{
  "id": "chg_XXXX",
  "agent": "funding-agent",
  "file": "ALCO_Tracker.xlsx",
  "tab": "Funding Facilities",
  "cell": "E8",
  "old_value": null,
  "new_value": "3.15",
  "source": "Slack #cac-committee | Jane Doe | 2026-03-24T10:42",
  "confidence": 0.91,
  "reasoning": "...",
  "status": "pending"
}
```

## Git Workflow
- Feature branches off main
- One service per PR when possible
- Never commit `.env`, credentials, or API keys
- Run `ruff check` and `pytest` before committing
