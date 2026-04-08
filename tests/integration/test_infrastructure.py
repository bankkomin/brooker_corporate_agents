"""Integration tests for Stage 1 infrastructure.

Run with Docker services up:
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
    python -m pytest tests/integration/test_infrastructure.py -v -m integration
"""
import os

import httpx
import pytest

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "corporate_agents")
POSTGRES_USER = os.getenv("POSTGRES_USER", "agents")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "devpassword")


@pytest.fixture
def http_client():
    with httpx.Client(timeout=10.0) as client:
        yield client


@pytest.mark.integration
class TestPostgres:
    """Verify PostgreSQL is running with correct schema."""

    @pytest.fixture
    def pg_conn(self):
        import psycopg2

        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
        )
        yield conn
        conn.close()

    def test_postgres_connection(self, pg_conn):
        """Can connect to Postgres."""
        cur = pg_conn.cursor()
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1

    def test_postgres_has_7_tables(self, pg_conn):
        """All 7 tables exist."""
        cur = pg_conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        tables = [row[0] for row in cur.fetchall()]
        expected = [
            "agent_interactions",
            "approval_decisions",
            "email_log",
            "escalations",
            "ingested_documents",
            "staging_proposals",
            "sync_log",
        ]
        assert tables == expected

    def test_staging_proposals_has_correct_columns(self, pg_conn):
        """staging_proposals table has the expected columns."""
        cur = pg_conn.cursor()
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'staging_proposals' ORDER BY ordinal_position"
        )
        columns = [row[0] for row in cur.fetchall()]
        assert "id" in columns
        assert "confidence" in columns
        assert "status" in columns
        assert "interaction_id" in columns


@pytest.mark.integration
class TestQdrant:
    """Verify Qdrant vector store is running."""

    def test_qdrant_health(self, http_client):
        """Qdrant health endpoint responds."""
        response = http_client.get("http://localhost:6333/healthz")
        assert response.status_code == 200


@pytest.mark.integration
class TestMinIO:
    """Verify MinIO object store is running."""

    def test_minio_health(self, http_client):
        """MinIO health endpoint responds."""
        response = http_client.get("http://localhost:9000/minio/health/live")
        assert response.status_code == 200


@pytest.mark.integration
class TestNginx:
    """Verify nginx load balancer is running."""

    def test_nginx_health(self, http_client):
        """nginx health endpoint responds."""
        response = http_client.get("http://localhost:8080/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.integration
class TestGateway:
    """Verify gateway service is running."""

    def test_gateway_health(self, http_client):
        """Gateway health endpoint responds."""
        response = http_client.get("http://localhost:3000/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "gateway"

    def test_gateway_root(self, http_client):
        """Gateway root endpoint returns service info."""
        response = http_client.get("http://localhost:3000/")
        assert response.status_code == 200
