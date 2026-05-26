# Second-Brain Vault Services — Buckets B3 + B4 + B5

> **Status:** design spec, not an execution plan. Identifies integration points and contracts so a future task-by-task plan can be written without re-doing discovery.

**Source:** Gap analysis against `eugeniughelbur/obsidian-second-brain` (May 2026). Vault hygiene (Bucket D) and template/skill conventions (A3/A4/A5/B1/B2) already landed across branches `chore/vault-skill-link-hygiene` and `chore/vault-root-index-and-health-skill`. This doc covers the service-side work the gap analysis surfaced.

**Goal:** Reach the reference repo's "self-maintaining vault" behavior — automated synthesis, cross-meeting fan-out, nightly propagation — while preserving our hard constraint that **agents never write directly to corporate data or the vault outside the staging pipeline**.

---

## Scope

- **B3** — Post-meeting subagent fan-out: when a meeting note lands, parallel agents extract entities, decisions, trends and propose vault updates via staging.
- **B4** — Auto-synthesis: when the same concept appears across ≥ N source documents, the system proposes a new `concepts/` note (or update to an existing one) via staging.
- **B5** — Background propagation: a nightly reflection-engine job promotes daily-log entries and session summaries into concept updates and skill proposals, all via staging.

## Non-scope

- Bypassing the staging pipeline. Every vault write proposed by these services lands in `/data/staging/pending/` for HOD approval. The data-safety rule in `CLAUDE.md` is load-bearing.
- Replacing `[[skills/shared/wiki-maintenance]]` or `[[skills/shared/vault-health-check]]`. Those are read-only and remain authoritative for vault lint.
- Phase 2 per-dept rollouts (Stages 11–19). B3/B4/B5 are dept-agnostic and should compose with whatever per-dept orchestrators exist.
- Real-time UI. All three buckets are async / scheduled.

---

## B3 — Post-meeting subagent fan-out

### What it does

When a new file lands in `obsidian-vault/{dept}/meeting-notes/YYYY-MM-DD-*.md`, spawn parallel extraction agents that each produce one type of vault artifact, and route every output through the staging pipeline.

Reference behavior: `/obsidian-save` in the reference repo spawns 5 parallel workers (People, Projects, Tasks, Decisions, Ideas). Our adaptation: **Entities, Decisions, Trends, Index-update, Source-summary** — the artifact types our vault actually uses.

### Where it lives

`services/cac-orchestrator/` — extend the existing LangGraph graph with a post-meeting fan-out node. Reuse:
- `services/cac-orchestrator/src/graph.py` — add a `meeting_fanout` node parallel to existing nodes
- `services/cac-orchestrator/src/staging_writer.py` — already writes manifests to `/data/staging/pending/`; reuse unchanged
- `services/rag-ingestion/src/vault_watcher.py` — already detects vault file changes; emit a new event type `meeting_note_landed`
- LangGraph's `Send` API for the parallel fan-out (5 workers max)

### Integration points

```
VaultWatcher detects new meeting-notes/*.md
  ↓ POST /events to cac-orchestrator (or queue via Postgres)
cac-orchestrator.meeting_fanout node receives event
  ↓ LangGraph Send -> 5 parallel extractor workers
each worker:
  - reads meeting note content
  - extracts its artifact type (Qwen 122B via vLLM)
  - drafts proposed vault file content
  - writes staging manifest with target path obsidian-vault/{dept}/{type}/...
  ↓
manifests aggregate in /data/staging/pending/{run_id}/
  ↓
approval-ui surfaces them as a single review batch (one meeting → N proposals)
  ↓ HOD approves
sync-back writes approved files into vault
  ↓
VaultWatcher re-ingests on file change (existing loop)
```

### Contracts (sketch)

**Event payload (VaultWatcher → orchestrator):**
```json
{
  "event": "meeting_note_landed",
  "vault_path": "obsidian-vault/cac/meeting-notes/2026-05-26-alco-monthly.md",
  "dept": "cac",
  "sha256": "...",
  "size_bytes": 8421
}
```

**Worker output (one per extracted artifact):**
Standard staging manifest extended with:
```json
{
  "id": "chg_XXXX",
  "agent": "meeting-extractor-entities",
  "file": "obsidian-vault/cac/entities/bicl.md",  // target write path
  "operation": "create" | "update" | "merge",
  "extracted_from": "obsidian-vault/cac/meeting-notes/2026-05-26-alco-monthly.md",
  "source_run_id": "run_XXXX",
  "diff": { ... },  // unified diff or full content
  "confidence": 0.78,
  ...
}
```

### Open questions

1. **Where is the source meeting note allowed to write?** Currently `[[skills/shared/wiki-maintenance]]` writes to `{dept}/log.md`. Does the meeting note itself land in `pending/` first, or is the human-created note the trigger? Reference repo writes directly; we need to decide if the meeting note is a vault-write or a staging-pipeline write.
2. **What's the LLM budget per meeting?** 5 parallel workers × Qwen 122B at ~30K tokens each is ~150K tokens per meeting. Acceptable for monthly committees, would not scale to daily standups. Confirm cadence assumption.
3. **Worker idempotency.** Re-running a fan-out on the same meeting note must not create duplicate proposals. Use `source_run_id` + `dept` + worker name as the dedupe key, or store last-processed sha256 in Postgres.

### Estimated size

- ~600 lines Python (1 new graph node, 5 worker functions, event handler)
- ~400 lines tests (mock vLLM, mock staging_writer, end-to-end with fake meeting note)
- 2-3 days work for one engineer

---

## B4 — Auto-synthesis on N-source threshold

### What it does

When the same concept (named entity, regulatory rule, framework) appears in ≥ N source documents across the corpus, propose a `concepts/` note via staging. If a concept note already exists, propose an update with the new sources.

Reference repo: auto-creates synthesis page when concept appears in 3+ sources. For us, N is per-dept-tunable (regulations might need 2, research might need 4).

### Where it lives

`services/rag-ingestion/` — extend ingestion with a co-occurrence tracker. Reuse:
- `services/rag-ingestion/src/chunker.py` — already extracts entities during chunking; expose those for tracking
- `services/rag-ingestion/src/qdrant_store.py` — already stores chunks with `entity` metadata; add a Postgres-side count
- new: `services/rag-ingestion/src/synthesis_tracker.py` — Postgres table `entity_mentions(entity, source_doc, dept, mentioned_at)`
- new: `services/rag-ingestion/src/synthesis_proposer.py` — when count(distinct source_doc) ≥ threshold and no concept note exists, generate proposal

### Integration points

```
Document ingestion -> chunker extracts entities
  ↓ for each entity, INSERT into entity_mentions
  ↓
nightly job: SELECT entity, COUNT(DISTINCT source_doc), dept FROM entity_mentions GROUP BY 1, 3
  ↓ for each row above threshold:
     - check if concepts/{kebab(entity)}.md exists in vault
     - if no: draft new concept note (Qwen 122B with all mentioning chunks as context)
     - if yes: check if note's `sources:` array misses any of these; if so, propose update
  ↓
write staging manifest to /data/staging/pending/synthesis/{entity}.json
```

### Contracts (sketch)

**Postgres schema:**
```sql
CREATE TABLE entity_mentions (
  id BIGSERIAL PRIMARY KEY,
  entity TEXT NOT NULL,
  entity_kind TEXT NOT NULL,  -- 'company' | 'instrument' | 'regulation' | 'concept'
  source_doc TEXT NOT NULL,   -- relative path in O:\brooker_database or vault
  dept TEXT NOT NULL,
  mentioned_at TIMESTAMPTZ DEFAULT NOW(),
  chunk_id TEXT,              -- Qdrant chunk reference
  UNIQUE (entity, source_doc, chunk_id)
);
CREATE INDEX ON entity_mentions (entity, dept);
```

**Synthesis manifest:**
```json
{
  "id": "chg_XXXX",
  "agent": "synthesis-proposer",
  "file": "obsidian-vault/regulations/concepts/audit-committee-composition.md",
  "operation": "create",
  "synthesis_evidence": {
    "entity": "audit-committee-composition",
    "source_count": 4,
    "sources": ["SEC_BoT_Audit_Code_2024.pdf", "Internal_AC_Charter_v3.docx", ...],
    "threshold_used": 3
  },
  "draft_content": "---\ntitle: Audit Committee Composition\n...",
  "confidence": 0.85,
  ...
}
```

### Open questions

1. **Entity extraction quality.** Current `chunker.py` extracts entities — but how well? If precision is low we'll spam synthesis proposals. Sample a week of ingestion first.
2. **Per-dept thresholds.** `regulations` benefits from low N (2 sources confirm a rule); `research` should be higher (4-5) to avoid spam from the noisy 2nd_Brain corpus. Store in `config/synthesis_thresholds.json`.
3. **Concept name canonicalization.** `audit-committee` vs `audit committee` vs `Audit Committee Composition` — same concept, three strings. Need a normalizer (kebab-case slug + stopword removal) that's deterministic.
4. **Update semantics.** When a concept note exists, "update" could mean: add to `sources:` array, append a paragraph, or rewrite. Probably "add to sources + flag for human review with diff" — never auto-rewrite body.

### Estimated size

- ~800 lines Python (Postgres schema + tracker + proposer + scheduler hook)
- ~500 lines tests
- 1 Postgres migration
- 1 config file
- 3-4 days work for one engineer

---

## B5 — Background propagation (reflection-engine nightly)

### What it does

Once a day, the reflection-engine reads the day's session summaries (from `cac-orchestrator` runs and `paperclip` sessions) and proposes:
- Memory promotions: turn high-signal session content into `_memory/` entries per department
- Skill proposals: when a session reveals a repeated agent failure pattern, propose a SKILL.md update via staging
- Daily-log entries: write `{dept}/daily-logs/YYYY-MM-DD.md` summarizing what the dept's agents did today

Reference repo uses Claude Code's PostCompact hook for this. Ours is a nightly batch — same end state, different trigger.

### Where it lives

`services/reflection-engine/` — port 3008, already exists per CLAUDE.md. Confirm its current scope before extending. Likely reuses:
- Postgres `sessions` and `proposals` tables (existing)
- `services/cac-orchestrator/src/staging_writer.py` (via shared module or HTTP)
- Vault read access (Zone 1, read-only)

### Integration points

```
Cron 02:00 daily
  ↓ reflection-engine.daily_reflection()
     - read all sessions WHERE date(started_at) = yesterday
     - read all proposals WHERE created_at = yesterday
     - per dept:
         * cluster session summaries by topic
         * detect failure patterns (3+ failures on same skill in 7 days)
         * draft daily-log entry
         * draft memory promotions
         * draft skill update proposals
  ↓
write all drafts as staging manifests under /data/staging/pending/reflection/{YYYY-MM-DD}/
  ↓
email-notifier sends one digest per dept HOD with link to approval-ui batch
  ↓
HOD approves selectively; sync-back writes approved files
```

### Contracts (sketch)

**Reflection output types** (each becomes a staging manifest):
- `daily_log_entry`: target `obsidian-vault/{dept}/daily-logs/YYYY-MM-DD.md`
- `memory_promotion`: target `obsidian-vault/{dept}/_memory/{topic}.md`
- `skill_update`: target `skills/{dept}/{skill}.md` (with diff)
- `skill_proposal`: new `skills/{dept}/{name}.md` from pattern

### Open questions

1. **Does `reflection-engine` already exist as scaffolding or as a working service?** CLAUDE.md lists it at port 3008. Need to read its current state before designing the extension.
2. **What signals justify memory promotion?** Reference repo uses "session length + cross-referenced 3+ times in subsequent sessions." We need a simpler heuristic for v1 — perhaps "confidence ≥ 0.9 and user explicitly endorsed."
3. **`_memory/` semantics.** Today these folders are empty (Bucket D found this). What's the intended distinction between `_memory/` and `concepts/`? Need product decision before B5 can be designed concretely.
4. **Email-notifier batch UX.** One email per dept per day with a digest link, or one email per proposal? Batch is better UX; email-notifier may need a new "digest" mode.

### Estimated size

- Highly dependent on Q1 (existing reflection-engine state). Could be ~500 lines (extension) to ~1500 lines (build out).
- 3-5 days work for one engineer.

---

## Suggested sequencing

1. **B3 first** — Smallest blast radius (one event type, one orchestrator), highest immediate value (committees meet monthly, fan-out automates real toil). Validates the staging-pipeline path for vault writes end-to-end.
2. **B4 second** — Bigger Postgres work but composable with B3 (synthesis proposals use the same manifest schema). Per-dept thresholds can roll out gradually.
3. **B5 last** — Depends on `reflection-engine` audit (open question #1) and the `_memory/` product question (#3). Building B3 + B4 first generates the session/proposal data B5 needs to learn from.

## Cross-cutting concerns

- **Data zones (CLAUDE.md):** All three buckets write only to Zone 2 (`/data/staging/`). No Zone 0/1 writes. Verify in container `:ro` mount tests.
- **Staging manifest schema:** Extending the existing schema (CLAUDE.md §Staging Proposal Manifest Schema). Each bucket adds 1-2 optional fields; no breaking change.
- **Approval-UI:** Already handles individual manifests. B3 needs "approve all" for a meeting's batch (5 manifests at once); B4 already works per-manifest; B5 needs "digest view" per dept per day.
- **Testing:** Each bucket needs unit tests + one integration test that fakes the trigger (file landing / threshold met / cron firing) and asserts staging manifests land correctly with no writes outside Zone 2.
- **Observability:** Each bucket should log to a dept-specific log file in the vault — `{dept}/log.md` for B3 (per `[[skills/shared/wiki-maintenance]]` format), `_memory/synthesis.log.md` for B4 (new), `_memory/reflection-YYYY-MM-DD.log.md` for B5 (new). Auditable in Obsidian without leaving the vault.

## What this plan does NOT decide

- The threshold N for B4 per dept (deferred to config).
- The `_memory/` vs `concepts/` distinction (B5 blocker — needs product call).
- Whether `meeting_note_landed` events go via HTTP POST or Postgres queue (B3 — depends on existing eventing patterns).
- Whether the fan-out node uses LangGraph's `Send` or spawns separate Task tool agents (B3 — implementation detail).

A follow-up task-by-task plan (matching the format of `2026-05-18-shared-investment-cluster-skill-set.md`) should be written per-bucket, after these open questions are resolved and the relevant service code has been re-audited.
