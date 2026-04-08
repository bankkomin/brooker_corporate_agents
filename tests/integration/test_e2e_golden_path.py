"""End-to-end golden path test.

Tests: @agent -> answer -> staging proposal -> approve -> sync
Requires all Docker services running.
"""
import httpx
import pytest

ORCHESTRATOR_URL = "http://localhost:3001"
PAPERCLIP_URL = "http://localhost:3100"
HEADERS = {"X-API-Key": "dev-paperclip-key"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_paperclip_has_heartbeats():
    """Verify cac-orchestrator registered its heartbeat."""
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS) as client:
        resp = await client.get("/heartbeats")
        assert resp.status_code == 200
        agents = resp.json()
        agent_names = [a["agent_name"] for a in agents]
        assert "cfo-agent" in agent_names


@pytest.mark.integration
@pytest.mark.asyncio
async def test_golden_path_ticket_creation():
    """Test that a query creates a Paperclip ticket."""
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS, timeout=30.0) as client:
        # Create a ticket directly (simulating what cac-orchestrator does)
        resp = await client.post("/tickets", json={
            "type": "query",
            "department": "cac",
            "agent": "cfo-agent",
            "payload": {
                "query": "What is our current liquidity ratio?",
                "response_summary": "Current LCR is 125%, above the 100% minimum.",
            },
        })
        assert resp.status_code == 201
        ticket = resp.json()
        assert ticket["ticket_id"].startswith("PPC-")
        assert ticket["type"] == "query"

        # Create a proposal ticket
        proposal_resp = await client.post("/tickets", json={
            "type": "proposal",
            "department": "cac",
            "agent": "cfo-agent",
            "payload": {
                "proposal_id": "chg_golden_001",
                "new_value": "3.15",
                "tab": "Funding Facilities",
                "cell": "E8",
            },
        })
        assert proposal_resp.status_code == 201
        assert proposal_resp.json()["type"] == "proposal"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_golden_path_approval_webhook():
    """Test approval webhook updates ticket and routes events."""
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS, timeout=30.0) as client:
        # Create proposal ticket
        create_resp = await client.post("/tickets", json={
            "type": "proposal",
            "department": "cac",
            "agent": "cfo-agent",
            "payload": {"proposal_id": "chg_approve_test"},
        })
        ticket_id = create_resp.json()["ticket_id"]

        # Move to pending_approval
        await client.patch(f"/tickets/{ticket_id}", json={"status": "pending_approval"})

        # Send approval webhook
        webhook_resp = await client.post("/webhooks/approval", json={
            "proposal_id": "chg_approve_test",
            "decision": "approved",
            "reviewer": "cfo@company.com",
            "timestamp": "2026-04-02T10:30:00Z",
        })
        assert webhook_resp.status_code == 200
        assert webhook_resp.json()["decision"] == "approved"

        # Verify ticket updated
        ticket_resp = await client.get(f"/tickets/{ticket_id}")
        assert ticket_resp.json()["status"] == "completed"
