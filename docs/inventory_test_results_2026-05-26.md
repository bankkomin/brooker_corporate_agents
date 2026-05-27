# Full pipeline inventory — what works, what doesn't (2026-05-26)

Snapshot from a single-pass probe of every reachable service + every untested code path identified in `docs/agent_deliverables_matrix.md`. Nothing has been fixed in this pass — that's the next session's work.

---

## ✅ Baseline 73-test suite — **71/74 PASSED** (96%)

3 failures, all LLM-nondeterministic on the same flaky use-cases:
- `USE-CASE vcc: FoF I hard cap (US$150M)`
- `USE-CASE legal: actionable PE mitigation (non-Thai-resident signing)`
- `USE-CASE cio: BTC holdings per coin book (164.6554)`

These pass intermittently (peak run: 18/18); LLM variance on borderline-relevant chunks. Documented as known-flaky in matrix §15.

---

## ✅ Pipelines newly verified this pass (12)

| # | Pipeline / endpoint | Evidence | Notes |
|---|---|---|---|
| 1 | `deck-writer POST /compose` (PowerPoint generation) | HTTP 200, 38s; produced `deck_20260526_112243_d88714.pptx`, **121,136 bytes, 13 slides**, 16 sources | Title slide empty — first-slide `.title.text` is `(no title)`. Minor cosmetic but worth fixing |
| 2 | `deck-writer POST /report` (RAG-based generic `.docx`) | HTTP 200, 15s; "Stay Liquid Doctrine review" — 7 sections, 16 sources | Works |
| 3 | `cac-orchestrator POST /summary` | HTTP 200, 3.0s; coherent committee summary with sources | Works |
| 4 | `cac-orchestrator GET /report/monthly-cfo` (LLM-markdown, NOT the deterministic docx) | HTTP 200, 6.9s; 2.2KB markdown report | Works — note: this is the OLD path; the docx pipeline is `/report/cac-meeting` |
| 5 | `cac-orchestrator GET /proposals/pending` | HTTP 200; `{"count": 0, "proposals": []}` | Endpoint works; **no real proposals exist** (staging never exercised — see §"Untested data paths") |
| 6 | `approval-ui` dashboard page (port 4000) | HTTP 200, 12,126 bytes; `<title>Brooker CAC — Approval Dashboard</title>` | HTML loads. API routes return 307 redirects (likely auth-gated). Underlying flow untested. |
| 7 | `gateway` `/health` (port 3000) | HTTP 200, JSON valid | App is fine; Docker healthcheck broken (see below) |
| 8 | `heartbeat` `/health` (port 3009) | HTTP 200; `enabled_departments: []` | App fine. Empty `enabled_departments` is by design (opt-in service) |
| 9 | `reflection-engine` `/health` (port 3008) | HTTP 200, `db_available: true` | App fine; Docker healthcheck broken (see below) |
| 10 | `email-notifier` (port 3005, container-internal) | logs show `GET /health HTTP/1.1 200 OK` healthcheck running every few seconds | Internal worker; serves but not exposed externally |
| 11 | `sync-back` (port 3006, container-internal) | same — healthchecks 200 every few seconds | Worker, alive |
| 12 | **Daily logs auto-generated** | `obsidian-vault/ic/daily-logs/2026-05-26.md` = **20,042 bytes**, written **today 18:23** by reflection-engine | Reflection-engine IS firing nightly logs as designed |

---

## ❌ Broken / has-issues (5)

| # | Pipeline | Root cause | Severity | Suggested fix |
|---|---|---|---|---|
| 1 | **`cac-paperclip` container** — crash loop, restarting every ~11s | `services/paperclip/src/main.py:4` calls `load_dotenv(Path(__file__).resolve().parents[3] / ".env")` — path resolution raises `IndexError: 3` because the file isn't deep enough in the tree relative to its mount point | **High** — blocks the employee portal flow entirely | Either guard with try/except, OR compute the .env path relative to /app (matches deck-writer's pattern), OR drop the dotenv call entirely if env is injected via Docker (it is). 5-min fix |
| 2 | **`gateway` Docker healthcheck reports "unhealthy"** | Healthcheck `test: ["CMD", "curl", "-f", ...]` but **curl is not installed in the gateway image** (`exec: "curl": executable file not found in $PATH`). App is actually serving 200s. | **Low** — cosmetic; misleads ops. Same pattern as the qdrant healthcheck. | Switch healthcheck to use Python's `urllib.request` (already in stdlib + image): `test: ["CMD","python","-c","import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:3000/health',timeout=3).status==200 else 1)"]`. |
| 3 | **`reflection-engine` Docker healthcheck "unhealthy"** | Same pattern as gateway — healthcheck command incompatible with image | **Low** — app is fine and producing daily logs | Same fix as #2 |
| 4 | **`approval-ui` `/api/proposals` returns 307 instead of 200** | Probably Next.js route redirect to a login or canonical URL. App is up but data path is untested. | **Medium** — the approval flow is the only human-in-the-loop gate before writes hit `/data/mirror/`. Critical safety path with **zero verification** today. | Investigate auth flow + add a smoke test that authenticates, lists proposals, approves one. After fix #5 below seeds data. |
| 5 | **`USE-CASE` flaky tests** — 3 fail on any given run (variance) | LLM nondeterminism on borderline-relevant chunks (FoF I hard cap, PE mitigation, BTC holdings) | **Low** — never silently produces wrong answers, just abstains | Already documented in matrix §15. Adding more alias chunks + voting wrapper would push these stable. ~1h. |

---

## 🚫 Untested data paths (3 critical — never exercised end-to-end)

These all have code that exists and is wired, but no transaction has ever flowed through them:

| Path | Evidence | Why this matters |
|---|---|---|
| **`staging_writer.py` → `/data/staging/pending/`** | Directory is **empty**; `staging_proposals` postgres table has **0 rows**; archive directory empty | This is the ONLY path that ever writes to real corporate data. CAC, CIO, VCC, Finance are all `capabilityTier: write` and would use it — but no agent has ever staged a proposal in this stack's history. **Highest-priority safety verification.** |
| **`approval-ui` approve → `sync-back` writes** | depends on #1 producing a proposal | Without a real proposal we can't test the approval gate, the sync-back to mirror, or the archive copy. |
| **`email-notifier` HOD escalation email** | container is up, healthchecks pass; no email has been sent in this session | Triggered by escalation events that require a real breach or proposal to fire |

**Recommended next step:** create ONE synthetic staging proposal end-to-end (agent stages → approval-ui surfaces → human approves → sync-back writes mirror → email-notifier sends). That single happy-path test would exercise paths #1, #2, #3 simultaneously. ~1h.

---

## 📊 Summary tally

| Category | Count |
|---|---|
| Pipelines verified working (incl. baseline) | **84** (71/74 use-cases + 12 newly verified - 1 paperclip + 2 healthcheck cosmetics) |
| Pipelines with real bugs | **2** (paperclip crash loop + approval-ui /api auth — really 1 critical + 1 to investigate) |
| Pipelines with cosmetic Docker issues | **2** (gateway + reflection-engine healthcheck — app fine, status display wrong) |
| Pipelines never exercised end-to-end | **3** (staging-write, approval+sync-back, escalation-email — all interdependent) |
| LLM-flaky test cases (already known) | **3** (covered in known-issues §15 of matrix) |

---

## Recommended fix order (next session)

1. **`paperclip` crash loop** — 5 min path-resolution fix. Unblocks the employee portal entirely.
2. **Gateway + reflection-engine healthcheck commands** — 5-10 min each; same Docker pattern. Stops false-unhealthy noise.
3. **Synthetic staging proposal end-to-end test** — 1h. Verifies the 3 untested critical paths in one shot.
4. **`approval-ui /api` auth check** — 30 min. Critical because it's the human gate.
5. **Voting wrapper for 3 LLM-flaky tests** — 1h. Pushes the suite from ~95% to consistent 100%.

Total: ~3h to close every gap surfaced in this pass.

---

# Addendum — Excel staging-write deep probe

Asked: can the agents produce Excel? Tested by force-triggering `maybe_write_staging_proposal()` directly with a synthetic high-confidence answer for CIO. Result: **mechanic works**, but uncovered **3 critical config bugs** that mean the path is effectively broken end-to-end.

## What actually happens when an agent stages

The staging artefact is a **JSON manifest** at `/data/staging/pending/{dept}/{chg_id}.json` — *not* an `.xlsx`. The Excel mutation happens later via `sync-back` when approved. The manifest schema:

```json
{
  "id": "chg_7828a859",
  "agent": "cio-agent",
  "dept_id": "cio",
  "file": null,           ← would be "CIO_Dashboard.xlsx" with schema
  "tab": null,            ← would be a sheet name
  "cell": null,           ← would be e.g. "G14"
  "new_value": "1.5 bps",
  "old_value": null,
  "source": "...",
  "confidence": 0.92,
  "reasoning": "...",
  "schema_missing": true, ← the smoking gun
  "status": "pending",
  "created_at": "..."
}
```

So **yes**, an agent can produce a staging proposal. But three bugs prevent the proposal from reaching a human / a corporate Excel:

## 🚨 Bug 1 (CRITICAL): read-only-orchestrator has NO `/data/staging` volume mount

```
docker inspect read-only-orchestrator | mounts:
  bind: services/__init__.py, services/shared, services/read-only-orchestrator/src, skills, obsidian-vault, config
  ← NO /data/staging
```

Compare cac-orchestrator (correct):
```
volume: brooker_corporate_agents_staging_data → /data/staging
```

**Impact:** every Finance / CIO / VCC proposal written by the read-only-orchestrator goes to an **ephemeral container path**. It's lost on restart and INVISIBLE to `sync-back` and `approval-ui` (which both mount the named volume).

**Fix:** add `- staging_data:/data/staging:rw` to read-only-orchestrator in `docker-compose.yml`. 1-line change.

## 🚨 Bug 2 (CRITICAL): approval-ui container is NOT running

```
docker exec ... approval-ui-1 → "container is not running"
docker ps --format '{{.Names}}\t{{.Ports}}' | grep ':4000' → empty
```

Yet `curl http://localhost:4000/` returns HTML with the right title. That implies something other than the docker container is serving port 4000 — likely a stale Next.js dev process on the host, OR the container's name differs.

**Fix:** find what's actually serving 4000 (kill stray host process if needed), then bring up the real container. Verify it mounts `staging_data` and reads pending proposals from `/data/staging/pending/`.

## 🚨 Bug 3 (MEDIUM): Excel schema files missing for 6 of 12 depts

`config/excel_schema/` has:
- `alco_tracker.json` (CAC ✓)
- `compliance_tracker.json` (Legal ✓ — though Legal is read_only)
- `hr_tracker.json` (HR ✓ — though HR is read_only)
- `investment_tracker.json` (IC or CIO?)
- `it_tracker.json`, `ops_tracker.json`, `risk_dashboard.json`

**MISSING** for write-tier depts: `cio_*.json`, `vcc_*.json`, `finance_*.json` (BICL), `ceo_*.json` (OKR tracker)

**Impact:** when a CIO / VCC / Finance agent stages a proposal, the manifest has `file=null, tab=null, cell=null, schema_missing=true`. `sync-back` cannot apply such a proposal to any Excel because it doesn't know which cell to update.

**Fix:** define `cio_dashboard.json`, `vcc_nav.json`, `finance_pn_tracker.json`, `ceo_okr.json` — each pointing at the canonical Excel file + tab + cell labels. ~30 min per dept. Without these, the write-tier mode is **all bark, no bite** — proposals get written but never get applied.

## 🐛 Bug 4 (LOW): hr-orchestrator missing `/data/staging` mount

Same as Bug 1 but for HR. Doesn't matter functionally because HR is `read_only`, but the config is inconsistent. If HR ever flips to `write_via_staging` (per the SKILL discussion), proposals would silently fail.

## Net answer to "can agents produce PPT / Excel?"

| Format | Verified | Notes |
|---|---|---|
| `.pptx` PowerPoint | ✅ YES | deck-writer `/compose` produced a 13-slide, 121 KB deck in this probe |
| `.docx` (deterministic, CAC report) | ✅ YES | already verified earlier this session, 6/6 facts correct |
| `.docx` (RAG-based generic) | ✅ YES | deck-writer `/report` produced a 7-section report in this probe |
| `.xlsx` proposal **JSON manifest** (the actual staging artefact) | ✅ YES (cac-orchestrator only) | Mechanic works; cac-orch writes to the proper volume. **But also broken for Finance/CIO/VCC** (Bug 1) — their proposals land in ephemeral storage |
| **End-to-end Excel mutation** (proposal → approval → mirror write) | ❌ NO | Bugs 1+2+3 all block. The full corporate-data write path has never been exercised |

## New fix priority order (replaces the earlier "next session" list)

1. **Bug 1 (read-only-orch staging volume mount)** — 1-line compose change. ~5 min.
2. **Bug 2 (approval-ui container missing)** — investigate + restart. ~15-30 min.
3. **Bug 3 (missing Excel schemas)** — write 4 JSON schema files for CIO/VCC/Finance/CEO. ~2h.
4. **paperclip path bug** — 5 min (still on the previous list).
5. **gateway + reflection-engine healthcheck cosmetics** — 5 min each.
6. **End-to-end synthetic proposal test** (now newly feasible after 1+2+3) — 30 min.
7. **3 flaky LLM tests** — voting wrapper. ~1h.

The Excel-mutation gap is much larger than I described in the original write-up. **`capabilityTier: write` for Finance / CIO / VCC is fictional today** — they look configured but their proposals don't persist. Worth flagging in your weekly update as the most serious finding from this pass.
