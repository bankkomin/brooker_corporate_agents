"""Integration tests for Paperclip service — requires running Docker services."""
import httpx
import pytest

PAPERCLIP_URL = "http://localhost:3100"
API_KEY = "dev-paperclip-key"
HEADERS = {"X-API-Key": API_KEY}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL) as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_departments():
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS) as client:
        resp = await client.get("/departments")
        assert resp.status_code == 200
        depts = resp.json()
        assert any(d["name"] == "cac" for d in depts)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_agents():
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS) as client:
        resp = await client.get("/departments/cac/agents")
        assert resp.status_code == 200
        agents = resp.json()
        agent_names = [a["agent_name"] for a in agents]
        assert "cfo-agent" in agent_names
        assert "openclaw" in agent_names


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_ticket():
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS) as client:
        resp = await client.post("/tickets", json={
            "type": "query",
            "department": "cac",
            "agent": "cfo-agent",
            "payload": {"query": "What is current liquidity?"},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["ticket_id"].startswith("PPC-")
        assert data["status"] == "open"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_ticket():
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS) as client:
        create_resp = await client.post("/tickets", json={
            "type": "proposal",
            "department": "cac",
            "agent": "cfo-agent",
            "payload": {"proposal_id": "chg_test_001"},
        })
        ticket_id = create_resp.json()["ticket_id"]
        resp = await client.get(f"/tickets/{ticket_id}")
        assert resp.status_code == 200
        assert resp.json()["ticket_id"] == ticket_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_ticket_status():
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS) as client:
        create_resp = await client.post("/tickets", json={
            "type": "query",
            "department": "cac",
            "agent": "cfo-agent",
            "payload": {"query": "test"},
        })
        ticket_id = create_resp.json()["ticket_id"]
        resp = await client.patch(f"/tickets/{ticket_id}", json={"status": "completed"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_heartbeat_registration():
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS) as client:
        resp = await client.post("/heartbeat", json={
            "agent_name": "test-agent",
            "department": "cac",
            "agent_role": "specialist",
            "endpoint_url": "http://test:9999/health",
            "skills": ["shared/test-skill"],
        })
        assert resp.status_code == 200
        assert resp.json()["agent_name"] == "test-agent"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_heartbeats():
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS) as client:
        resp = await client.get("/heartbeats")
        assert resp.status_code == 200
        assert len(resp.json()) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_ticket_invalid_department():
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS) as client:
        resp = await client.post("/tickets", json={
            "type": "query",
            "department": "nonexistent",
            "agent": "test",
            "payload": {},
        })
        assert resp.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_ticket_not_found():
    async with httpx.AsyncClient(base_url=PAPERCLIP_URL, headers=HEADERS) as client:
        resp = await client.get("/tickets/PPC-9999")
        assert resp.status_code == 404
