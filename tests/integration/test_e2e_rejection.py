"""E2E rejection flow test."""
import httpx
import pytest

PAPERCLIP_URL = "http://localhost:3100"
HEADERS = {"X-API-Key": "dev-paperclip-key"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rejection_updates_ticket():
    """HOD rejects -> ticket rejected -> notification sent."""
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS, timeout=30.0) as client:
        create_resp = await client.post("/tickets", json={
            "type": "proposal",
            "department": "cac",
            "agent": "cfo-agent",
            "payload": {"proposal_id": "chg_reject_test"},
        })
        ticket_id = create_resp.json()["ticket_id"]

        await client.patch(f"/tickets/{ticket_id}", json={"status": "pending_approval"})

        resp = await client.post("/webhooks/approval", json={
            "proposal_id": "chg_reject_test",
            "decision": "rejected",
            "reviewer": "cfo@company.com",
            "timestamp": "2026-04-02T10:30:00Z",
            "notes": "Insufficient justification",
        })
        assert resp.status_code == 200

        ticket = await client.get(f"/tickets/{ticket_id}")
        assert ticket.json()["status"] == "rejected"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deferral_keeps_pending():
    """HOD defers -> ticket stays pending_approval."""
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS, timeout=30.0) as client:
        create_resp = await client.post("/tickets", json={
            "type": "proposal",
            "department": "cac",
            "agent": "cfo-agent",
            "payload": {"proposal_id": "chg_defer_test"},
        })
        ticket_id = create_resp.json()["ticket_id"]

        await client.patch(f"/tickets/{ticket_id}", json={"status": "pending_approval"})

        resp = await client.post("/webhooks/approval", json={
            "proposal_id": "chg_defer_test",
            "decision": "deferred",
            "reviewer": "cfo@company.com",
            "timestamp": "2026-04-02T10:30:00Z",
            "notes": "Need more data",
        })
        assert resp.status_code == 200

        ticket = await client.get(f"/tickets/{ticket_id}")
        assert ticket.json()["status"] == "pending_approval"
