"""E2E escalation flow test."""
import httpx
import pytest

PAPERCLIP_URL = "http://localhost:3100"
HEADERS = {"X-API-Key": "dev-paperclip-key"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_escalation_creates_ticket():
    """Breach detection -> escalation ticket created."""
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS, timeout=30.0) as client:
        resp = await client.post("/tickets", json={
            "type": "escalation",
            "department": "cac",
            "agent": "cfo-agent",
            "payload": {
                "breach_type": "covenant_ratio",
                "details": "Ratio at 9.2%, threshold is 10%",
                "severity": "high",
            },
        })
        assert resp.status_code == 201
        ticket = resp.json()
        assert ticket["type"] == "escalation"
        assert ticket["status"] == "open"
