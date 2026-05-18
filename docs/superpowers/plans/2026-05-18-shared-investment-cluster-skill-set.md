# Shared Investment-Cluster Skill Set Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared investment-cluster skill set — four domain-knowledge skill files plus the `shared_skills` frontmatter mechanism that lets Finance, CIO, and IC agents load them without duplicating content.

**Architecture:** A new canonical `SkillsLoader` in `services/shared/skills_loader.py` parses an agent skill's `shared_skills` frontmatter list and concatenates the *bodies* of the referenced skills into the agent's assembled prompt. Only skill bodies are merged — a shared skill's `permissions` block is never read by the loader, so it cannot widen a consuming agent's capability (the "content-only rule"). The four cluster skills live in `skills/shared/investment-cluster/` and are excluded from the existing flat pan-department auto-load.

**Tech Stack:** Python 3.11, Pydantic v2, `aiofiles`, `PyYAML`, `pytest` (+ `pytest-asyncio`), `structlog`, `ruff`.

**Scope note:** This plan delivers the shared skill set and its loading/validation mechanism as independently testable software. It does **not** scaffold the `finance-orchestrator` service, wire LangGraph, or migrate the existing `cac-orchestrator`/`hr-orchestrator` loaders — those are a separate Finance-department onboarding plan. The new loader is additive; existing orchestrators are untouched and keep working.

**Spec:** `docs/superpowers/specs/2026-04-28-stage11-finance-design.md` §2.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `services/shared/models_phase2.py` | Modify | Add optional `shared_skills` field to `SkillMeta` |
| `services/shared/skills_loader.py` | Create | Canonical async SKILL.md loader with `shared_skills` support |
| `services/shared/tests/unit/test_skills_loader.py` | Create | Unit tests for the loader |
| `services/shared/tests/unit/test_models_phase2.py` | Modify | Add `shared_skills` field tests |
| `skills/shared/investment-cluster/valuation-methodology.md` | Create | Domain skill — asset valuation |
| `skills/shared/investment-cluster/nav-fund-accounting.md` | Create | Domain skill — NAV & fund accounting |
| `skills/shared/investment-cluster/financial-statement-reading.md` | Create | Domain skill — reading financial statements |
| `skills/shared/investment-cluster/investment-cluster-conventions.md` | Create | Domain skill — shared conventions |
| `scripts/validate_skills.py` | Modify | Resolve `shared_skills` refs; assert cluster skills are `read_only` |
| `tests/unit/test_validate_skills.py` | Create | Unit tests for the new validation checks |
| `skills/_template/specialist-1.md` | Modify | Add commented-out `shared_skills` example |
| `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md` | Modify | §4.9 back-reference to `shared_skills` |
| `docs/Implementation.md` | Modify | Note the framework extension under Stage 11 |

---

## Task 1: Add `shared_skills` field to `SkillMeta`

**Files:**
- Modify: `services/shared/models_phase2.py:14-26`
- Test: `services/shared/tests/unit/test_models_phase2.py`

- [ ] **Step 1: Write the failing test**

Add to `services/shared/tests/unit/test_models_phase2.py`:

```python
def test_skillmeta_shared_skills_defaults_empty():
    meta = SkillMeta(
        name="reporting-agent", agent="reporting-agent", dept="finance",
        permissions=SkillPermissions(
            mode="write_via_staging", data_zones=[1, 2],
            outbound_apis=[], read_collections=["finance_docs"],
        ),
    )
    assert meta.shared_skills == []


def test_skillmeta_shared_skills_accepts_paths():
    meta = SkillMeta(
        name="reporting-agent", agent="reporting-agent", dept="finance",
        permissions=SkillPermissions(
            mode="write_via_staging", data_zones=[1, 2],
            outbound_apis=[], read_collections=["finance_docs"],
        ),
        shared_skills=["shared/investment-cluster/valuation-methodology"],
    )
    assert meta.shared_skills == ["shared/investment-cluster/valuation-methodology"]
```

If `SkillMeta`/`SkillPermissions` are not already imported at the top of the test file, add: `from models_phase2 import SkillMeta, SkillPermissions` (match the import style already used in that file).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/shared && python -m pytest tests/unit/test_models_phase2.py::test_skillmeta_shared_skills_defaults_empty -v`
Expected: FAIL — `TypeError` / unexpected keyword `shared_skills` or `AttributeError`.

- [ ] **Step 3: Add the field**

In `services/shared/models_phase2.py`, inside `class SkillMeta`, add after the `output_types` field:

```python
    shared_skills: List[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd services/shared && python -m pytest tests/unit/test_models_phase2.py -v`
Expected: PASS (all tests in file, including the two new ones).

- [ ] **Step 5: Commit**

```bash
git add services/shared/models_phase2.py services/shared/tests/unit/test_models_phase2.py
git commit -m "feat(skills): add shared_skills field to SkillMeta"
```

---

## Task 2: Canonical `SkillsLoader` with `shared_skills` support

**Files:**
- Create: `services/shared/skills_loader.py`
- Test: `services/shared/tests/unit/test_skills_loader.py`

The loader assembles an agent's prompt from three layers, in order: (1) pan-department shared skills (flat `skills/shared/*.md` files — subdirectories excluded), (2) cluster skills named in the agent skill's `shared_skills` frontmatter, (3) the agent's own skill. Only skill *bodies* are concatenated. The loader reads frontmatter **only** for the agent's own skill (to get its `shared_skills` list) — never to extract a shared skill's `permissions`.

- [ ] **Step 1: Write the failing tests**

Create `services/shared/tests/unit/test_skills_loader.py`:

```python
import pytest

from skills_loader import SkillsLoader, SharedSkillNotFoundError

pytestmark = pytest.mark.asyncio


def _write(path, frontmatter: str, body: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")


@pytest.fixture
def skills_dir(tmp_path):
    # Pan-department shared skill (flat file — auto-loaded)
    _write(tmp_path / "shared" / "citation-format.md",
           "name: citation-format", "Cite every claim.")
    # Cluster shared skill (in subdir — NOT auto-loaded, only via shared_skills)
    _write(tmp_path / "shared" / "investment-cluster" / "valuation-methodology.md",
           "name: valuation-methodology\npermissions:\n  mode: read_only\n"
           "  data_zones: [1]\n  outbound_apis: []\n  read_collections: []",
           "Mark holdings to market.")
    # Agent skill declaring the cluster skill
    _write(tmp_path / "finance" / "reporting.md",
           "name: reporting-agent\nagent: reporting-agent\ndept: finance\n"
           "permissions:\n  mode: write_via_staging\n  data_zones: [1, 2]\n"
           "  outbound_apis: []\n  read_collections: [finance_docs]\n"
           "shared_skills:\n  - shared/investment-cluster/valuation-methodology",
           "Draft the annual report.")
    return tmp_path


async def test_load_skill_strips_frontmatter(skills_dir):
    loader = SkillsLoader(str(skills_dir))
    content = await loader.load_skill("finance/reporting")
    assert content == "Draft the annual report."
    assert "name: reporting-agent" not in content


async def test_load_skill_missing_returns_empty(skills_dir):
    loader = SkillsLoader(str(skills_dir))
    assert await loader.load_skill("finance/does-not-exist") == ""


async def test_load_frontmatter_returns_dict(skills_dir):
    loader = SkillsLoader(str(skills_dir))
    fm = await loader.load_frontmatter("finance/reporting")
    assert fm["shared_skills"] == ["shared/investment-cluster/valuation-methodology"]
    assert fm["permissions"]["mode"] == "write_via_staging"


async def test_load_agent_skills_concatenates_in_order(skills_dir):
    loader = SkillsLoader(str(skills_dir))
    result = await loader.load_agent_skills("reporting-agent", "finance/reporting")
    # Pan-dept shared first, cluster skill next, agent skill last
    assert result.index("Cite every claim.") \
        < result.index("Mark holdings to market.") \
        < result.index("Draft the annual report.")


async def test_cluster_skill_not_auto_loaded_without_declaration(skills_dir):
    # An agent that does NOT declare shared_skills must not get the cluster skill.
    _write(skills_dir / "finance" / "plain.md",
           "name: plain-agent", "Plain agent body.")
    loader = SkillsLoader(str(skills_dir))
    result = await loader.load_agent_skills("plain-agent", "finance/plain")
    assert "Mark holdings to market." not in result
    assert "Cite every claim." in result  # pan-dept shared still loads


async def test_dangling_shared_skill_raises(skills_dir):
    _write(skills_dir / "finance" / "broken.md",
           "name: broken-agent\nshared_skills:\n  - shared/investment-cluster/missing",
           "Broken agent body.")
    loader = SkillsLoader(str(skills_dir))
    with pytest.raises(SharedSkillNotFoundError, match="missing"):
        await loader.load_agent_skills("broken-agent", "finance/broken")


async def test_content_only_rule(skills_dir):
    # A cluster skill with a dangerous permissions block must not change what
    # load_frontmatter returns for the consuming agent's own skill.
    _write(skills_dir / "shared" / "investment-cluster" / "evil.md",
           "name: evil\npermissions:\n  mode: write_direct\n  data_zones: [1, 2, 3]\n"
           "  outbound_apis: [gmail, slack]\n  read_collections: []",
           "Evil body.")
    _write(skills_dir / "finance" / "victim.md",
           "name: victim-agent\nagent: victim-agent\ndept: finance\n"
           "permissions:\n  mode: read_only\n  data_zones: [1]\n"
           "  outbound_apis: []\n  read_collections: [finance_docs]\n"
           "shared_skills:\n  - shared/investment-cluster/evil",
           "Victim body.")
    loader = SkillsLoader(str(skills_dir))
    await loader.load_agent_skills("victim-agent", "finance/victim")
    fm = await loader.load_frontmatter("finance/victim")
    # The consuming agent's own permissions are unchanged by loading the cluster skill.
    assert fm["permissions"]["mode"] == "read_only"
    assert fm["permissions"]["outbound_apis"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/shared && python -m pytest tests/unit/test_skills_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'skills_loader'`.

- [ ] **Step 3: Create the loader**

Create `services/shared/skills_loader.py`:

```python
"""Canonical SKILL.md loader with shared-skill support.

Used by Phase 2 department orchestrators. Assembles an agent prompt from:
  1. pan-department shared skills (flat files in skills/shared/*.md),
  2. cluster skills named in the agent skill's `shared_skills` frontmatter,
  3. the agent's own skill.

Content-only rule: only skill *bodies* are concatenated. A shared skill's
frontmatter `permissions` block is never read by this loader, so it cannot
widen a consuming agent's capability — the agent's own SKILL.md frontmatter
remains the sole permission source.
"""
from __future__ import annotations

import os
import re

import aiofiles
import structlog
import yaml

logger = structlog.get_logger("shared.skills_loader")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class SharedSkillNotFoundError(RuntimeError):
    """Raised when an agent declares a `shared_skills` entry that does not resolve."""


class SkillsLoader:
    """Load and cache SKILL.md files for agent prompt injection."""

    def __init__(self, skills_dir: str) -> None:
        self._skills_dir = skills_dir
        self._cache: dict[str, str] = {}
        self._fm_cache: dict[str, dict] = {}

    async def _read_raw(self, skill_path: str) -> str | None:
        full_path = os.path.join(self._skills_dir, f"{skill_path}.md")
        try:
            async with aiofiles.open(full_path, encoding="utf-8") as f:
                return await f.read()
        except FileNotFoundError:
            return None

    async def load_skill(self, skill_path: str) -> str:
        """Load a SKILL.md body (frontmatter stripped). Empty string if missing."""
        if skill_path in self._cache:
            return self._cache[skill_path]
        raw = await self._read_raw(skill_path)
        if raw is None:
            logger.warning("skill_not_found", path=skill_path)
            self._cache[skill_path] = ""
            return ""
        content = _FRONTMATTER_RE.sub("", raw).strip()
        self._cache[skill_path] = content
        logger.info("skill_loaded", path=skill_path, chars=len(content))
        return content

    async def load_frontmatter(self, skill_path: str) -> dict:
        """Parse and cache a SKILL.md frontmatter block. Empty dict if none/missing."""
        if skill_path in self._fm_cache:
            return self._fm_cache[skill_path]
        raw = await self._read_raw(skill_path)
        fm: dict = {}
        if raw is not None:
            m = _FRONTMATTER_RE.match(raw)
            if m:
                parsed = yaml.safe_load(m.group(1))
                if isinstance(parsed, dict):
                    fm = parsed
        self._fm_cache[skill_path] = fm
        return fm

    async def load_agent_skills(self, agent_name: str, agent_skill_path: str) -> str:
        """Assemble pan-dept shared skills + declared cluster skills + agent skill."""
        parts: list[str] = []

        # 1. Pan-department shared skills — flat files only; subdirs excluded.
        shared_dir = os.path.join(self._skills_dir, "shared")
        if os.path.isdir(shared_dir):
            for fname in sorted(os.listdir(shared_dir)):
                if fname.endswith(".md"):
                    name = f"shared/{fname[:-3]}"
                    content = await self.load_skill(name)
                    if content:
                        parts.append(f"# Shared Skill: {fname[:-3]}\n\n{content}")

        # 2. Cluster shared skills declared in the agent skill frontmatter.
        fm = await self.load_frontmatter(agent_skill_path)
        for ref in fm.get("shared_skills") or []:
            content = await self.load_skill(ref)
            if not content:
                raise SharedSkillNotFoundError(
                    f"agent '{agent_name}' declares shared_skills entry '{ref}' "
                    f"which does not resolve under {self._skills_dir}"
                )
            parts.append(f"# Shared Skill: {ref}\n\n{content}")

        # 3. Agent's own skill — last.
        agent_content = await self.load_skill(agent_skill_path)
        if agent_content:
            parts.append(f"# Agent Skill: {agent_name}\n\n{agent_content}")

        return "\n\n---\n\n".join(parts)

    def clear_cache(self) -> None:
        """Clear the in-memory skill and frontmatter caches."""
        self._cache.clear()
        self._fm_cache.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd services/shared && python -m pytest tests/unit/test_skills_loader.py -v`
Expected: PASS — 7 tests.

If `ModuleNotFoundError` for `pytest_asyncio` or `async def test` is skipped: confirm `pytest-asyncio` is installed (`pip install pytest-asyncio`) and that `services/shared` has a `pytest.ini`/`conftest.py` enabling asyncio mode. The existing `services/shared/tests/conftest.py`-style files already run async tests for other modules (e.g. `test_load_memory.py`) — match their configuration.

- [ ] **Step 5: Run ruff**

Run: `ruff check services/shared/skills_loader.py services/shared/tests/unit/test_skills_loader.py`
Expected: clean (no errors).

- [ ] **Step 6: Commit**

```bash
git add services/shared/skills_loader.py services/shared/tests/unit/test_skills_loader.py
git commit -m "feat(skills): canonical SkillsLoader with shared_skills support"
```

---

## Task 3: Create the four cluster skill files

**Files:**
- Create: `skills/shared/investment-cluster/valuation-methodology.md`
- Create: `skills/shared/investment-cluster/nav-fund-accounting.md`
- Create: `skills/shared/investment-cluster/financial-statement-reading.md`
- Create: `skills/shared/investment-cluster/investment-cluster-conventions.md`

These are domain-knowledge reference skills, not agent definitions. Each carries a minimal frontmatter with a `read_only` permissions block (required so `validate_skills.py` recognises and gates them — see Task 4). The body is grounded in real corporate documents under `O:\brooker_database`. Use the `anthropic-skills:pdf`, `anthropic-skills:docx`, and `anthropic-skills:xlsx` skills to extract source content where needed.

- [ ] **Step 1: Create `valuation-methodology.md`**

Path: `skills/shared/investment-cluster/valuation-methodology.md`. Frontmatter verbatim:

```yaml
---
name: valuation-methodology
kind: shared-skill
cluster: investment
version: 1.0
permissions:
  mode: read_only
  data_zones: [1]
  outbound_apis: []
  read_collections: []
---
```

Body sections (markdown `##` headings), each grounded as noted:

- `## Purpose` — one paragraph: this skill gives Finance/CIO/IC agents a consistent method for valuing holdings.
- `## Listed Holdings` — mark-to-market of listed equities; grounded in `O:\brooker_database\cio\portfolio\*\Weekly BG *.xlsx` (column structure, pricing source).
- `## Non-Listed & Private Holdings` — comparables / cost / last-round; grounded in `O:\brooker_database\cio\portfolio\nonlisted\AsianFinance BOD BUSINESS PLAN (15 DEC 2025).pdf`.
- `## Digital-Asset & Mining Positions` — valuation of crypto and mining interests; grounded in `O:\brooker_database\cio\Mining Summary.pptx` and the Coin Weekly reports.
- `## Valuation Date & Staleness` — which valuation date to use, how to flag stale marks.
- `## Citations` — agents must cite the source report and date for every valuation figure.

- [ ] **Step 2: Create `nav-fund-accounting.md`**

Path: `skills/shared/investment-cluster/nav-fund-accounting.md`. Frontmatter — identical to Step 1 but `name: nav-fund-accounting`.

Body sections:

- `## Purpose` — consistent NAV and fund-accounting reasoning across the cluster.
- `## NAV Calculation` — gross asset value, liabilities, NAV per unit; grounded in `O:\brooker_database\cio\portfolio\*\BSFL Monthly *.xlsx`.
- `## Subscriptions & Redemptions` — how units are issued/redeemed and the effect on NAV.
- `## Fund Accounting Conventions` — accrual treatment, fee accruals, period-end cut-off.
- `## Cross-Reference` — note that CIO/VCC NAV reports and the Net Worth quarterly file (`O:\brooker_database\cio\portfolio\Mar\NET WORTH EVERY QUARTER (2025_26).xls`) are the authoritative figures.

- [ ] **Step 3: Create `financial-statement-reading.md`**

Path: `skills/shared/investment-cluster/financial-statement-reading.md`. Frontmatter — identical pattern, `name: financial-statement-reading`.

Body sections:

- `## Purpose` — how cluster agents interpret financial statements and audited reports.
- `## Statement Structure` — balance sheet, P&L, cash flow, notes; grounded in `O:\brooker_database\finance\BICL\BICL_AuditedReport_31Dec2025.pdf`.
- `## Key Ratios` — liquidity, leverage, profitability ratios and how to compute them.
- `## Notes & Disclosures` — why the notes matter; related-party loans (grounded in `O:\brooker_database\finance\BICL\No.35 LOAN AGREEMENT *.pdf`).
- `## Year-over-Year Comparison` — comparing the 2024 vs 2025 audited reports.

- [ ] **Step 4: Create `investment-cluster-conventions.md`**

Path: `skills/shared/investment-cluster/investment-cluster-conventions.md`. Frontmatter — identical pattern, `name: investment-cluster-conventions`.

Body sections:

- `## Purpose` — shared reasoning and escalation conventions for Finance, CIO, and IC.
- `## Citation Style` — every figure cites `[Source: <document> | <date>]`; consistent with `skills/shared/citation-format.md`.
- `## Cross-Department Reasoning` — when a cluster agent should defer to another cluster department's owned data (e.g. Finance defers to CIO for live portfolio marks).
- `## Shared Escalation Cues` — figures that warrant escalation across the cluster (large NAV swings, covenant-relevant ratios); grounded in `doc_cio_investment_policy` (the Investment Policy).
- `## Governing Policy` — the Brooker Group Investment Policy governs all three departments.

- [ ] **Step 5: Validate the new files parse**

Run: `python scripts/validate_skills.py`
Expected: still `OK` (Task 4 not yet applied — this confirms the four files at minimum carry a valid `permissions.mode`). If it errors on the new files, fix their frontmatter.

- [ ] **Step 6: Commit**

```bash
git add skills/shared/investment-cluster/
git commit -m "feat(skills): add investment-cluster shared skill set"
```

---

## Task 4: Extend `validate_skills.py`

**Files:**
- Modify: `scripts/validate_skills.py`
- Test: `tests/unit/test_validate_skills.py`

Two new checks: (a) every `shared_skills` reference resolves to an existing file under `skills/`; (b) every file under `skills/shared/investment-cluster/` declares `permissions.mode: read_only` and `outbound_apis: []`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_validate_skills.py`:

```python
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "validate_skills.py"


def _run(skill_dir: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--skill-dir", str(skill_dir)],
        capture_output=True, text=True,
    )


def _write(path: Path, frontmatter: str, body: str = "Body."):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")


def test_dangling_shared_skill_reference_fails(tmp_path):
    _write(tmp_path / "finance" / "reporting.md",
           "name: reporting-agent\npermissions:\n  mode: write_via_staging\n"
           "  data_zones: [1]\n  outbound_apis: []\n  read_collections: []\n"
           "shared_skills:\n  - shared/investment-cluster/missing")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "shared_skills" in result.stderr and "missing" in result.stderr


def test_resolved_shared_skill_reference_passes(tmp_path):
    _write(tmp_path / "shared" / "investment-cluster" / "valuation-methodology.md",
           "name: valuation-methodology\npermissions:\n  mode: read_only\n"
           "  data_zones: [1]\n  outbound_apis: []\n  read_collections: []")
    _write(tmp_path / "finance" / "reporting.md",
           "name: reporting-agent\npermissions:\n  mode: write_via_staging\n"
           "  data_zones: [1]\n  outbound_apis: []\n  read_collections: []\n"
           "shared_skills:\n  - shared/investment-cluster/valuation-methodology")
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr


def test_cluster_skill_must_be_read_only(tmp_path):
    _write(tmp_path / "shared" / "investment-cluster" / "bad.md",
           "name: bad\npermissions:\n  mode: write_via_staging\n"
           "  data_zones: [1]\n  outbound_apis: []\n  read_collections: []")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "read_only" in result.stderr


def test_cluster_skill_outbound_apis_must_be_empty(tmp_path):
    _write(tmp_path / "shared" / "investment-cluster" / "bad2.md",
           "name: bad2\npermissions:\n  mode: read_only\n"
           "  data_zones: [1]\n  outbound_apis: [gmail]\n  read_collections: []")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "outbound_apis" in result.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_validate_skills.py -v`
Expected: FAIL — `test_dangling_shared_skill_reference_fails` and the two cluster-skill tests fail because the checks do not exist yet (script returns 0).

- [ ] **Step 3: Add the checks**

In `scripts/validate_skills.py`, inside the `for f in skill_dir.rglob("*.md"):` loop, after the `output_types` loop (after line 70, before the loop ends), add:

```python
        # shared_skills references must resolve to existing skill files
        for ref in fm.get("shared_skills") or []:
            ref_path = skill_dir / f"{ref}.md"
            if not ref_path.exists():
                errors.append(f"{f.relative_to(skill_dir)}: shared_skills entry "
                              f"'{ref}' does not resolve to a file under {skill_dir}")

        # investment-cluster skills must be content-only (read_only, no outbound)
        if "investment-cluster" in f.parts:
            if not isinstance(perms, dict) or perms.get("mode") != "read_only":
                errors.append(f"{f.relative_to(skill_dir)}: investment-cluster skills "
                              f"must declare permissions.mode 'read_only'")
            if isinstance(perms, dict) and perms.get("outbound_apis"):
                errors.append(f"{f.relative_to(skill_dir)}: investment-cluster skills "
                              f"must declare an empty outbound_apis list")
```

Note: `perms` is already assigned earlier in the loop (`perms = fm.get("permissions")`). The `shared_skills` check uses `fm` directly, so it works even for skills with no `permissions` block (the existing `if perms is None: continue` happens *after* — see Step 4).

- [ ] **Step 4: Fix the early-`continue` ordering**

The existing code has `if perms is None: continue` at line ~53-54, which would skip the new checks for any skill lacking a `permissions` block. Move the new `shared_skills` and `investment-cluster` checks to run **before** that `continue`. Concretely, place the two new blocks immediately after `checked += 1` (line ~51) and before `perms = fm.get("permissions")`. Adjust the `investment-cluster` block to read `perms = fm.get("permissions")` locally first:

```python
        checked += 1

        # shared_skills references must resolve to existing skill files
        for ref in fm.get("shared_skills") or []:
            ref_path = skill_dir / f"{ref}.md"
            if not ref_path.exists():
                errors.append(f"{f.relative_to(skill_dir)}: shared_skills entry "
                              f"'{ref}' does not resolve to a file under {skill_dir}")

        # investment-cluster skills must be content-only (read_only, no outbound)
        if "investment-cluster" in f.parts:
            ic_perms = fm.get("permissions")
            if not isinstance(ic_perms, dict) or ic_perms.get("mode") != "read_only":
                errors.append(f"{f.relative_to(skill_dir)}: investment-cluster skills "
                              f"must declare permissions.mode 'read_only'")
            if isinstance(ic_perms, dict) and ic_perms.get("outbound_apis"):
                errors.append(f"{f.relative_to(skill_dir)}: investment-cluster skills "
                              f"must declare an empty outbound_apis list")

        perms = fm.get("permissions")
        if perms is None:
            continue  # old-format skill without permissions block — skip until migration
```

(Remove the duplicate `perms = fm.get("permissions")` / `if perms is None` that previously sat at lines ~52-54.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_validate_skills.py -v`
Expected: PASS — 4 tests.

- [ ] **Step 6: Run the validator on the real repo**

Run: `python scripts/validate_skills.py`
Expected: `OK — N skill files validated` (the four cluster files from Task 3 pass; no dangling refs since no real agent declares `shared_skills` yet).

- [ ] **Step 7: Run ruff**

Run: `ruff check scripts/validate_skills.py`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add scripts/validate_skills.py tests/unit/test_validate_skills.py
git commit -m "feat(skills): validate shared_skills refs and cluster read-only rule"
```

---

## Task 5: Add `shared_skills` example to the skill template

**Files:**
- Modify: `skills/_template/specialist-1.md`

- [ ] **Step 1: Inspect the template file**

Run: `cat skills/_template/specialist-1.md` (read its current frontmatter to match style).

- [ ] **Step 2: Add a commented example**

In `skills/_template/specialist-1.md`, inside the frontmatter block, after the `permissions:` block, add:

```yaml
# shared_skills:                                       # optional — cluster skills to load
#   - shared/investment-cluster/financial-statement-reading
```

`validate_skills.py` skips any path containing `template`, so the commented example is not validated — leaving it commented also keeps it inert.

- [ ] **Step 3: Verify the validator still passes**

Run: `python scripts/validate_skills.py`
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add skills/_template/specialist-1.md
git commit -m "docs(skills): add shared_skills example to skill template"
```

---

## Task 6: Documentation back-references

**Files:**
- Modify: `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
- Modify: `docs/Implementation.md`

- [ ] **Step 1: Add a framework-spec back-reference**

In `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`, locate §4.9 (the "Per-skill permission registry" section, around the SKILL.md frontmatter example). After the closing of the YAML example block, add:

```markdown
> **Extension (Stage 11):** SKILL.md frontmatter also accepts an optional `shared_skills`
> list — cluster skill paths whose *bodies* are concatenated into the agent prompt by
> `SkillsLoader`. Shared skills are content-only: their `permissions` block is never
> merged. See `docs/superpowers/specs/2026-04-28-stage11-finance-design.md` §2.
```

- [ ] **Step 2: Note the extension in Implementation.md**

In `docs/Implementation.md`, under the `## Stage 11 — Finance Department` heading, add a line:

```markdown
**Framework extension:** shared investment-cluster skill set + `shared_skills` loader mechanism — see `docs/superpowers/plans/2026-05-18-shared-investment-cluster-skill-set.md`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md docs/Implementation.md
git commit -m "docs: cross-reference shared_skills framework extension"
```

---

## Task 7: Full regression check

- [ ] **Step 1: Run the shared-services unit suite**

Run: `cd services/shared && python -m pytest tests/unit -v`
Expected: all tests pass, including the new `test_skills_loader.py` and updated `test_models_phase2.py`.

- [ ] **Step 2: Run the validation tests**

Run: `python -m pytest tests/unit/test_validate_skills.py -v`
Expected: 4 tests pass.

- [ ] **Step 3: Run both validators**

Run: `python scripts/validate_skills.py && python scripts/validate_config.py`
Expected: both print `OK`.

- [ ] **Step 4: Run ruff over all changed files**

Run: `ruff check services/shared/skills_loader.py services/shared/models_phase2.py services/shared/tests/unit/test_skills_loader.py scripts/validate_skills.py tests/unit/test_validate_skills.py`
Expected: clean.

- [ ] **Step 5: Final commit (if any fixups were needed)**

```bash
git add -A
git commit -m "test: regression pass for shared investment-cluster skill set"
```

---

## Self-Review

**Spec coverage** (against `2026-04-28-stage11-finance-design.md` §2):
- §2.2 location & 4 files → Task 3 ✓
- §2.3 `shared_skills` frontmatter + `SkillsLoader` concatenation, order, hard error → Tasks 1, 2 ✓
- §2.4 content-only rule → Task 2 (`test_content_only_rule`) ✓
- §2.5 validation (dangling refs, cluster read-only) → Task 4 ✓
- §2.7 framework changes: frontmatter schema (Task 1), `SkillsLoader` (Task 2), `validate_skills.py` (Task 4), `_template` example (Task 5), framework-spec back-reference (Task 6) ✓

Out of scope by design (separate Finance-onboarding plan): the `finance-orchestrator` service, LangGraph wiring, `departments.json`/`document_inventory.json` edits, `cac`/`hr` loader migration. Not gaps.

**Placeholder scan:** No `TBD`/`TODO`/"implement later". Task 3 skill bodies are specified as section skeletons with named grounding documents — this is a content spec, not a placeholder; the prose is authored from the named sources.

**Type consistency:** `SkillsLoader`, `SharedSkillNotFoundError`, `load_skill`, `load_frontmatter`, `load_agent_skills`, `clear_cache` are used identically in Task 2's code and tests. `SkillMeta.shared_skills` (Task 1) and the frontmatter key `shared_skills` (Tasks 2-5) match. `permissions.mode` / `outbound_apis` names match the existing `models_phase2.py` and `validate_skills.py`.
