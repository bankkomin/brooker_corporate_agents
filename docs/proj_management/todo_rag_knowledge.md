# TODO — RAG & Knowledge Base

RAG pipeline, Qdrant collections, Obsidian vault, MinIO document store.

---

## P0 — Critical

### [ ] Seed Obsidian vault with initial content
- **Status:** [x] Done — 9 articles created in previous session
- 6 financial concepts (LCR, NSFR, CAR, CET1, Duration Gap, RWA) in `obsidian-vault/cac/concepts/`
- 2 shared policies (Data Governance, Escalation Policy) in `obsidian-vault/shared/policies/`
- 1 escalation protocol (Breach Response) in `obsidian-vault/shared/escalation-protocols/`
- **Remaining:** Add entity docs, decision records, meeting notes, and trend articles when real data is available

---

## P1 — High

### [ ] Remove embedding dimension 1536 fallback — fail fast instead
- **Audit finding (AI-H5)** — silently creates broken Qdrant collections
- `services/rag-ingestion/src/main.py:49` falls back to `dim = 1536` if vLLM unreachable
- Qwen 3.5 9B actual dimension: 4096
- Collections created with wrong dimension; all upserts fail with dimension mismatch
- **Fix:** Remove fallback; fail fast at startup if embed endpoint unreachable, or add `EMBEDDING_DIM` env var

### [ ] Create MinIO buckets for document storage
- MinIO runs on port 9000 (API) / 9001 (console)
- No bucket initialisation is configured in docker-compose
- `rag-ingestion` needs a bucket for uploaded documents
- **Fix:** Create bucket on first startup: `mc mb minio/documents`; or add init container to docker-compose

### [ ] Place real `ALCO_Tracker.xlsx` in mirror directory
- Must exist at `/data/mirror/ALCO_Tracker.xlsx`
- Without it, excel_navigator can map cells but sync-back has nothing to modify
- Can use a template copy for UAT testing
- **Dependency:** `config/excel_schema/alco_tracker.json` must match this file's structure

### [ ] Verify Qdrant embedding dimension matches vLLM model
- Auto-detected from first embedding call; falls back to 1536 (wrong) if vLLM is down
- Check with: `curl http://localhost:8002/v1/embeddings -d '{"input":"test","model":"..."}'`
- If collections created with wrong dimension, delete and recreate before loading data

---

## P2 — Medium

### [ ] Fix embedder_type defaulting to "mock"
- **Audit finding (AI-M4)** — local dev silently stores zero-vectors in Qdrant
- `services/rag-ingestion/src/config.py:12` — `embedder_type: str = "mock"`
- Docker Compose overrides to `vllm`, but local runs without env var use mock silently
- **Fix:** Default to `"vllm"`, enable mock explicitly in test config only

### [ ] Configure vault watcher ignore patterns
- `config/obsidian_watch.json` defines ignore folders and files
- Current ignores: `.obsidian/`, `.trash/`, `templates/`, files starting with `_`
- Add patterns for `.canvas`, `.excalidraw` if present

### [ ] Test document ingestion pipeline end-to-end
- Upload a PDF via `POST http://localhost:3004/ingest/document` (multipart form)
- Verify: file extracted -> chunked (512 tokens) -> embedded -> stored in Qdrant
- Check: `curl http://localhost:6333/collections/cac_docs` should show increased point count
- Test retrieval: query cac-orchestrator with a question about the uploaded doc

---
*Last updated: 2026-04-10*
