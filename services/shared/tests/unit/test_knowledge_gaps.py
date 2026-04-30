import pytest
from unittest.mock import AsyncMock
from services.shared.knowledge_gaps import detect_self_report


@pytest.mark.asyncio
async def test_detects_no_data_phrase():
    db_conn = AsyncMock()
    result = await detect_self_report(
        response="I don't have data on the Q3 NSFR ratio.",
        dept_id="cac", agent_id="liquidity-agent",
        query="Q3 NSFR", db_conn=db_conn,
    )
    assert result is True
    db_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_no_detection_on_normal_response():
    db_conn = AsyncMock()
    result = await detect_self_report(
        response="The LCR is 118.5% as of today.",
        dept_id="cac", agent_id="liquidity-agent",
        query="LCR", db_conn=db_conn,
    )
    assert result is False
    db_conn.execute.assert_not_called()
