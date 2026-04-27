# Project Management — TODO Index

Master index of all outstanding setup, implementation, and go-live tasks.
Organised by domain. Each file tracks its own completion status.

Includes audit findings from 2026-04-10 full-system audit (5 parallel audits: DB schema, backend API, frontend, AI/vLLM, LangGraph).

| File | Domain | Items | CRIT | HIGH | MED |
|------|--------|-------|------|------|-----|
| [todo_infrastructure.md](todo_infrastructure.md) | Docker, data dirs, networking, scripts | 7 | 3 | 2 | 2 |
| [todo_ai_infra.md](todo_ai_infra.md) | vLLM, embeddings, LLM prompts, timeouts | 19 | 5 | 7 | 7 |
| [todo_database.md](todo_database.md) | Postgres, migrations, column alignment, Qdrant | 14 | 4 | 6 | 4 |
| [todo_config.md](todo_config.md) | .env, JSON configs, JWT keys, env var naming | 8 | 2 | 4 | 2 |
| [todo_integrations.md](todo_integrations.md) | Slack, Email, SharePoint, SFTP | 8 | 2 | 4 | 2 |
| [todo_services.md](todo_services.md) | Inter-service wiring, graph logic, API mismatches | 25 | 5 | 8 | 12 |
| [todo_rag_knowledge.md](todo_rag_knowledge.md) | RAG pipeline, Obsidian vault, MinIO | 7 | 1 | 4 | 3 |
| [todo_frontend.md](todo_frontend.md) | Approval UI, Next.js, browser testing | 14 | 1 | 5 | 8 |
| [todo_testing_qa.md](todo_testing_qa.md) | UAT, linting, fixtures, coverage | 7 | 0 | 4 | 3 |
| **TOTAL** | | **109** | **23** | **44** | **43** |

## Priority Legend

- **P0 — Critical**: Blocks all services from starting or running; will crash at runtime
- **P1 — High**: Required before real users interact with the system; silent data loss or wrong behavior
- **P2 — Medium**: Functional gaps, stubs, TODOs, maintenance traps, or fragile patterns
- **P3 — Low**: Polish, optimisation, pre-go-live quality items

## Status

- `[x]` — Done
- `[ ]` — Not started
- `[~]` — In progress / partially done

## Audit Sources (2026-04-10)

All audit findings are tagged with IDs for traceability:
- **DB-N** — Database schema alignment audit
- **API-N** — Backend API + inter-service connection audit
- **FE-N** — Frontend-to-backend connection audit
- **AI-CN/HN/MN** — AI/vLLM integration audit (Critical/High/Medium)
- **LG-N** — LangGraph orchestrator logic audit

---
*Last updated: 2026-04-10*
