# Stage 10 — Phase 2 Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 2 department-onboarding framework infrastructure so 9 downstream departments (Stages 11-19) can be added with ~1.5 days of effort each instead of 5 days.

**Architecture:** Three layers — (1) catalog config (`departments.json` extended + new `document_inventory.json`), (2) code templates (`services/_template-orchestrator/` + `skills/_template/`), (3) two new shared services (`reflection-engine` for self-improvement, `heartbeat` for opt-in proactive layer). Plus per-skill permission frontmatter, knowledge-gap tracking, an `agent_performance` signal-strength view, and approval-ui extensions for skill-update review + knowledge-gap admin.

**Tech Stack:** Python 3.11+, FastAPI, LangGraph 0.2+, AsyncPostgresSaver (Postgres 16), Qdrant 1.12+, Claude Agent SDK, APScheduler, Pydantic v2, langchain-openai, Next.js 15 + Tailwind 4 (approval-ui), Vitest, pytest 8.0+, ruff.

**Spec:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`

---

## Phase 0 — Setup & Regression Baseline

### Task 0.1: Create feature branch

**Files:**
- Modify: git state

- [ ] **Step 1: Create branch from main**

```bash
git checkout main
git pull
git checkout -b stage-10-phase2-framework
```

- [ ] **Step 2: Verify clean working tree**

Run: `git status`
Expected: `nothing to commit, working tree clean`

### Task 0.2: Capture regression baseline

**Files:**
- Create: `tests/baselines/stage9-regression-baseline.txt`
- Create: `tests/baselines/cac-golden-fixtures/` (recorded CAC responses)
- Create: `tests/baselines/hr-golden-fixtures/` (recorded HR responses)

- [ ] **Step 1: Run full test suite, save output**

```bash
pytest --tb=no -q > tests/baselines/stage9-regression-baseline.txt 2>&1
echo "Baseline test count: $(grep -c '^PASS' tests/baselines/stage9-regression-baseline.txt)"
```

Expected: ≥ 391 tests pass.

- [ ] **Step 2: Record golden-master CAC fixtures**

Run a curated set of 10 CAC queries (covering each specialist) and save responses:

```bash
python scripts/record_golden_master.py --orchestrator cac --output tests/baselines/cac-golden-fixtures/
```

If `scripts/record_golden_master.py` doesn't exist yet, create a minimal version that POSTs to `localhost:3001/query` with 10 fixed queries and writes `(query, response, citations, confidence)` JSON.

- [ ] **Step 3: Record golden-master HR fixtures**

```bash
python scripts/record_golden_master.py --orchestrator hr --output tests/baselines/hr-golden-fixtures/
```

- [ ] **Step 4: Create the diff script**

Phases 3, 7, and 8 call `scripts/diff_golden_master.py`. Create it now:

```python
# scripts/diff_golden_master.py
"""Re-run baseline queries against the live orchestrator and diff response + citations.
Exits 0 if no semantic regression; 1 if answers diverge beyond tolerance.
"""
import argparse, json, sys, requests
from pathlib import Path
from difflib import SequenceMatcher

PORTS = {"cac": 3001, "hr": 3002}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orchestrator", required=True, choices=PORTS.keys())
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--threshold", type=float, default=0.85,
                    help="min SequenceMatcher ratio for response text")
    args = ap.parse_args()

    base = Path(args.baseline)
    drift = []
    for fixture_file in sorted(base.glob("*.json")):
        recorded = json.loads(fixture_file.read_text())
        live = requests.post(
            f"http://localhost:{PORTS[args.orchestrator]}/query",
            json={"query": recorded["query"]}, timeout=60
        ).json()
        ratio = SequenceMatcher(None, recorded["response"], live["response"]).ratio()
        if ratio < args.threshold:
            drift.append({
                "fixture": fixture_file.name, "ratio": ratio,
                "baseline_excerpt": recorded["response"][:160],
                "live_excerpt":     live["response"][:160],
            })
    if drift:
        for d in drift:
            print(f"DRIFT {d['fixture']} ratio={d['ratio']:.2f}", file=sys.stderr)
            print(f"  baseline: {d['baseline_excerpt']}", file=sys.stderr)
            print(f"  live:     {d['live_excerpt']}", file=sys.stderr)
        sys.exit(1)
    print(f"OK — {len(list(base.glob('*.json')))} fixtures within tolerance")

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Commit baseline**

```bash
git add tests/baselines/ scripts/record_golden_master.py scripts/diff_golden_master.py
git commit -m "chore(stage10): capture stage 9 regression baseline + golden master fixtures + diff tool"
```

---

## Phase 1 — Schema & Config Foundation

### Task 1.1: Extend `config/departments.schema.json`

**Files:**
- Modify: `config/departments.schema.json`
- Test: `tests/unit/test_departments_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_departments_config.py
import json
from jsonschema import validate, ValidationError
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "config" / "departments.schema.json").read_text())

def test_dept_row_requires_capability_tier():
    bad = {"dept_id": "x", "name": "X"}  # missing capabilityTier
    with pytest.raises(ValidationError):
        validate(bad, SCHEMA)

def test_dept_row_requires_cross_read_access_array():
    row = {
        "dept_id": "x", "name": "X",
        "capabilityTier": "read_only",
        # crossReadAccess missing
    }
    with pytest.raises(ValidationError):
        validate(row, SCHEMA)

def test_dept_row_requires_agent_topology():
    row = {
        "dept_id": "x", "name": "X",
        "capabilityTier": "read_only",
        "crossReadAccess": [],
    }
    with pytest.raises(ValidationError):
        validate(row, SCHEMA)

def test_dept_row_full_valid():
    row = {
        "dept_id": "finance", "name": "Finance",
        "capabilityTier": "write",
        "crossReadAccess": [],
        "agentTopology": {"orchestrator": "cfo-agent", "specialists": ["a", "b", "c"]},
        "documents": ["doc_finance_annual_report"],
        "heartbeat": {"enabled": False, "schedule": "", "context_sources": [], "outbound_actions": []},
        "live": False,
    }
    validate(row, SCHEMA)  # no exception
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/unit/test_departments_config.py -v`
Expected: FAIL — schema doesn't yet require new fields.

- [ ] **Step 3: Extend schema**

```json
// config/departments.schema.json (key additions)
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["dept_id", "name", "capabilityTier", "crossReadAccess", "agentTopology"],
  "properties": {
    "dept_id":  { "type": "string", "pattern": "^[a-z][a-z0-9_-]*$" },
    "name":     { "type": "string" },
    "capabilityTier": { "enum": ["read_only", "write"] },
    "crossReadAccess": {
      "type": "array",
      "items": { "type": "string" }
    },
    "agentTopology": {
      "type": "object",
      "required": ["orchestrator", "specialists"],
      "properties": {
        "orchestrator": { "type": "string" },
        "specialists":  { "type": "array", "items": { "type": "string" } }
      }
    },
    "documents": { "type": "array", "items": { "type": "string" } },
    "heartbeat": {
      "type": "object",
      "required": ["enabled"],
      "properties": {
        "enabled":  { "type": "boolean" },
        "schedule": { "type": "string" },
        "context_sources": { "type": "array", "items": { "type": "string" } },
        "outbound_actions": { "type": "array", "items": { "type": "string" } }
      }
    },
    "live": { "type": "boolean" },
    "slackChannel": { "type": "string" },
    "hodEmail":     { "type": "string" },
    "escalationRules": { "type": "object" }
  }
}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/unit/test_departments_config.py -v`
Expected: PASS, all 4 tests.

- [ ] **Step 5: Commit**

```bash
git add config/departments.schema.json tests/unit/test_departments_config.py
git commit -m "feat(stage10): extend departments.schema.json with capabilityTier, crossReadAccess, agentTopology, heartbeat"
```

### Task 1.2: Migrate `config/departments.json`

**Files:**
- Modify: `config/departments.json`
- Test: `tests/unit/test_departments_config.py`

- [ ] **Step 1: Add migration test**

```python
# Append to tests/unit/test_departments_config.py
def test_existing_cac_dept_has_new_fields():
    data = json.loads((ROOT / "config" / "departments.json").read_text())
    cac = next(d for d in data["departments"] if d["dept_id"] == "cac")
    assert cac["capabilityTier"] == "write"
    assert cac["crossReadAccess"] == ["finance", "risk", "cio", "ceo"]
    assert cac["agentTopology"]["orchestrator"] == "cfo-agent"
    assert cac["live"] is True

def test_existing_hr_dept_has_new_fields():
    data = json.loads((ROOT / "config" / "departments.json").read_text())
    hr = next(d for d in data["departments"] if d["dept_id"] == "hr")
    assert hr["capabilityTier"] == "read_only"
    assert hr["live"] is True

def test_nine_future_depts_present_with_live_false():
    data = json.loads((ROOT / "config" / "departments.json").read_text())
    expected = {"finance", "ib", "ic", "cio", "vcc", "comms", "legal", "risk", "it"}
    found = {d["dept_id"] for d in data["departments"]}
    assert expected.issubset(found)
    for did in expected:
        d = next(x for x in data["departments"] if x["dept_id"] == did)
        assert d["live"] is False, f"{did} should be live=false at Stage 10"
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/unit/test_departments_config.py::test_nine_future_depts_present_with_live_false -v`
Expected: FAIL.

- [ ] **Step 3: Edit `config/departments.json`**

For each existing entry (cac, hr) add: `capabilityTier`, `crossReadAccess`, `agentTopology`, `documents`, `heartbeat`. Set `live: true`.

For each of the 9 new depts (finance, ib, ic, cio, vcc, comms, legal, risk, it), add an entry with cross-read per spec §3.4, capability tier per §3.3, agentTopology per each dept skeleton spec §1, and `live: false`.

Reference: `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md` §3.3 for documents and §3.4 for crossReadAccess.

- [ ] **Step 4: Run all departments_config tests**

Run: `pytest tests/unit/test_departments_config.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add config/departments.json tests/unit/test_departments_config.py
git commit -m "feat(stage10): migrate departments.json with capabilityTier/crossReadAccess + add 9 future depts (live=false)"
```

### Task 1.3: Create `config/document_inventory.schema.json`

**Files:**
- Create: `config/document_inventory.schema.json`
- Test: `tests/unit/test_document_inventory.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_document_inventory.py
import json
from jsonschema import validate, ValidationError
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "config" / "document_inventory.schema.json").read_text())

def test_doc_row_requires_owner_dept():
    with pytest.raises(ValidationError):
        validate({"id": "doc_x", "title": "X"}, SCHEMA)

def test_doc_row_tier_enum():
    with pytest.raises(ValidationError):
        validate({"id": "doc_x", "title": "X", "ownerDept": "x", "tier": "bogus",
                  "vaultPath": "x", "qdrantCollection": "x_docs"}, SCHEMA)

def test_doc_row_full_valid():
    validate({
        "id": "doc_finance_annual_report",
        "title": "Annual report",
        "ownerDept": "finance",
        "tier": "report",
        "vaultPath": "obsidian-vault/finance/entities/annual-report.md",
        "qdrantCollection": "finance_docs",
        "ingestSource": "sharepoint://Finance/Annual",
        "frequency": "annual",
        "crossReadAccess": ["ceo", "cac"]
    }, SCHEMA)
```

- [ ] **Step 2: Run, expect missing-file error**

Run: `pytest tests/unit/test_document_inventory.py -v`
Expected: FAIL — schema file missing.

- [ ] **Step 3: Create schema**

```json
// config/document_inventory.schema.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "title", "ownerDept", "tier", "vaultPath", "qdrantCollection"],
  "properties": {
    "id":               { "type": "string", "pattern": "^doc_[a-z0-9_]+$" },
    "title":            { "type": "string" },
    "ownerDept":        { "type": "string" },
    "tier":             { "enum": ["policy", "report", "tracker", "narrative"] },
    "vaultPath":        { "type": "string" },
    "qdrantCollection": { "type": "string", "pattern": "^[a-z0-9_]+$" },
    "ingestSource":     { "type": "string" },
    "frequency":        { "type": "string" },
    "crossReadAccess":  { "type": "array", "items": { "type": "string" } }
  }
}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/unit/test_document_inventory.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add config/document_inventory.schema.json tests/unit/test_document_inventory.py
git commit -m "feat(stage10): add document_inventory.schema.json"
```

### Task 1.4: Populate `config/document_inventory.json`

**Files:**
- Create: `config/document_inventory.json`
- Test: `tests/unit/test_document_inventory.py` (extend)

- [ ] **Step 1: Write completeness tests**

```python
# Append to tests/unit/test_document_inventory.py
def test_inventory_loads_and_validates():
    data = json.loads((ROOT / "config" / "document_inventory.json").read_text())
    for row in data["documents"]:
        validate(row, SCHEMA)

def test_inventory_has_all_owner_depts():
    data = json.loads((ROOT / "config" / "document_inventory.json").read_text())
    owners = {d["ownerDept"] for d in data["documents"]}
    expected = {"ceo", "finance", "ib", "hr", "ic", "cac", "cio", "legal", "risk", "vcc", "comms", "it"}
    assert owners == expected, f"missing: {expected - owners}, extra: {owners - expected}"

def test_inventory_qdrant_collections_match_owner():
    data = json.loads((ROOT / "config" / "document_inventory.json").read_text())
    for row in data["documents"]:
        assert row["qdrantCollection"].startswith(row["ownerDept"]), f"{row['id']}: collection mismatch"

def test_inventory_total_count_in_expected_range():
    data = json.loads((ROOT / "config" / "document_inventory.json").read_text())
    assert 50 <= len(data["documents"]) <= 60, "spec says ~53 rows"
```

- [ ] **Step 2: Create `config/document_inventory.json`**

Reference framework spec §3.3 table for the per-dept document list. Each row uses the schema from §3.2. Slugs follow `doc_{dept}_{snake_case}` pattern.

Sample shape (CEO + Finance + Comms shown; full 53 rows for all 12 depts):

```json
{
  "documents": [
    { "id": "doc_ceo_strategic_retreat", "title": "Strategic Retreat Plan", "ownerDept": "ceo",
      "tier": "narrative", "vaultPath": "obsidian-vault/ceo/entities/strategic-retreat.md",
      "qdrantCollection": "ceo_docs", "frequency": "annual", "crossReadAccess": ["legal"] },
    { "id": "doc_ceo_leadership_monthly", "title": "Leadership monthly report", "ownerDept": "ceo",
      "tier": "report", "vaultPath": "obsidian-vault/ceo/entities/leadership-monthly.md",
      "qdrantCollection": "ceo_docs", "frequency": "monthly", "crossReadAccess": [] },
    // … remaining ~51 rows per spec §3.3
  ]
}
```

Use the exact dept counts from spec §3.3: 7 (CEO), 5 (Finance), 7 (IB), 3 (HR), 3 (IC), 4 (CAC), 3 (CIO), 3 (Legal), 1 (Risk), 8 (VCC), 7 (Comms), 2 (IT) = 53 rows.

- [ ] **Step 3: Run tests, verify pass**

Run: `pytest tests/unit/test_document_inventory.py -v`
Expected: all 6 PASS.

- [ ] **Step 4: Commit**

```bash
git add config/document_inventory.json tests/unit/test_document_inventory.py
git commit -m "feat(stage10): populate document_inventory.json with 53 corporate docs across 12 depts"
```

### Task 1.5: Migration 010 — schema additions

**Files:**
- Create: `migrations/010_phase2_framework.sql`
- Test: `tests/integration/test_migration_010.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/integration/test_migration_010.py
import asyncpg, pytest, os

@pytest.mark.asyncio
async def test_agent_knowledge_gaps_table_exists():
    conn = await asyncpg.connect(os.environ["POSTGRES_DSN"])
    cols = await conn.fetch("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='agent_knowledge_gaps' ORDER BY ordinal_position
    """)
    names = {c['column_name'] for c in cols}
    assert names >= {"id", "dept_id", "agent_id", "query", "hit_count",
                     "llm_self_report", "expected_doc_type", "resolved_at",
                     "resolved_by", "created_at"}
    await conn.close()

@pytest.mark.asyncio
async def test_agent_skill_proposals_table_exists():
    conn = await asyncpg.connect(os.environ["POSTGRES_DSN"])
    cols = await conn.fetch("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='agent_skill_proposals'
    """)
    names = {c['column_name'] for c in cols}
    assert names >= {"id", "dept_id", "agent_id", "skill_path", "trigger",
                     "evidence", "status", "proposed_diff", "hod_decision_at", "created_at"}
    await conn.close()

@pytest.mark.asyncio
async def test_reflection_runs_table_exists():
    conn = await asyncpg.connect(os.environ["POSTGRES_DSN"])
    cols = await conn.fetch("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='reflection_runs'
    """)
    assert {c['column_name'] for c in cols} >= {"id", "dept_id", "started_at", "completed_at", "status", "error"}
    await conn.close()

@pytest.mark.asyncio
async def test_agent_performance_view_returns_correct_signal_strength():
    """Insert synthetic approve/edit/reject rows, verify computed signal_strength."""
    conn = await asyncpg.connect(os.environ["POSTGRES_DSN"])
    # ... fixture rows ...
    rows = await conn.fetch("SELECT * FROM agent_performance ORDER BY proposal_id")
    assert rows[0]['signal_strength'] == 1.0  # approved
    assert rows[1]['signal_strength'] == 0.0  # rejected
    assert 0.5 <= rows[2]['signal_strength'] <= 1.0  # edited (proximity-based)
    await conn.close()
```

- [ ] **Step 2: Create migration file**

```sql
-- migrations/010_phase2_framework.sql

CREATE TABLE IF NOT EXISTS agent_knowledge_gaps (
  id              BIGSERIAL PRIMARY KEY,
  dept_id         TEXT NOT NULL,
  agent_id        TEXT NOT NULL,
  query           TEXT NOT NULL,
  hit_count       INT NOT NULL,
  llm_self_report TEXT,
  expected_doc_type TEXT,
  resolved_at     TIMESTAMPTZ,
  resolved_by     TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_knowledge_gaps_dept_unresolved
  ON agent_knowledge_gaps(dept_id) WHERE resolved_at IS NULL;

CREATE TABLE IF NOT EXISTS agent_skill_proposals (
  id              BIGSERIAL PRIMARY KEY,
  dept_id         TEXT NOT NULL,
  agent_id        TEXT NOT NULL,
  skill_path      TEXT NOT NULL,
  trigger         TEXT NOT NULL,
  evidence        JSONB NOT NULL,
  status          TEXT DEFAULT 'pending',
  proposed_diff   TEXT,
  hod_decision_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_skill_proposals_status ON agent_skill_proposals(status);

CREATE TABLE IF NOT EXISTS reflection_runs (
  id           BIGSERIAL PRIMARY KEY,
  dept_id      TEXT NOT NULL,
  started_at   TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  status       TEXT NOT NULL,           -- running | success | failed
  error        TEXT,
  stats        JSONB                    -- counts of promoted facts, lessons, proposals
);
CREATE INDEX IF NOT EXISTS idx_reflection_runs_dept_started ON reflection_runs(dept_id, started_at DESC);

CREATE OR REPLACE VIEW agent_performance AS
SELECT
  ai.dept_id,
  ai.agent_id,
  sp.id AS proposal_id,
  ad.action,
  CASE ad.action
    WHEN 'approved' THEN 1.0
    WHEN 'edited' THEN
      0.5 + 0.5 * (1.0 - LEAST(1.0,
        ABS(sp.proposed_value::numeric - ad.edited_value::numeric)
        / NULLIF(GREATEST(ABS(sp.proposed_value::numeric), 1), 0)
      ))
    WHEN 'rejected' THEN 0.0
  END AS signal_strength,
  ad.rejection_reason,
  ad.edited_value,
  ad.created_at
FROM approval_decisions ad
JOIN staging_proposals  sp ON sp.id = ad.proposal_id
JOIN agent_interactions ai ON ai.id = sp.interaction_id;
```

- [ ] **Step 3: Run migration**

```bash
python scripts/run_migrations.py --target 010
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_migration_010.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add migrations/010_phase2_framework.sql tests/integration/test_migration_010.py
git commit -m "feat(stage10): migration 010 — knowledge gaps, skill proposals, reflection runs, agent_performance view"
```

### Task 1.6: Build `scripts/validate_config.py`

**Files:**
- Create: `scripts/validate_config.py`
- Test: `tests/unit/test_validate_config_script.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_validate_config_script.py
import subprocess, json, tempfile, os
from pathlib import Path

def test_validate_config_passes_on_real_config():
    result = subprocess.run(["python", "scripts/validate_config.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"stderr: {result.stderr}"

def test_validate_config_fails_on_broken_dept(tmp_path, monkeypatch):
    bad = tmp_path / "departments.json"
    bad.write_text(json.dumps({"departments": [{"dept_id": "broken"}]}))  # missing required fields
    result = subprocess.run(
        ["python", "scripts/validate_config.py", "--departments", str(bad)],
        capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "capabilityTier" in result.stderr or "capabilityTier" in result.stdout

def test_validate_config_catches_inventory_owner_mismatch(tmp_path):
    bad = tmp_path / "inv.json"
    bad.write_text(json.dumps({"documents": [
        {"id": "doc_finance_x", "title": "X", "ownerDept": "finance",
         "tier": "report", "vaultPath": "x", "qdrantCollection": "wrong_docs"}  # mismatch!
    ]}))
    result = subprocess.run(
        ["python", "scripts/validate_config.py", "--inventory", str(bad)],
        capture_output=True, text=True
    )
    assert result.returncode != 0
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/unit/test_validate_config_script.py -v`
Expected: FAIL — script doesn't exist.

- [ ] **Step 3: Create script**

```python
#!/usr/bin/env python3
"""Validate config/departments.json + config/document_inventory.json against schemas + cross-references."""
import argparse, json, sys
from pathlib import Path
from jsonschema import validate, ValidationError

ROOT = Path(__file__).resolve().parents[1]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--departments", default=str(ROOT / "config" / "departments.json"))
    ap.add_argument("--departments-schema", default=str(ROOT / "config" / "departments.schema.json"))
    ap.add_argument("--inventory", default=str(ROOT / "config" / "document_inventory.json"))
    ap.add_argument("--inventory-schema", default=str(ROOT / "config" / "document_inventory.schema.json"))
    args = ap.parse_args()

    errors = []

    dept_schema = json.loads(Path(args.departments_schema).read_text())
    depts = json.loads(Path(args.departments).read_text())["departments"]
    for d in depts:
        try:
            validate(d, dept_schema)
        except ValidationError as e:
            errors.append(f"dept {d.get('dept_id', '?')}: {e.message}")

    inv_schema = json.loads(Path(args.inventory_schema).read_text())
    inv = json.loads(Path(args.inventory).read_text())["documents"]
    dept_ids = {d["dept_id"] for d in depts}
    for row in inv:
        try:
            validate(row, inv_schema)
        except ValidationError as e:
            errors.append(f"doc {row.get('id', '?')}: {e.message}")
            continue
        if row["ownerDept"] not in dept_ids:
            errors.append(f"doc {row['id']}: ownerDept '{row['ownerDept']}' not in departments.json")
        if not row["qdrantCollection"].startswith(row["ownerDept"]):
            errors.append(f"doc {row['id']}: collection '{row['qdrantCollection']}' "
                          f"should start with ownerDept '{row['ownerDept']}'")

    for d in depts:
        for cra in d.get("crossReadAccess", []):
            if cra not in dept_ids and cra != "*":
                errors.append(f"dept {d['dept_id']}: crossReadAccess '{cra}' not a known dept")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"OK — {len(depts)} depts, {len(inv)} docs validated")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/unit/test_validate_config_script.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_config.py tests/unit/test_validate_config_script.py
git commit -m "feat(stage10): scripts/validate_config.py — schema + cross-ref validation"
```

### Task 1.7: Build `scripts/validate_skills.py`

**Files:**
- Create: `scripts/validate_skills.py`
- Test: `tests/unit/test_validate_skills_script.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_validate_skills_script.py
import subprocess

def test_validate_skills_passes_on_real_skills():
    result = subprocess.run(["python", "scripts/validate_skills.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"stderr: {result.stderr}"

def test_validate_skills_catches_unknown_collection(tmp_path):
    skill = tmp_path / "bad.md"
    skill.write_text("""---
name: bad
agent: bad-agent
dept: cac
permissions:
  mode: read_only
  data_zones: [1]
  outbound_apis: []
  read_collections: [imaginary_collection]
---
""")
    result = subprocess.run(
        ["python", "scripts/validate_skills.py", "--skill-dir", str(tmp_path)],
        capture_output=True, text=True
    )
    assert result.returncode != 0
```

- [ ] **Step 2: Create script**

```python
#!/usr/bin/env python3
"""Validate SKILL.md frontmatter (permissions, output_types) and cross-refs."""
import argparse, json, sys, re
from pathlib import Path
import yaml  # PyYAML

ROOT = Path(__file__).resolve().parents[1]
KNOWN_MODES = {"read_only", "write_via_staging", "write_direct"}
KNOWN_OUTPUT_TYPES = {"text", "table", "checklist", "decision_tree", "calculation"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-dir", default=str(ROOT / "skills"))
    ap.add_argument("--inventory", default=str(ROOT / "config" / "document_inventory.json"))
    args = ap.parse_args()

    inv = json.loads(Path(args.inventory).read_text())["documents"]
    known_collections = {d["qdrantCollection"] for d in inv} | {"shared_policies"}

    errors = []
    skill_dir = Path(args.skill_dir)
    for f in skill_dir.rglob("*.md"):
        if f.name.startswith("_") or "history" in f.parts:
            continue
        text = f.read_text()
        m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not m:
            continue  # not a skill file
        try:
            fm = yaml.safe_load(m.group(1))
        except yaml.YAMLError as e:
            errors.append(f"{f}: yaml parse error: {e}")
            continue
        perms = fm.get("permissions", {})
        if perms.get("mode") not in KNOWN_MODES:
            errors.append(f"{f}: permissions.mode '{perms.get('mode')}' invalid")
        for col in perms.get("read_collections", []):
            if col not in known_collections:
                errors.append(f"{f}: read_collections '{col}' not in inventory")
        for ot in fm.get("output_types", ["text"]):
            if ot not in KNOWN_OUTPUT_TYPES:
                errors.append(f"{f}: output_types '{ot}' unknown")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"OK — skill frontmatter valid")

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run tests, verify pass**

Run: `pytest tests/unit/test_validate_skills_script.py -v`
Expected: PASS (note: real skills test may fail until Phase 2 frontmatter rollout — mark `xfail` until Task 2.5).

- [ ] **Step 4: Commit**

```bash
git add scripts/validate_skills.py tests/unit/test_validate_skills_script.py
git commit -m "feat(stage10): scripts/validate_skills.py — frontmatter + collection cross-refs"
```

### Task 1.8: Phase 1 commit + regression check

- [ ] **Step 1: Run full test suite**

Run: `pytest --tb=short`
Expected: all baseline tests still pass + new Phase 1 tests pass.

- [ ] **Step 2: Diff against baseline**

```bash
diff tests/baselines/stage9-regression-baseline.txt <(pytest --tb=no -q 2>&1) || echo "regressions detected — review"
```

- [ ] **Step 3: Tag phase 1 complete**

```bash
git tag stage10-phase1-complete
```

---

## Phase 2 — Skills Folder Cleanup + Frontmatter Extension

### Task 2.1: Rename `skills/invest/` → `skills/ic/`

**Files:**
- Move: `skills/invest/*` → `skills/ic/*`
- Test: `tests/integration/test_invest_to_ic_rename.py`

- [ ] **Step 1: Verify nothing imports `skills/invest/*`**

```bash
grep -rn "skills/invest" services/ scripts/ config/ tests/ || echo "no consumers"
```

Expected: `no consumers`. If any matches found, document and fix in this task.

- [ ] **Step 2: Write the rename safety test**

```python
# tests/integration/test_invest_to_ic_rename.py
import os, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_skills_ic_dir_exists():
    assert (ROOT / "skills" / "ic").is_dir()

def test_skills_invest_dir_gone():
    assert not (ROOT / "skills" / "invest").exists()

def test_renamed_files_present():
    for name in ["ic-orchestrator.md", "due-diligence.md", "portfolio.md", "valuation.md"]:
        assert (ROOT / "skills" / "ic" / name).is_file(), f"missing {name}"

def test_no_remaining_skills_invest_references():
    res = subprocess.run(
        ["grep", "-rn", "--include=*.py", "--include=*.json", "--include=*.md",
         "skills/invest", str(ROOT)],
        capture_output=True, text=True
    )
    # Allow only this test file to mention "skills/invest"
    bad = [l for l in res.stdout.splitlines() if "test_invest_to_ic_rename.py" not in l]
    assert not bad, f"residual references: {bad}"
```

- [ ] **Step 3: Run, expect failure**

Run: `pytest tests/integration/test_invest_to_ic_rename.py -v`
Expected: FAIL.

- [ ] **Step 4: Rename**

```bash
git mv skills/invest skills/ic
```

- [ ] **Step 5: Run tests, verify pass + regression check**

```bash
pytest tests/integration/test_invest_to_ic_rename.py -v
pytest --tb=short  # full regression
```

- [ ] **Step 6: Commit**

```bash
git commit -m "refactor(stage10): rename skills/invest → skills/ic to match dept_id convention"
```

### Task 2.2: Delete `skills/ops/`

**Files:**
- Delete: `skills/ops/`

- [ ] **Step 1: Verify nothing imports**

```bash
grep -rn "skills/ops" services/ scripts/ config/ tests/ || echo "no consumers"
```

- [ ] **Step 2: Delete + commit**

```bash
git rm -r skills/ops
git commit -m "refactor(stage10): delete skills/ops — not in org chart"
```

### Task 2.3: Move `skills/shared/cfo-agent.md` → `skills/finance/cfo-agent.md`

**Files:**
- Create: `skills/finance/` directory
- Move: `skills/shared/cfo-agent.md` → `skills/finance/cfo-agent.md`
- Create: `skills/shared/cfo-agent.md` (re-export stub)

- [ ] **Step 1: Move file**

```bash
mkdir -p skills/finance
git mv skills/shared/cfo-agent.md skills/finance/cfo-agent.md
```

- [ ] **Step 2: Create stub for backwards compat**

```markdown
<!-- skills/shared/cfo-agent.md -->
---
name: cfo-agent
agent: cfo-agent
dept: shared
deprecated: true
canonical: skills/finance/cfo-agent.md
---

# DEPRECATED — moved to `skills/finance/cfo-agent.md`

This stub exists for one stage as backwards compatibility while consumers migrate. SkillsLoader will resolve `cfo-agent` to the canonical path.
```

- [ ] **Step 3: Update SkillsLoader to resolve canonical paths**

In `services/shared/skills_loader.py`, add canonical resolution: if frontmatter contains `deprecated: true` and `canonical: <path>`, load the canonical file instead and emit a `logger.info("loaded {agent} via deprecation stub")`.

- [ ] **Step 4: Run regression**

```bash
pytest --tb=short -k "cac or skills_loader"
```

Expected: PASS — CAC orchestrator still loads the CFO Agent skill.

- [ ] **Step 5: Commit**

```bash
git add skills/shared/cfo-agent.md skills/finance/ services/shared/skills_loader.py
git commit -m "refactor(stage10): move cfo-agent skill from shared/ to finance/ with backcompat stub"
```

### Task 2.4: Extend Skill Pydantic model

**Files:**
- Modify: `services/shared/models.py` (or wherever the Skill pydantic model lives — verify with `grep -rn "class Skill" services/shared/`)
- Test: `services/shared/tests/unit/test_skill_model.py`

- [ ] **Step 1: Write failing test**

```python
# services/shared/tests/unit/test_skill_model.py
from services.shared.models import Skill, SkillPermissions

def test_skill_with_permissions_block():
    s = Skill(
        name="x", agent="x-agent", dept="x",
        permissions=SkillPermissions(
            mode="read_only", data_zones=[1], outbound_apis=[],
            read_collections=["x_docs"]
        ),
        output_types=["text", "table"]
    )
    assert s.permissions.mode == "read_only"

def test_skill_invalid_mode_rejected():
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        Skill(name="x", agent="x", dept="x",
              permissions=SkillPermissions(mode="bogus", data_zones=[],
                                           outbound_apis=[], read_collections=[]),
              output_types=["text"])

def test_skill_default_output_types_is_text_only():
    s = Skill(name="x", agent="x-agent", dept="x",
              permissions=SkillPermissions(mode="read_only", data_zones=[1],
                                           outbound_apis=[], read_collections=["x_docs"]))
    assert s.output_types == ["text"]
```

- [ ] **Step 2: Extend model**

```python
# services/shared/models.py (add)
from typing import List, Literal
from pydantic import BaseModel, Field

class SkillPermissions(BaseModel):
    mode: Literal["read_only", "write_via_staging", "write_direct"]
    data_zones: List[int]
    outbound_apis: List[Literal["gmail", "slack", "sharepoint"]] = Field(default_factory=list)
    read_collections: List[str]

class Skill(BaseModel):
    name: str
    agent: str
    dept: str
    version: str = "1.0"
    permissions: SkillPermissions
    output_types: List[Literal["text", "table", "checklist", "decision_tree", "calculation"]] = ["text"]
    deprecated: bool = False
    canonical: str | None = None
```

- [ ] **Step 3: Run tests**

Run: `pytest services/shared/tests/unit/test_skill_model.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add services/shared/models.py services/shared/tests/unit/test_skill_model.py
git commit -m "feat(stage10): extend Skill pydantic model with permissions + output_types"
```

### Task 2.5: Update CAC SKILL.md frontmatter

**Files:**
- Modify: `skills/cac/liquidity-analysis.md`, `capital-allocation.md`, `alm-review.md`, `funding-facilities.md`, `covenant-monitoring.md`
- Modify: `skills/finance/cfo-agent.md` (formerly shared/)

- [ ] **Step 1: Update each CAC skill's frontmatter**

For each file, replace the existing frontmatter with the extended schema. Example for liquidity-analysis:

```yaml
---
name: liquidity-analysis
agent: liquidity-agent
dept: cac
version: 1.0
permissions:
  mode: write_via_staging
  data_zones: [1, 2]
  outbound_apis: []
  read_collections: [cac_docs, cac_chat, cac_knowledge, shared_policies, finance_docs, risk_docs, cio_docs]
output_types: [text, table, calculation]
---
```

Per spec §3.4, CAC's crossReadAccess includes `[finance, risk, cio, ceo]` — `read_collections` reflects this (note: `_docs` only; `_chat` and `_knowledge` are dept-private).

- [ ] **Step 2: Update CFO Agent skill (skills/finance/cfo-agent.md)**

```yaml
---
name: cfo-agent
agent: cfo-agent
dept: finance
version: 1.0
permissions:
  mode: write_via_staging
  data_zones: [1, 2]
  outbound_apis: []
  read_collections: [finance_docs, finance_chat, finance_knowledge, shared_policies]
output_types: [text, table, calculation]
---
```

- [ ] **Step 3: Run validation**

```bash
python scripts/validate_skills.py
pytest --tb=short -k "cac"
```

Expected: validation OK; CAC tests still pass.

- [ ] **Step 4: Commit**

```bash
git add skills/cac/ skills/finance/cfo-agent.md
git commit -m "feat(stage10): extend CAC + CFO skill frontmatter with permissions + output_types"
```

### Task 2.6: Update HR SKILL.md frontmatter

**Files:**
- Modify: `skills/hr/hr-orchestrator.md`, `policy.md`, `compensation.md`, `talent.md`

Same pattern as Task 2.5 but with HR's posture: `mode: read_only`, `read_collections: [hr_docs, hr_chat, hr_knowledge, shared_policies]`.

- [ ] **Step 1: Update each file**
- [ ] **Step 2: Validate + regression**
- [ ] **Step 3: Commit**

```bash
git commit -m "feat(stage10): extend HR skill frontmatter with permissions (read-only)"
```

### Task 2.7: Update IC/IT/Legal/Risk scaffold frontmatter

**Files:**
- Modify: `skills/ic/*.md`, `skills/it/*.md`, `skills/legal/*.md`, `skills/risk/*.md`

For each scaffold dept, set frontmatter per their dept skeleton spec §6 default permissions. All four are read-only depts.

- [ ] **Step 1: Update each (16 files)**
- [ ] **Step 2: Validate**
- [ ] **Step 3: Commit**

```bash
git commit -m "feat(stage10): extend IC/IT/Legal/Risk scaffold skill frontmatter"
```

### Task 2.8: Phase 2 commit + regression

- [ ] **Step 1: Full regression**

```bash
pytest --tb=short
python scripts/validate_skills.py
python scripts/validate_config.py
```

- [ ] **Step 2: Tag**

```bash
git tag stage10-phase2-complete
```

---

## Phase 3 — Shared Library Updates

### Task 3.1: Add `load_memory` node helper to BaseAgent

**Files:**
- Modify: `services/shared/base_agent.py`
- Test: `services/shared/tests/unit/test_load_memory.py`

- [ ] **Step 1: Write failing test**

```python
# services/shared/tests/unit/test_load_memory.py
from services.shared.base_agent import load_memory_node

def test_load_memory_reads_three_files(tmp_path):
    mem_dir = tmp_path / "_memory" / "test-agent"
    mem_dir.mkdir(parents=True)
    (mem_dir / "soul.md").write_text("# Soul\nPersonality.")
    (mem_dir / "user.md").write_text("# User\nFacts.")
    (mem_dir / "memory.md").write_text("# Memory\nLessons.")
    state = {"agent_id": "test-agent", "vault_root": str(tmp_path)}
    result = load_memory_node(state)
    assert "Personality" in result["agent_memory"]
    assert "Facts" in result["agent_memory"]
    assert "Lessons" in result["agent_memory"]

def test_load_memory_handles_missing_files(tmp_path):
    """Missing files should not crash — return empty sections."""
    state = {"agent_id": "missing-agent", "vault_root": str(tmp_path)}
    result = load_memory_node(state)
    assert "agent_memory" in result
    assert result["agent_memory"] == ""  # all three missing
```

- [ ] **Step 2: Implement**

```python
# services/shared/base_agent.py (add)
from pathlib import Path

def load_memory_node(state: dict) -> dict:
    """LangGraph node: read soul.md/user.md/memory.md for the active agent.
    Concatenates non-empty files into state['agent_memory']. Missing files are silently skipped.
    """
    vault_root = Path(state.get("vault_root", "/vault"))
    dept = state.get("dept_id", "unknown")
    agent = state.get("agent_id", "unknown")
    base = vault_root / dept / "_memory" / agent
    parts = []
    for fname in ("soul.md", "user.md", "memory.md"):
        f = base / fname
        if f.is_file():
            content = f.read_text().strip()
            if content:
                parts.append(content)
    return {"agent_memory": "\n\n---\n\n".join(parts)}
```

- [ ] **Step 3: Test pass**

Run: `pytest services/shared/tests/unit/test_load_memory.py -v`

- [ ] **Step 4: Commit**

```bash
git add services/shared/base_agent.py services/shared/tests/unit/test_load_memory.py
git commit -m "feat(stage10): add load_memory LangGraph node helper to BaseAgent"
```

### Task 3.2: Add `crossReadAccess` support to retrieve_context

**Files:**
- Modify: `services/shared/retrieve_context.py` (verify path with grep)
- Test: `tests/integration/test_cross_dept_read.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/integration/test_cross_dept_read.py
import pytest
import asyncio

@pytest.mark.asyncio
async def test_cac_reads_finance_docs(qdrant_with_finance_docs, cac_dept_config):
    """CAC's crossReadAccess includes finance — must retrieve from finance_docs."""
    from services.shared.retrieve_context import retrieve_context_with_crossread
    hits = await retrieve_context_with_crossread(
        query="latest networth",
        dept_config=cac_dept_config
    )
    sources = {h.collection for h in hits}
    assert "finance_docs" in sources, "CAC should retrieve finance docs via crossRead"

@pytest.mark.asyncio
async def test_hr_does_not_read_finance_docs(qdrant_with_finance_docs, hr_dept_config):
    """HR's crossReadAccess is empty — finance_docs MUST NOT appear."""
    from services.shared.retrieve_context import retrieve_context_with_crossread
    hits = await retrieve_context_with_crossread(
        query="latest networth",
        dept_config=hr_dept_config
    )
    sources = {h.collection for h in hits}
    assert "finance_docs" not in sources, "HR cross-read leak — finance_docs returned"

@pytest.mark.asyncio
async def test_graceful_degrade_missing_collection(qdrant_no_finance, cac_dept_config):
    """If finance_docs collection doesn't exist, retrieval still succeeds with available collections."""
    from services.shared.retrieve_context import retrieve_context_with_crossread
    hits = await retrieve_context_with_crossread(
        query="liquidity",
        dept_config=cac_dept_config
    )
    # Should return hits from cac_docs etc, not raise
    assert isinstance(hits, list)
```

- [ ] **Step 2: Implement**

```python
# services/shared/retrieve_context.py (extend or wrap existing)
import logging
log = logging.getLogger(__name__)

async def retrieve_context_with_crossread(query: str, dept_config: dict, qdrant_client=None, top_k=5):
    dept_id = dept_config["dept_id"]
    cross = dept_config.get("crossReadAccess", [])
    collections = (
        [f"{dept_id}_docs", f"{dept_id}_chat", f"{dept_id}_knowledge", "shared_policies"]
        + [f"{d}_docs" for d in cross if d != "*"]
    )
    if "*" in cross:
        # Resolve to all live depts (CEO + Legal pattern)
        all_depts = ...  # read from departments.json
        collections = list(set(collections + [f"{d}_docs" for d in all_depts]))
    weights = {c: (1.0 if c.startswith(dept_id) else 0.7 if c == "shared_policies" else 0.4)
               for c in collections}

    hits = []
    for c in collections:
        try:
            res = await qdrant_client.search(collection_name=c, query=query, top=top_k)
            for h in res:
                h.weight = weights.get(c, 0.4)
                hits.append(h)
        except Exception as e:
            # Graceful degrade — Qdrant raises if collection missing
            log.info("collection %s unavailable, skipping (%s)", c, type(e).__name__)
    hits.sort(key=lambda h: h.score * h.weight, reverse=True)
    return hits[:top_k]
```

- [ ] **Step 3: Update CAC + HR orchestrator retrieve nodes to use the new function**

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_cross_dept_read.py -v`

- [ ] **Step 5: Run regression vs golden master**

```bash
python scripts/diff_golden_master.py --orchestrator cac --baseline tests/baselines/cac-golden-fixtures/
python scripts/diff_golden_master.py --orchestrator hr --baseline tests/baselines/hr-golden-fixtures/
```

Expected: minimal drift (cross-read may add citations from shared_policies but core answers identical).

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(stage10): retrieve_context with crossReadAccess + graceful-degrade missing collections"
```

### Task 3.3: Knowledge-gap writer (retrieve)

**Files:**
- Modify: `services/shared/retrieve_context.py`
- Test: `services/cac-orchestrator/tests/unit/test_knowledge_gaps.py`

- [ ] **Step 1: Write test**

```python
@pytest.mark.asyncio
async def test_low_hit_count_writes_gap(db_conn, mock_qdrant_low_hits):
    from services.shared.retrieve_context import retrieve_context_with_crossread
    await retrieve_context_with_crossread(query="obscure topic", dept_config=...)
    rows = await db_conn.fetch("SELECT * FROM agent_knowledge_gaps WHERE query='obscure topic'")
    assert len(rows) == 1
    assert rows[0]["hit_count"] < 3

@pytest.mark.asyncio
async def test_normal_hit_count_no_gap(db_conn, mock_qdrant_full_hits):
    await retrieve_context_with_crossread(query="liquidity", dept_config=...)
    rows = await db_conn.fetch("SELECT * FROM agent_knowledge_gaps WHERE query='liquidity'")
    assert len(rows) == 0
```

- [ ] **Step 2: Add gap writer**

```python
# Inside retrieve_context_with_crossread, after combining hits:
if len(hits) < 3:
    await db_conn.execute(
        "INSERT INTO agent_knowledge_gaps (dept_id, agent_id, query, hit_count) VALUES ($1, $2, $3, $4)",
        dept_id, dept_config.get("active_agent", "unknown"), query, len(hits)
    )
```

- [ ] **Step 3: Test pass**
- [ ] **Step 4: Commit**

```bash
git commit -m "feat(stage10): write agent_knowledge_gaps row when retrieve hits < 3"
```

### Task 3.4: Knowledge-gap writer (synthesise — LLM phrase detection)

**Files:**
- Modify: `services/shared/synthesise.py` (verify path)
- Test: `services/cac-orchestrator/tests/unit/test_knowledge_gaps.py`

- [ ] **Step 1: Test**

```python
@pytest.mark.asyncio
async def test_llm_self_report_writes_gap(db_conn):
    from services.shared.synthesise import detect_self_report
    response = "I don't have data on the Q3 NSFR ratio for the European subsidiary."
    await detect_self_report(response, dept_id="cac", agent_id="liquidity-agent",
                             query="Q3 NSFR for EU sub", db_conn=db_conn)
    rows = await db_conn.fetch(
        "SELECT * FROM agent_knowledge_gaps WHERE query='Q3 NSFR for EU sub'"
    )
    assert len(rows) == 1
    assert rows[0]["llm_self_report"].startswith("I don't have data on")
```

- [ ] **Step 2: Implement**

```python
# services/shared/synthesise.py
import re

SELF_REPORT_PATTERNS = [
    r"don'?t have data on",
    r"unable to find",
    r"no information about",
    r"i couldn'?t find",
]

async def detect_self_report(response: str, dept_id: str, agent_id: str, query: str, db_conn):
    if any(re.search(p, response, re.IGNORECASE) for p in SELF_REPORT_PATTERNS):
        await db_conn.execute(
            """INSERT INTO agent_knowledge_gaps
               (dept_id, agent_id, query, hit_count, llm_self_report)
               VALUES ($1, $2, $3, $4, $5)""",
            dept_id, agent_id, query, 0, response[:500]
        )
```

- [ ] **Step 3: Wire into synthesise_response node**
- [ ] **Step 4: Test pass**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(stage10): detect LLM self-report phrases and write knowledge gap"
```

### Task 3.5: Daily-log writer in `log_interaction`

**Files:**
- Modify: `services/shared/base_agent.py` (or wherever log_interaction lives)
- Test: `services/shared/tests/unit/test_daily_log.py`

- [ ] **Step 1: Test**

```python
def test_daily_log_appends_entry(tmp_path):
    from services.shared.base_agent import log_interaction_node
    state = {
        "vault_root": str(tmp_path),
        "dept_id": "cac",
        "user_id": "U123",
        "query": "what's the LCR?",
        "response": "LCR is 118.50%",
        "citations": ["doc:liq.pdf:p3"],
        "confidence": 0.91,
        "proposal_id": "chg_4421",
    }
    log_interaction_node(state)
    log_file = tmp_path / "cac" / "daily-logs"
    files = list(log_file.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "what's the LCR?" in content
    assert "chg_4421" in content
```

- [ ] **Step 2: Implement**

```python
def log_interaction_node(state: dict) -> dict:
    from datetime import datetime
    vault = Path(state["vault_root"])
    dept = state["dept_id"]
    log_dir = vault / dept / "daily-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    f = log_dir / f"{today}.md"
    entry = f"""
## {datetime.utcnow().strftime("%H:%M")} · @{state.get('user_id', '?')} · proposal: {state.get('proposal_id', 'none')}
**Q:** {state['query']}
**A:** {state['response']}
**Citations:** {', '.join(state.get('citations', []))}
**Confidence:** {state.get('confidence', 0.0):.2f}
**Outcome:** pending
"""
    with f.open("a") as fp:
        fp.write(entry)
    return state
```

- [ ] **Step 3: Test pass**
- [ ] **Step 4: Commit**

```bash
git commit -m "feat(stage10): append every interaction to obsidian-vault/{dept}/daily-logs/YYYY-MM-DD.md"
```

### Task 3.6: Permission enforcement

**Files:**
- Modify: `services/shared/skills_loader.py`
- Modify: `services/shared/base_agent.py`
- Test: `services/shared/tests/unit/test_permission_enforcement.py`

- [ ] **Step 1: Tests**

```python
def test_read_only_skill_blocks_staging_writer():
    from services.shared.base_agent import ensure_can_write
    skill = Skill(..., permissions=SkillPermissions(mode="read_only", ...))
    with pytest.raises(PermissionError):
        ensure_can_write(skill, action="staging_proposal")

def test_skills_loader_rejects_unknown_collection():
    from services.shared.skills_loader import SkillsLoader
    loader = SkillsLoader(known_collections={"cac_docs"})
    bad_skill = "---\npermissions:\n  read_collections: [imaginary]\n---\n"
    with pytest.raises(ValueError):
        loader.parse(bad_skill)
```

- [ ] **Step 2: Implement enforcement**
- [ ] **Step 3: Update CAC orchestrator's staging_writer node to call `ensure_can_write`**
- [ ] **Step 4: Regression check**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(stage10): enforce read_only skills cannot reach staging_writer; reject unknown collections"
```

### Task 3.7: Update CAC orchestrator to use new shared

**Files:**
- Modify: `services/cac-orchestrator/src/graph.py`
- Test: golden-master regression

- [ ] **Step 1: Add `load_memory` as first node in CAC graph**
- [ ] **Step 2: Replace retrieve node with `retrieve_context_with_crossread`**
- [ ] **Step 3: Add `log_interaction` after synthesise**
- [ ] **Step 4: Run golden-master diff**

```bash
python scripts/diff_golden_master.py --orchestrator cac --baseline tests/baselines/cac-golden-fixtures/
```

Expected: ≤ minor citation drift; core answer text unchanged.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(stage10): wire CAC orchestrator with load_memory + crossread + daily-log nodes"
```

### Task 3.8: Update HR orchestrator

Mirror of Task 3.7 for HR. (Read-only — staging path remains absent.)

- [ ] **Step 1-5: as 3.7 but for HR**

### Task 3.9: Phase 3 commit + regression

```bash
pytest --tb=short
git tag stage10-phase3-complete
```

---

## Phase 4 — Reflection Engine Service

### Task 4.1: Scaffold service

**Files:**
- Create: `services/reflection-engine/Dockerfile`
- Create: `services/reflection-engine/requirements.txt`
- Create: `services/reflection-engine/src/main.py`
- Create: `services/reflection-engine/src/config.py`
- Create: `services/reflection-engine/tests/conftest.py`

- [ ] **Step 1: Create FastAPI skeleton**

```python
# services/reflection-engine/src/main.py
from fastapi import FastAPI
from .config import settings

app = FastAPI(title="reflection-engine", version="0.1.0")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "reflection-engine", "port": settings.PORT}
```

- [ ] **Step 2: Config**

```python
# services/reflection-engine/src/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PORT: int = 3008
    POSTGRES_DSN: str
    LLM_BASE_URL: str = "http://nginx:8080/v1"
    PAPERCLIP_URL: str = "http://paperclip:3100"
    VAULT_ROOT: str = "/vault"
    REFLECTION_CRON: str = "0 2 * * *"   # 02:00 daily

settings = Settings()
```

- [ ] **Step 3: Health smoke test**

```python
# services/reflection-engine/tests/unit/test_health.py
from fastapi.testclient import TestClient
from services.reflection_engine.src.main import app

def test_health():
    r = TestClient(app).get("/health")
    assert r.json()["service"] == "reflection-engine"
```

- [ ] **Step 4: Commit**

```bash
git add services/reflection-engine/
git commit -m "feat(stage10): scaffold reflection-engine service (port 3008)"
```

### Task 4.2: Daily log reader

**Files:**
- Create: `services/reflection-engine/src/log_reader.py`
- Test: `services/reflection-engine/tests/unit/test_log_reader.py`

- [ ] **Step 1: Test**

```python
def test_parses_daily_log_entries(tmp_path):
    f = tmp_path / "2026-04-27.md"
    f.write_text("""
## 14:23 · @U123 · proposal: chg_4421
**Q:** What's the LCR?
**A:** LCR is 118.50%
**Citations:** liq.pdf:p3
**Confidence:** 0.91
**Outcome:** approved

## 15:01 · @U456 · proposal: none
**Q:** Show me the NSFR
**A:** NSFR is 104.2%
**Citations:**
**Confidence:** 0.85
**Outcome:** pending
""")
    from services.reflection_engine.src.log_reader import parse_daily_log
    entries = parse_daily_log(f)
    assert len(entries) == 2
    assert entries[0].outcome == "approved"
    assert entries[0].proposal_id == "chg_4421"
```

- [ ] **Step 2: Implement**

```python
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

@dataclass
class LogEntry:
    timestamp: str
    user_id: str
    proposal_id: str | None
    query: str
    response: str
    citations: list[str]
    confidence: float
    outcome: str

def parse_daily_log(path: Path) -> List[LogEntry]:
    text = path.read_text()
    entries = []
    for block in re.split(r"\n## ", text):
        if not block.strip(): continue
        # parse with regex per the schema
        ...
    return entries
```

- [ ] **Step 3: Test pass**
- [ ] **Step 4: Commit**

### Task 4.3: approval_decisions joiner

**Files:**
- Create: `services/reflection-engine/src/decisions_joiner.py`
- Test: `services/reflection-engine/tests/unit/test_decisions_joiner.py`

- [ ] **Step 1: Test that joins entries with their approval decisions via proposal_id**
- [ ] **Step 2: Implement SQL: SELECT from agent_performance WHERE dept_id = ?**
- [ ] **Step 3: Commit**

### Task 4.4: Claude Agent SDK client

**Files:**
- Create: `services/reflection-engine/src/sdk_client.py`
- Test: `services/reflection-engine/tests/unit/test_sdk_client.py`

- [ ] **Step 1: Build Claude client with prompt template**

```python
REFLECTION_PROMPT = """
You are a reflection agent for the {dept_id} {agent_id} agent. Read yesterday's interactions
and decisions, then update the agent's memory.md and user.md.

Yesterday's daily log:
{daily_log}

Decisions on staging proposals:
{decisions}

Knowledge gaps identified:
{gaps}

Current memory.md:
{current_memory}

Current user.md:
{current_user}

Output a JSON object:
{{
  "memory_md_updates": [{{"section": "...", "content": "..."}}, ...],
  "user_md_updates": [{{"section": "...", "content": "..."}}, ...],
  "skill_proposals": [{{"skill_path": "...", "trigger": "...", "evidence": ...}}, ...]
}}

Only promote facts you are highly confident about. Be conservative.
"""
```

- [ ] **Step 2: Test JSON parse + retry on parse failure**
- [ ] **Step 3: Commit**

### Task 4.5: Memory promotion logic

**Files:**
- Create: `services/reflection-engine/src/promoter.py`
- Test: `services/reflection-engine/tests/unit/test_promoter.py`

- [ ] **Step 1: Test that promoter writes new memory.md, archives old**

```python
def test_promoter_archives_then_writes(tmp_path):
    mem_dir = tmp_path / "_memory" / "x-agent"
    mem_dir.mkdir(parents=True)
    (mem_dir / "memory.md").write_text("old content")
    from services.reflection_engine.src.promoter import promote
    promote(mem_dir, sdk_output={"memory_md_updates": [{"section": "Lessons", "content": "new"}], ...})
    assert (mem_dir / "memory.md").read_text() != "old content"
    archive_dir = mem_dir / "history"
    assert any(f.name.endswith("memory.md") for f in archive_dir.iterdir())
```

- [ ] **Step 2: Implement archive-then-write**
- [ ] **Step 3: Commit**

### Task 4.6: Pattern detection (skill_proposals trigger)

**Files:**
- Create: `services/reflection-engine/src/pattern_detector.py`
- Test: `services/reflection-engine/tests/integration/test_skill_proposals.py`

- [ ] **Step 1: Integration test from spec §8.1**

```python
@pytest.mark.asyncio
async def test_five_same_shape_low_signal_triggers_proposal(db_conn):
    # Insert 5 staging_proposals + decisions where signal_strength < 0.5 for same skill
    for i in range(5):
        await insert_synthetic_low_signal(db_conn, skill_path="skills/cac/liquidity-analysis.md")
    from services.reflection_engine.src.pattern_detector import detect
    proposals = await detect(db_conn, dept_id="cac")
    assert len(proposals) == 1
    assert proposals[0]["skill_path"] == "skills/cac/liquidity-analysis.md"

@pytest.mark.asyncio
async def test_four_same_shape_does_not_trigger(db_conn):
    for i in range(4):
        await insert_synthetic_low_signal(db_conn, skill_path="skills/cac/liquidity-analysis.md")
    from services.reflection_engine.src.pattern_detector import detect
    proposals = await detect(db_conn, dept_id="cac")
    assert len(proposals) == 0
```

- [ ] **Step 2: Implement detector**

```python
async def detect(db_conn, dept_id: str, threshold_count=5, signal_max=0.5):
    rows = await db_conn.fetch("""
        SELECT agent_id, skill_path,
               COUNT(*) AS n,
               AVG(signal_strength) AS avg_signal
        FROM agent_performance ap
        JOIN agent_interactions ai ON ai.id = ap.proposal_id
        WHERE ap.dept_id = $1 AND ap.created_at > NOW() - INTERVAL '7 days'
        GROUP BY agent_id, skill_path
        HAVING COUNT(*) >= $2 AND AVG(signal_strength) < $3
    """, dept_id, threshold_count, signal_max)
    proposals = []
    for r in rows:
        # Insert agent_skill_proposals row + return
        ...
    return proposals
```

- [ ] **Step 3: Tests pass**
- [ ] **Step 4: Commit**

### Task 4.7: APScheduler nightly cron

**Files:**
- Create: `services/reflection-engine/src/scheduler.py`
- Modify: `services/reflection-engine/src/main.py`

- [ ] **Step 1: Wire cron to invoke per-dept reflection at 02:00 daily**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

def start_scheduler():
    sched = AsyncIOScheduler()
    sched.add_job(run_reflection_for_all_live_depts, "cron", hour=2, minute=0)
    sched.start()
    return sched
```

- [ ] **Step 2: Test that schedule fires (mock time)**
- [ ] **Step 3: Commit**

### Task 4.8: /health + paperclip heartbeat

- [ ] **Step 1: Add heartbeat POST to paperclip every 60s**
- [ ] **Step 2: Test heartbeat round-trip with mock paperclip**
- [ ] **Step 3: Commit**

### Task 4.9: Integration test — dry-run on synthetic CAC data

**Files:**
- Create: `services/reflection-engine/tests/integration/test_engine.py`

- [ ] **Step 1: Build test that:**
  1. Creates synthetic CAC daily log (5 entries, mix of approved/edited/rejected)
  2. Inserts matching agent_interactions + staging_proposals + approval_decisions
  3. Calls `engine.run_dept(dept_id="cac")`
  4. Asserts: memory.md updated, history archive present, no skill_proposals (since 5 not in same skill)
  5. Asserts: reflection_runs row inserted with status=success

- [ ] **Step 2: Run, verify pass**
- [ ] **Step 3: Commit**

### Task 4.10: Docker compose entry

```yaml
reflection-engine:
  build: ./services/reflection-engine
  ports: ["3008:3008"]
  environment:
    POSTGRES_DSN: ${POSTGRES_DSN}
    LLM_BASE_URL: http://nginx:8080/v1
    PAPERCLIP_URL: http://paperclip:3100
    VAULT_ROOT: /vault
  volumes:
    - ./obsidian-vault:/vault:rw
  depends_on: [postgres, paperclip]
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3008/health"]
    interval: 30s
```

- [ ] **Step 1: Add to docker-compose.yml**
- [ ] **Step 2: `docker compose config` validates**
- [ ] **Step 3: `docker compose up -d reflection-engine` succeeds; health 200**
- [ ] **Step 4: Commit**

### Task 4.11: Phase 4 tag

```bash
git tag stage10-phase4-complete
```

---

## Phase 5 — Heartbeat Service (Default Disabled)

### Task 5.1: Scaffold

Same skeleton pattern as Task 4.1 but for `services/heartbeat/` on port 3009.

- [ ] **Step 1-3: scaffold + health + commit**

### Task 5.2: Per-dept config reader

**Files:**
- Create: `services/heartbeat/src/config_reader.py`

- [ ] **Step 1: Test reads departments.json, filters to `heartbeat.enabled == true`**
- [ ] **Step 2: Implement**
- [ ] **Step 3: Commit**

### Task 5.3: Context-gathering API client (Slack + SharePoint stubs)

- [ ] **Step 1: Build pluggable source client**
- [ ] **Step 2: Stubs for `slack:`, `sharepoint:` URI prefixes (real impl deferred per spec §4.8)**
- [ ] **Step 3: Test with stubs**
- [ ] **Step 4: Commit**

### Task 5.4: Orchestrator-invocation client

- [ ] **Step 1: HTTP POST to `{dept}-orchestrator:30XX/proactive` endpoint with assembled context**
- [ ] **Step 2: Tests with mock orchestrator**
- [ ] **Step 3: Commit**

### Task 5.5: APScheduler dispatcher

- [ ] **Step 1: Per-dept cron schedules built from `heartbeat.schedule` strings**
- [ ] **Step 2: Test all-disabled state — no jobs scheduled**
- [ ] **Step 3: Test enabled-but-no-action — context gathered, orchestrator returns null, no Slack post**
- [ ] **Step 4: Commit**

### Task 5.6: /health endpoint + paperclip heartbeat

- [ ] **Step 1-3: as 4.8**

### Task 5.7: Integration test — all-disabled

- [ ] **Step 1: Verify with HR + CAC heartbeat off, no jobs run, no errors**
- [ ] **Step 2: Commit**

### Task 5.8: Docker compose entry

```yaml
heartbeat:
  build: ./services/heartbeat
  ports: ["3009:3009"]
  environment:
    POSTGRES_DSN: ${POSTGRES_DSN}
    PAPERCLIP_URL: http://paperclip:3100
  depends_on: [postgres, paperclip]
  restart: unless-stopped
```

### Task 5.9: Phase 5 tag

```bash
git tag stage10-phase5-complete
```

---

## Phase 6 — Template Scaffolds

### Task 6.1: Create `services/_template-orchestrator/`

**Files:**
- Copy: `services/hr-orchestrator/` → `services/_template-orchestrator/`
- Modify: replace dept-specific identifiers with placeholders

- [ ] **Step 1: Copy HR scaffolding**

```bash
cp -r services/hr-orchestrator services/_template-orchestrator
```

- [ ] **Step 2: Replace placeholders**

In every Python file, JSON, and README inside `_template-orchestrator/`, replace:
- `hr` → `{DEPT_ID}`
- `HR` → `{DEPT_NAME}`
- `3002` → `{PORT}`
- agent class names → `{AGENT_CLASS}`
- collection names → `{COLLECTION}`

- [ ] **Step 3: Add a top-level `_template-orchestrator/README.md`**

```markdown
# Template Orchestrator

Copy this directory to bootstrap a new dept-orchestrator service. Use `service-scaffold` skill.

Placeholders:
- `{DEPT_ID}` — lowercase dept slug (e.g. `finance`)
- `{DEPT_NAME}` — human-readable name (e.g. `Finance`)
- `{PORT}` — service port (3010+)
- `{AGENT_CLASS}` — agent Python class names
- `{COLLECTION}` — Qdrant collection prefix
```

- [ ] **Step 4: Commit**

```bash
git add services/_template-orchestrator/
git commit -m "feat(stage10): create services/_template-orchestrator/ from HR copy with placeholders"
```

### Task 6.2: Create `skills/_template/`

**Files:**
- Create: `skills/_template/orchestrator.md`
- Create: `skills/_template/specialist-1.md`, `specialist-2.md`, `specialist-3.md`

- [ ] **Step 1: Author placeholder templates**

Each file has the standard frontmatter (with `{DEPT}`, `{AGENT}` placeholders) and section headers (Mandate, Tone & Style, Domain Knowledge, Retrieval, Staging Proposal Rules, Excel Navigation, Escalation, Output Format, Hard Rules per PRD §11).

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(stage10): create skills/_template/ with placeholder skill files"
```

### Task 6.3: Update `service-scaffold` skill

**Files:**
- Modify: `.claude/skills/service-scaffold/SKILL.md` (or wherever it lives — verify path)

- [ ] **Step 1: Add `--from-template <path> --dept-id <id> --port <port>` flow that copies + sed-replaces**
- [ ] **Step 2: Test with a dry-run dept ("xyz")**
- [ ] **Step 3: Commit**

### Task 6.4: Test scaffolding

**Files:**
- Test: `tests/integration/test_scaffold_template.py`

- [ ] **Step 1: Test creates `services/xyz-orchestrator/`, asserts files compile, runs the FastAPI test client, gets 200 from /health**
- [ ] **Step 2: Cleanup — `git checkout` to restore**
- [ ] **Step 3: Commit test**

### Task 6.5: Phase 6 tag

```bash
git tag stage10-phase6-complete
```

---

## Phase 7 — Approval-UI Extensions

### Task 7.1: Add Skill Updates tab

**Files:**
- Modify: `services/approval-ui/src/components/Navigation.tsx` (verify path)
- Create: `services/approval-ui/src/pages/skill-updates.tsx`

- [ ] **Step 1: Add tab to nav (visible to HOD + admin roles)**
- [ ] **Step 2: Stub page at `/skill-updates`**
- [ ] **Step 3: Vitest test for nav link**
- [ ] **Step 4: Commit**

### Task 7.2: Build SkillUpdatesPage with diff renderer

**Files:**
- Modify: `services/approval-ui/src/pages/skill-updates.tsx`
- Create: `services/approval-ui/src/components/SkillProposalCard.tsx`
- Create: `services/approval-ui/src/components/SkillDiffViewer.tsx`

- [ ] **Step 1: Fetch from `/api/skill-proposals?status=hod_review`**
- [ ] **Step 2: Render diff (unified-diff style) per proposal**
- [ ] **Step 3: Approve / Edit / Reject buttons → POST to gateway**
- [ ] **Step 4: Vitest tests**
- [ ] **Step 5: Commit**

### Task 7.3: Wire gateway endpoint

**Files:**
- Modify: `services/gateway/src/routes/skill_proposals.py`

- [ ] **Step 1: GET /api/skill-proposals (paginated, dept-scoped)**
- [ ] **Step 2: POST /api/skill-proposals/{id}/decision (approve/edit/reject)**
- [ ] **Step 3: On approve: emit Paperclip event → OpenClaw commits + auto-PR**
- [ ] **Step 4: Tests**
- [ ] **Step 5: Commit**

### Task 7.4: Build admin /admin/knowledge-gaps

**Files:**
- Create: `services/approval-ui/src/pages/admin/knowledge-gaps.tsx`
- Modify: `services/gateway/src/routes/admin.py`

- [ ] **Step 1: GET /api/admin/knowledge-gaps (sortable table: dept, agent, query, count, last_seen)**
- [ ] **Step 2: Page renders table with filters**
- [ ] **Step 3: Mark-as-resolved action → POST**
- [ ] **Step 4: Tests**
- [ ] **Step 5: Commit**

### Task 7.5: Vitest run + commit

```bash
cd services/approval-ui && npm test
```

### Task 7.6: Phase 7 tag

```bash
git tag stage10-phase7-complete
```

---

## Phase 8 — Final Wiring + Skeleton Plans

### Task 8.1: Create 9 vault folder skeletons

**Files:**
- Create: `obsidian-vault/{finance,ib,ic,cio,vcc,comms,legal,risk,it}/...`

- [ ] **Step 1: Bash loop creating subdirs**

```bash
for d in finance ib ic cio vcc comms legal risk it; do
  mkdir -p obsidian-vault/$d/{concepts,decisions,meeting-notes,entities,trends,daily-logs,_memory}
  # placeholder files so git tracks empty dirs
  for sub in concepts decisions meeting-notes entities trends daily-logs; do
    touch obsidian-vault/$d/$sub/.gitkeep
  done
  # _memory subdirs created per dept stage (need agent names from per-dept spec)
  touch obsidian-vault/$d/_memory/.gitkeep
done
```

- [ ] **Step 2: Commit**

```bash
git add obsidian-vault/
git commit -m "feat(stage10): scaffold 9 dept vault folders (finance, ib, ic, cio, vcc, comms, legal, risk, it)"
```

### Task 8.2: Update `obsidian_watch.json`

**Files:**
- Modify: `config/obsidian_watch.json`

- [ ] **Step 1: Add path → collection mapping for each new dept**

For each of the 9 depts: 7 mappings (concepts, decisions, meeting-notes, entities, trends, daily-logs, _memory) → collection. Daily-logs maps to `{dept}_chat`. Concepts/entities/trends → `{dept}_knowledge`. Decisions/meeting-notes → `{dept}_docs`. _memory → no Qdrant indexing (agent-private).

- [ ] **Step 2: Run validation**

```bash
python scripts/validate_config.py
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(stage10): map 9 dept vault paths to Qdrant collections in obsidian_watch.json"
```

### Task 8.3: Create 9 dept skeleton plans

**Files:**
- Create: `docs/superpowers/plans/_per-dept-plan-template.md`
- Create: `docs/superpowers/plans/2026-04-28-stage11-finance.md`
- ... through `2026-04-28-stage19-ib.md` (9 files total)

**Note:** The 9 dept skeleton **specs** already exist at `docs/superpowers/specs/2026-04-28-stage{11..19}-{dept}-design.md` — they were authored alongside the framework spec during the Stage 10 brainstorming session. This task creates the matching **plans**.

Each plan follows the same structure as this Stage 10 plan but with skeleton tasks referencing the framework's onboarding checklist (§5). The skeleton plans are short — they list the 12 onboarding steps as tasks and reference back to the framework spec for each step's detail.

- [ ] **Step 1: Author skeleton plan template `docs/superpowers/plans/_per-dept-plan-template.md`**

```markdown
# Stage {N} — {Dept Name} Department Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans

**Goal:** Stand up the {dept} department orchestrator with {N} agents per the dept skeleton spec.

**Spec:** `docs/superpowers/specs/YYYY-MM-DD-stage{N}-{dept}-design.md`

**Onboarding checklist:** Framework spec §5 (12 steps).

---

## Phase A — Catalog audit + spec finalization (Step 1-2)

- [ ] Run `python scripts/validate_config.py` — passes for {dept}
- [ ] Spec at `docs/superpowers/specs/YYYY-MM-DD-stage{N}-{dept}-design.md` is filled and reviewed

## Phase B — Scaffold (Step 3-4)

- [ ] Run scaffolding skill from `services/_template-orchestrator/`
- [ ] Copy `skills/_template/` to `skills/{dept}/`, fill content via skill-writer

## Phase C — Wiring (Step 5-6)

- [ ] Implement specialist agent classes, wire LangGraph
- [ ] Migration `migrations/0XX_add_{dept}_department.sql`

## Phase D — Tests (Step 7)

- [ ] All required tests per framework §5 Step 7

## Phase E — Deploy (Step 8-10)

- [ ] docker-compose entry
- [ ] Slack channel + bot routing
- [ ] Vault + memory bootstrap

## Phase F — Smoke + Go-live (Step 11-12)

- [ ] Six framework smoke tests pass
- [ ] Flip `live: true`, restart gateway, update Implementation.md, tag
```

- [ ] **Step 2: Generate 9 dept skeleton plans from template**

For each dept (finance, risk, legal, it, comms, ic, cio, vcc, ib), produce a plan file by copying the template and substituting `{N}`, `{dept}`, `{Dept Name}`. Reference the matching dept spec.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/_per-dept-plan-template.md docs/superpowers/plans/2026-04-28-stage*.md
git commit -m "feat(stage10): scaffold 9 dept skeleton plans + per-dept-plan-template"
```

### Task 8.4: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Bump Phase status section**

In CLAUDE.md, add to the Project Identity section: "**Phase 2 framework:** Stage 10 complete (2026-04-28). 9 dept stages scaffolded; awaiting per-dept rollout."

- [ ] **Step 2: Update Services table — add `reflection-engine` (3008) and `heartbeat` (3009)**
- [ ] **Step 3: Commit**

### Task 8.5: Update `Implementation.md`

**Files:**
- Modify: `docs/Implementation.md`

- [ ] **Step 1: Add Stage 10 entry**

```markdown
## Stage 10 — Phase 2 Framework Infrastructure ✅ (2026-04-28)

### 10A — Schema & Config
- [x] Extended `config/departments.schema.json` with capabilityTier, crossReadAccess, agentTopology, heartbeat
- [x] Migrated `config/departments.json` (CAC + HR + 9 future depts at live=false)
- [x] Created `config/document_inventory.json` (53 corporate documents)
- [x] Migration 010 — agent_knowledge_gaps, agent_skill_proposals, reflection_runs, agent_performance view
- [x] Validation scripts: `scripts/validate_config.py`, `validate_skills.py`

### 10B — Skills Cleanup + Frontmatter
- [x] Renamed `skills/invest/` → `skills/ic/`
- [x] Deleted `skills/ops/`
- [x] Moved `skills/shared/cfo-agent.md` → `skills/finance/cfo-agent.md` (with backcompat stub)
- [x] Extended SKILL.md frontmatter with permissions + output_types (CAC + HR + 4 scaffolds)

### 10C — Shared Library
- [x] load_memory node, retrieve_context_with_crossread, knowledge gap writers, daily-log writer

### 10D — Reflection Engine (port 3008)
- [x] Service scaffold + Claude Agent SDK integration
- [x] Memory promotion + skill_proposals pattern detection
- [x] APScheduler nightly cron

### 10E — Heartbeat (port 3009, default disabled)
- [x] Service scaffold + per-dept config reader

### 10F — Templates
- [x] services/_template-orchestrator/ + skills/_template/

### 10G — Approval-UI
- [x] Skill Updates tab + admin/knowledge-gaps view

### 10H — Vault folders + skeleton plans
- [x] 9 dept vault folder skeletons + obsidian_watch.json mappings
- [x] 9 dept skeleton plans + per-dept-plan-template

**Architecture:** Phase 2 framework lets each downstream dept stage land in ~1.5 days. Catalog (departments.json + document_inventory.json) + templates (services/_template-orchestrator + skills/_template) + shared services (reflection-engine + heartbeat) + per-skill permission registry + agent_performance signal-strength view from approval_decisions.
**Files:** ~80 new files | **Tests:** ~50 new
**Spec:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
**Plan:** `docs/superpowers/plans/2026-04-28-stage10-phase2-framework.md`
```

- [ ] **Step 2: Commit**

### Task 8.6: Run full regression + smoke

- [ ] **Step 1: Full pytest run**

```bash
pytest --tb=short
```

Expected: ≥ 441 tests pass (391 baseline + ~50 new).

- [ ] **Step 2: Validation scripts**

```bash
python scripts/validate_config.py && python scripts/validate_skills.py
```

- [ ] **Step 3: Docker stack health**

```bash
docker compose up -d
sleep 60
for port in 3000 3001 3002 3003 3004 3008 3009 3100 3200 4000; do
  curl -fsS http://localhost:$port/health || echo "FAIL: port $port"
done
```

Expected: all healthy.

- [ ] **Step 4: Golden-master diff (CAC + HR)**

```bash
python scripts/diff_golden_master.py --orchestrator cac --baseline tests/baselines/cac-golden-fixtures/
python scripts/diff_golden_master.py --orchestrator hr --baseline tests/baselines/hr-golden-fixtures/
```

Expected: ≤ minor citation drift; no answer regression.

### Task 8.7: Final commit + tag

- [ ] **Step 1: Final commit**

```bash
git add -A
git commit -m "feat(stage10): complete Phase 2 framework — ready for per-dept rollout"
```

- [ ] **Step 2: Tag**

```bash
git tag stage-10-framework-live
```

- [ ] **Step 3: Open PR for review**

```bash
gh pr create --title "Stage 10: Phase 2 Department Framework" \
  --body-file docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md
```

---

## Acceptance summary

| Acceptance criterion (from spec §7.1) | Validated by |
|---|---|
| All existing tests still green (CAC + HR regression) | Task 0.2 baseline + Task 8.6 golden-master diff |
| New services pass health/heartbeat | Task 8.6 docker health loop |
| Reflection engine processes a manual day's worth of CAC + HR data without errors | Task 4.9 integration test |
| Validation scripts catch a deliberately-broken JSON config | Task 1.6 + Task 1.7 unit tests |
| Cross-dept read enforcement works | Task 3.2 integration test |
| Skill rename safe (`invest` → `ic`) | Task 2.1 integration test |
| All 9 dept skeleton specs + plans exist | Task 8.3 |
| Approval-UI new tabs functional | Task 7.5 Vitest |

---

## Estimated effort

| Phase | Tasks | Hours |
|---|---|---|
| 0 — Setup + baseline | 2 | 1h |
| 1 — Schema & Config | 8 | 3h |
| 2 — Skills cleanup + frontmatter | 8 | 2h |
| 3 — Shared library | 9 | 3h |
| 4 — Reflection engine | 11 | 4h |
| 5 — Heartbeat | 9 | 3h |
| 6 — Templates | 5 | 2h |
| 7 — Approval-UI | 6 | 3h |
| 8 — Final wiring + skeletons | 7 | 2h |
| **Total** | **65 tasks** | **~23 hours (~3 days focused work)** |

Spec said 1.5 weeks calendar — that includes review cycles, integration testing, and hand-off. Pure coding time is ~3 days.

---

## Out of scope for Stage 10

- Implementing any of the 9 dept orchestrators (Stages 11-19 do that)
- Activating heartbeat for any dept (default disabled per spec §4.8)
- Voyager-style novel-skill invention (deferred per spec §1.5)
- Cross-agent learning across depts (deferred)
- True RL fine-tuning (deferred)

---

## Next steps after Stage 10

1. Stage 11 — Finance: first per-dept rollout, stress-tests cross-read enforcement
2. After Stage 11 lands: pause to verify cross-read works in production (spec §7.5 decision gate)
3. Stages 12-14: easy quad (Risk, Legal, IT) — read-only with existing scaffolds, can run in parallel if review bandwidth allows
4. Stage 15-16: medium pair (Comms, IC)
5. Stage 17-19: complex trio (CIO, VCC, IB)
