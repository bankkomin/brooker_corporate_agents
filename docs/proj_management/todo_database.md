# TODO — Database

PostgreSQL setup, migrations, connection management, and Qdrant collections.

---

## P0 — Critical

### [ ] Fix sync-back queries referencing non-existent columns on `staging_proposals`
- **Audit finding (DB-1, DB-2, DB-3)** — will crash at runtime
- `services/sync-back/src/processor.py:42-58` — SELECT references `proposal_id`, `approved_at`, `approved_by`, `synced_at` — none exist. PK is `id`, not `proposal_id`
- `services/sync-back/src/archiver.py:29-55` — SELECT references `proposal_id`, `approved_at`, `approved_by`, `rejected_at`, `rejected_by`, `synced_at`, `archived_at` — none exist
- `services/sync-back/src/rollback.py:43-44` — `WHERE proposal_id = $1` — column doesn't exist, rollback after failed Excel write is broken
- **Root cause:** sync-back was written assuming `staging_proposals` has columns that only exist in `approval_decisions`
- **Fix (option A — preferred):** Rewrite sync-back queries to use `id` as PK and JOIN `approval_decisions` for approval metadata — matches gateway's existing pattern
- **Fix (option B):** New migration `008_staging_approval_columns.sql` adding the missing columns
- **Blocking:** Entire sync-back pipeline is non-functional without this fix

### [ ] Fix sync-mirror inserting wrong column names into `sync_log`
- **Audit finding (DB-5)** — will crash on every sync cycle
- `services/sync-mirror/src/main.py:39-47` and `services/sync-mirror/src/sync_log.py:19-28`
- Inserts `source`, `files_synced`, `error_detail` — actual columns are `files_updated`, `files_checked`, `error`
- `synced_at` is auto-set by DEFAULT NOW() so passing it explicitly is redundant but not an error
- **Fix:** Update column names in both files to match migration `001_initial_schema.sql`

### [ ] Fix email-notifier scheduler querying non-existent `proposal_id` column
- **Audit finding (DB-4)** — 24h overdue reminder job crashes on every run
- `services/email-notifier/src/scheduler.py:39-43` — `SELECT proposal_id` from `staging_proposals` — column is `id`
- **Fix:** Change `proposal_id` to `id` in the SELECT

### [ ] Verify Postgres migrations run on first startup
- 4 migration files in `migrations/`:
  - `001_initial_schema.sql` — 7 core tables
  - `002_add_interaction_fk.sql` — FK: staging_proposals.interaction_id -> agent_interactions.id
  - `003_dept_columns.sql` — Add `dept` column to staging_proposals, escalations, approval_decisions
  - `007_paperclip_tables.sql` — paperclip tables + CAC seed data
- Confirm entrypoint runs all `.sql` files in order on first boot
- **Test:** `docker compose up postgres` then `docker exec postgres psql -U cac -d cac_db -c '\dt'` — should list 11 tables

---

## P1 — High

### [ ] Fix email_sender writing `'retrying'` status that violates CHECK constraint
- **Audit finding (DB-7)** — crashes retry loop exactly when you need it
- `services/email-notifier/src/email_sender.py:137` — `update_email_status(..., status="retrying")`
- `email_log.delivery_status` CHECK allows only: `'sent', 'delivered', 'failed', 'bounced', 'pending'`
- PostgreSQL rejects `'retrying'` with constraint violation, crashing before retry exhaustion
- **Fix:** Use `'pending'` instead of `'retrying'`, or add `'retrying'` to the CHECK via migration

### [ ] Fix sync-back Pydantic models mirroring non-existent columns
- **Audit finding (DB-6)** — downstream of the broken queries
- `services/sync-back/src/models.py` — `ApprovedProposal` has `approved_at`, `approved_by`; `ArchiveRecord` has `rejected_at`, `rejected_by`
- These fields are populated from DB rows that reference non-existent columns
- **Fix:** Update models to source approval metadata from `approval_decisions` table

### [ ] Fix orchestrator INSERT omitting `dept` column
- **Audit finding (DB-8)** — masked by DEFAULT, but wrong for multi-department
- `services/cac-orchestrator/src/tools/db_client.py:134-154` — INSERT into `staging_proposals` omits `dept`
- Works only because `DEFAULT 'cac'` exists — silently assigns all proposals to CAC
- **Fix:** Add explicit `dept` parameter from graph state

### [ ] Fix vault_watcher overwriting `created_at` on re-index
- **Audit finding (DB-9)** — corrupts original ingestion timestamp
- `services/rag-ingestion/src/vault_watcher.py:229-235` — `ON CONFLICT DO UPDATE SET created_at = NOW()`
- `created_at` is semantically the first-ingestion time; being used as `updated_at`
- **Fix:** Add `updated_at` column via migration `008_*`, update the UPSERT to SET `updated_at = NOW()`

### [ ] Set Postgres credentials in `.env`
- Variables: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- Default in docker-compose.dev.yml is dev-only — must change for production
- **File:** `.env` (create from `.env.example`)

### [ ] Verify Qdrant collection auto-creation
- `rag-ingestion` auto-creates 4 collections: `cac_docs`, `cac_chat`, `cac_knowledge`, `shared_policies`
- **Important:** If vLLM embedding model isn't running at startup, collections get wrong dimension (see todo_ai_infra.md H5)
- **Test:** `curl http://localhost:6333/collections` after rag-ingestion starts

---

## P2 — Medium

### [ ] Fix sync-mirror `SyncLogger` using psycopg2 in async context
- **Audit finding (DB-10)** — blocks event loop
- `services/sync-mirror/src/sync_log.py` uses `psycopg2` with `%s` placeholders (synchronous)
- `log_sync()` is `async` but internally calls synchronous psycopg2 — blocks event loop
- **Fix:** Convert to `asyncpg` with `$N` placeholders to match the rest of the codebase

### [ ] Fix vault_watcher using psycopg2 without connection pooling
- **Audit finding (DB-11)** — can exhaust Postgres connections
- `services/rag-ingestion/src/vault_watcher.py` wraps psycopg2 in `asyncio.to_thread` (avoids blocking) but opens/closes a new connection per call with no pooling
- **Fix:** Use the existing asyncpg pool from the service, or add a psycopg2 pool

### [ ] Fix Paperclip CREATE_TICKET RETURNING clause
- **Audit finding (DB-12)** — cosmetic inconsistency
- `services/paperclip/src/db/queries.py:9-12` — RETURNING omits `interaction_id` even though it's inserted
- Freshly-created ticket appears to have no `interaction_id` in creation response
- **Fix:** Add `interaction_id` to RETURNING clause

### [ ] Review migration gap: 004-006 missing
- Migrations jump from `003` to `007`
- Likely intentional (stages 4-6 didn't add tables) but should be confirmed
- Future migrations should continue from `008`

---
*Last updated: 2026-04-10*
