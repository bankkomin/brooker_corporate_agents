from unittest.mock import AsyncMock, MagicMock  # noqa: I001

import pytest


@pytest.mark.asyncio
async def test_weekly_brief_structure():
    from services.shared.report_generator import generate_weekly_brief

    conn = AsyncMock()
    conn.fetchval.return_value = 5
    conn.fetch.return_value = [{"query": "test query", "hit_count": 1}]

    # Build a proper async context manager for pool.acquire()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)

    pool = MagicMock()
    pool.acquire.return_value = acquire_cm

    report = await generate_weekly_brief("cac", "CAC Committee", pool)

    assert report.report_type == "weekly_brief"
    assert report.dept_id == "cac"
    assert len(report.sections) >= 1
    assert "Activity Summary" in report.sections[0].title
