# AGENTS.md - Session Context

Paste this into Claude Code at the start of each session for full project context.

## Project

Corporate AI Agent System for Brooker Group. Phase 1: Capital Allocation & ALCO Committee.

## Current Stage

**Stage 1: Infrastructure** - See `docs/Implementation.md` for progress.

## Key Files

- `PRD.md` - Full product requirements
- `docs/superpowers/specs/2026-03-25-architecture-design.md` - Architecture spec
- `docs/Implementation.md` - Stage progress checklist
- `docker-compose.yml` - Docker infrastructure
- `.env.example` - All environment variables

## Architecture Summary

- 12 Docker services on `agent-net` bridge network
- nginx on port 8080 load-balances dual DGX Spark vLLM (port 8000)
- Qwen3.5 122B for reasoning, Qwen3.5 9B for embeddings (port 8002)
- PostgreSQL with 7 tables, Qdrant for vectors, MinIO for documents
- Data zones: mirror (ro), staging (rw), archive (rw)
- Agents read mirror only, propose changes via staging, require HOD approval
