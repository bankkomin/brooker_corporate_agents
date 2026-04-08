"""Unit tests for the gateway service health endpoint."""
from fastapi.testclient import TestClient


def test_health_endpoint_returns_200():
    """GET /health returns 200 with service name."""
    from services.gateway.src.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "gateway"


def test_root_returns_service_info():
    """GET / returns basic service information."""
    from services.gateway.src.main import app

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "corporate-ai-agents" in data["name"].lower() or "gateway" in data["name"].lower()
