import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_weekly_brief_structure():
    from services.shared.report_generator import generate_weekly_brief

    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    conn.fetchval.return_value = 5
    conn.fetch.return_value = [{"query": "test query", "hit_count": 1}]

    report = await generate_weekly_brief("cac", "CAC Committee", pool)

    assert report.report_type == "weekly_brief"
    assert report.dept_id == "cac"
    assert len(report.sections) >= 1
    assert "Activity Summary" in report.sections[0].title
