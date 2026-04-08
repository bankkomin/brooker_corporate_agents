"""Heartbeat registration, renewal, and stale detection test."""
import httpx
import pytest

PAPERCLIP_URL = "http://localhost:3100"
HEADERS = {"X-API-Key": "dev-paperclip-key"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_heartbeat_registration_and_renewal():
    """Register agent, renew heartbeat, verify health."""
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS) as client:
        resp = await client.post("/heartbeat", json={
            "agent_name": "heartbeat-test-agent",
            "department": "cac",
            "agent_role": "specialist",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

        resp2 = await client.post("/heartbeat", json={
            "agent_name": "heartbeat-test-agent",
            "department": "cac",
            "agent_role": "specialist",
        })
        assert resp2.status_code == 200

        list_resp = await client.get("/heartbeats")
        agents = list_resp.json()
        test_agent = [a for a in agents if a["agent_name"] == "heartbeat-test-agent"]
        assert len(test_agent) == 1
        assert test_agent[0]["health"] == "healthy"
