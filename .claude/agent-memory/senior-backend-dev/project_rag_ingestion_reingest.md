---
name: project-rag-ingestion-reingest
description: POST /reingest-vault endpoint added to rag-ingestion; config mount gap discovered and fixed
metadata:
  type: project
---

Task #50 added `POST /reingest-vault` to `services/rag-ingestion/src/main.py`.

**What was built:**
- `services/rag-ingestion/src/vault_reingest.py` — `VaultReingester` class (the business logic layer, kept separate from main.py for testability)
- `services/rag-ingestion/src/models.py` — `ReIngestVaultRequest`, `ReIngestVaultResult`, `FileIngestResult` models added
- `services/rag-ingestion/src/qdrant_store.py` — `delete_by_source_prefix()` added (scroll+batch-delete for stale chunks)
- `services/rag-ingestion/src/main.py` — `/reingest-vault` endpoint + watch_config loading in lifespan
- `tests/unit/test_rag_ingestion_reingest.py` — 8 unit tests (all pass)
- `scripts/ingest_dept.py` — replaced per-file loop with single `/reingest-vault` streaming call; added `--subdirs`, `--delete-stale`, `--dry-run` CLI flags

**Config mount gap discovered:**
The `rag-ingestion` container could not read `obsidian_watch.json` because `/app/config/` was never mounted. Fixed by adding `- ./config:/app/config:ro` to `docker-compose.dev.yml`. The production `docker-compose.yml` also lacks this mount — needs attention when deploying to prod.

**Pre-existing bug documented (not fixed):**
`QdrantStore.upsert_chunks()` uses `uuid.uuid4()` for point IDs — non-deterministic. Re-ingesting the same file creates duplicate vectors rather than upserting. Fix requires deriving IDs from `hash(source_path + chunk_index)`. Documented in the `/reingest-vault` docstring.

**delete_by_source_prefix implementation note:**
Uses scroll+filter+delete-by-IDs (not Qdrant's filter-delete API) because the Python client's `delete()` with a `Filter` selector uses exact match, not prefix. The scroll approach is safe for collections up to ~500k points.

**Why:** ingest_dept.py loop was ~38s for IB (16 files), ~203s for IC (75 files) sequentially, no streaming, no gateway-triggerable endpoint.
**How to apply:** When triggering vault re-ingest from gateway/scheduler, use `POST /reingest-vault` with `Content-Type: application/json`. Stream the NDJSON response for progress. Use `dry_run=true` to validate file discovery before committing.
