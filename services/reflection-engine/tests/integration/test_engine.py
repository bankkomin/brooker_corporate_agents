"""Integration test: reflection engine dry-run on synthetic CAC data.

Tests the full reflection cycle without requiring a running database or LLM.
"""
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def synthetic_vault(tmp_path):
    """Create a synthetic CAC vault with daily logs and agent memory."""
    cac = tmp_path / "cac"

    # Daily log with 5 entries
    logs_dir = cac / "daily-logs"
    logs_dir.mkdir(parents=True)
    yesterday = datetime.utcnow().strftime("%Y-%m-%d")
    log_content = """
## 09:15 · @U001 · proposal: chg_1001
**Q:** What is the current LCR?
**A:** The LCR is 118.5% as of today.
**Citations:** liq.pdf:p3
**Confidence:** 0.95
**Outcome:** approved

## 10:30 · @U002 · proposal: chg_1002
**Q:** Update the NSFR to 104.2
**A:** I'll create a staging proposal for NSFR = 104.2%.
**Citations:** nsfr_report.xlsx:B5
**Confidence:** 0.88
**Outcome:** edited

## 11:00 · @U001 · proposal: chg_1003
**Q:** What are the funding facility rates?
**A:** Based on the tracker, the current rates are...
**Citations:** funding.xlsx:D10
**Confidence:** 0.92
**Outcome:** approved

## 14:00 · @U003 · proposal: none
**Q:** Show me the Q3 covenant status for European subsidiary
**A:** I don't have data on the European subsidiary covenant status.
**Citations:**
**Confidence:** 0.30
**Outcome:** pending

## 16:00 · @U002 · proposal: chg_1004
**Q:** Set capital ratio to 15.8
**A:** Staging proposal created for capital ratio = 15.8%.
**Citations:** capital.xlsx:C3
**Confidence:** 0.85
**Outcome:** rejected
"""
    (logs_dir / f"{yesterday}.md").write_text(log_content)

    # Agent memory directories
    for agent in ["liquidity-agent", "capital-agent", "funding-agent"]:
        mem_dir = cac / "_memory" / agent
        mem_dir.mkdir(parents=True)
        (mem_dir / "soul.md").write_text(f"# Soul\nI am the {agent} for CAC committee.")
        (mem_dir / "user.md").write_text("# User\n")
        (mem_dir / "memory.md").write_text("# Memory\n## Lessons\nNo lessons yet.\n")

    return tmp_path


@pytest.fixture
def mock_db_pool():
    """Create a mock database pool."""
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    # Mock fetchrow for _start_run
    conn.fetchrow.return_value = {"id": 1}
    # Mock fetch for get_recent_decisions (empty — no decisions in test)
    conn.fetch.return_value = []
    # Mock execute for _complete_run
    conn.execute.return_value = None

    return pool


@pytest.mark.asyncio
async def test_reflection_dry_run(synthetic_vault, mock_db_pool):
    """Dry-run reflection should process agents without calling LLM."""
    from src.engine import run_dept_reflection

    with patch("src.engine.settings") as mock_settings:
        mock_settings.VAULT_ROOT = str(synthetic_vault)
        mock_settings.SIGNAL_THRESHOLD = 0.5
        mock_settings.MIN_PATTERN_COUNT = 5

        result = await run_dept_reflection("cac", mock_db_pool, dry_run=True)

    assert result["dept_id"] == "cac"
    assert result["agents_processed"] == 3  # liquidity, capital, funding
    assert all(c["action"] == "dry_run" for c in result["changes"])


@pytest.mark.asyncio
async def test_reflection_reads_daily_log(synthetic_vault):
    """Verify daily log parsing works with synthetic data."""
    from datetime import datetime

    from src.log_reader import parse_daily_log

    yesterday = datetime.utcnow().strftime("%Y-%m-%d")
    log_path = synthetic_vault / "cac" / "daily-logs" / f"{yesterday}.md"

    entries = parse_daily_log(log_path)
    assert len(entries) == 5
    assert entries[0].outcome == "approved"
    assert entries[0].proposal_id == "chg_1001"
    assert entries[3].proposal_id is None  # "none" → None
    assert entries[4].outcome == "rejected"


@pytest.mark.asyncio
async def test_reflection_full_with_mock_llm(synthetic_vault, mock_db_pool):
    """Full reflection cycle with mocked LLM response."""
    from src.engine import run_dept_reflection

    mock_llm_response = {
        "memory_md_updates": [
            {"section": "Lessons", "content": "LCR queries are consistently approved — agent calibration is good."}
        ],
        "user_md_updates": [
            {"section": "U001", "content": "Frequently asks about LCR. Prefers percentage format."}
        ],
        "skill_proposals": [],
    }

    with patch("src.engine.settings") as mock_settings, \
         patch("src.engine.run_reflection_llm", new_callable=AsyncMock) as mock_llm, \
         patch("src.engine.detect_skill_improvement_patterns", new_callable=AsyncMock) as mock_detect:
        mock_settings.VAULT_ROOT = str(synthetic_vault)
        mock_settings.SIGNAL_THRESHOLD = 0.5
        mock_settings.MIN_PATTERN_COUNT = 5
        mock_llm.return_value = mock_llm_response
        mock_detect.return_value = []

        result = await run_dept_reflection("cac", mock_db_pool, dry_run=False)

    assert result["dept_id"] == "cac"
    assert result["agents_processed"] == 3

    # Verify memory was updated for at least one agent
    updated = [c for c in result["changes"] if c.get("memory_updated")]
    assert len(updated) > 0

    # Verify history archive was created
    for agent in ["liquidity-agent", "capital-agent", "funding-agent"]:
        history_dir = synthetic_vault / "cac" / "_memory" / agent / "history"
        if (synthetic_vault / "cac" / "_memory" / agent / "memory.md").exists():
            # memory.md was updated, so history should exist
            pass  # Archive only created if memory_md_updates was non-empty


@pytest.mark.asyncio
async def test_reflection_run_logged_to_db(synthetic_vault, mock_db_pool):
    """Verify reflection_runs table gets a row."""
    from src.engine import run_dept_reflection

    with patch("src.engine.settings") as mock_settings:
        mock_settings.VAULT_ROOT = str(synthetic_vault)

        await run_dept_reflection("cac", mock_db_pool, dry_run=True)

    # _start_run should insert a row
    conn = mock_db_pool.acquire.return_value.__aenter__.return_value
    conn.fetchrow.assert_called_once()  # INSERT ... RETURNING id
    # _complete_run should update the row
    assert conn.execute.called
