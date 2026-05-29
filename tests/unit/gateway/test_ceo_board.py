"""Unit tests for the gateway CEO board aggregator endpoint."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from services.gateway.src.main import app


def _make_token(
    private_pem: bytes,
    *,
    sub: str = "ceo-01",
    dept: str = "ceo",
    role: str = "ceo",
    permissions: list[str] | None = None,
    exp_delta: timedelta = timedelta(hours=1),
) -> str:
    payload: dict = {
        "sub": sub,
        "dept": dept,
        "role": role,
        "permissions": permissions or ["read"],
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + exp_delta,
    }
    return jwt.encode(payload, private_pem, algorithm="RS256")


def _make_brooker_token(
    secret: str,
    *,
    sub: str = "emp-ceo-01",
    role: str = "ceo",
    email: str = "ceo@brookergroup.com",
    exp_delta: timedelta = timedelta(hours=1),
) -> str:
    """Forge an HS256 Brooker-issued token (no dept claim required)."""
    payload: dict = {
        "sub": sub,
        "role": role,
        "email": email,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + exp_delta,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class _FakeAcquire:
    def __init__(self, conn: AsyncMock) -> None:
        self._conn = conn

    async def __aenter__(self) -> AsyncMock:
        return self._conn

    async def __aexit__(self, *args: object) -> None:
        pass


def _mock_pool() -> tuple[MagicMock, AsyncMock]:
    conn = AsyncMock()
    pool = MagicMock()
    pool.acquire.return_value = _FakeAcquire(conn)
    return pool, conn


def _proposal_row(
    *,
    id_: str = "chg_0001",
    dept: str = "cac",
    status: str = "pending",
    created_at: datetime | None = None,
    decided_at: datetime | None = None,
) -> dict:
    row = {
        "id": id_,
        "created_at": created_at or datetime(2026, 5, 1, 12, 0, 0),
        "agent": "funding-agent",
        "file": "ALCO_Tracker.xlsx",
        "tab": "Funding Facilities",
        "cell": "E8",
        "old_value": None,
        "new_value": "3.15",
        "confidence": 0.91,
        "reasoning": "test",
        "status": status,
        "dept": dept,
        "source": "Slack",
    }
    if decided_at is not None:
        row["decided_at"] = decided_at
    return row


def _escalation_row(*, id_: int = 1, dept: str = "cac", severity: str = "high") -> dict:
    return {
        "id": id_,
        "created_at": datetime(2026, 5, 1, 12, 0, 0),
        "interaction_id": 42,
        "severity": severity,
        "trigger_type": "confidence_threshold",
        "detail": "Confidence below 0.5",
        "paperclip_ticket_id": "TKT-001",
        "resolved_at": None,
        "resolved_by": None,
        "dept": dept,
    }


def _ceo_claims(source: str = "cac"):
    from services.gateway.src.auth import JWTClaims

    return JWTClaims(
        sub="ceo-01",
        dept="ceo",
        role="ceo",
        permissions=["read"],
        proposal_id=None,
        email="ceo@brookergroup.com" if source == "brooker" else None,
        source=source,
    )


def _hod_claims():
    from services.gateway.src.auth import JWTClaims

    return JWTClaims(
        sub="hod-cac-01",
        dept="cac",
        role="hod",
        permissions=["read", "approve"],
        proposal_id=None,
    )


class TestCeoBoardSuccess:
    """GET /api/ceo/board — happy path for the CEO role."""

    @pytest.mark.asyncio
    async def test_returns_columns_aggregated_across_depts(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem)
        pool, conn = _mock_pool()

        # Four sequential fetch() calls: pending, approved, rejected, escalations
        conn.fetch = AsyncMock(
            side_effect=[
                [_proposal_row(id_="chg_p1", dept="cac"),
                 _proposal_row(id_="chg_p2", dept="risk")],
                [_proposal_row(id_="chg_a1", dept="cac", status="approved")],
                [],
                [_escalation_row(id_=1, dept="legal", severity="critical")],
            ]
        )

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            mock_validate.return_value = _ceo_claims()

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/ceo/board", headers=_auth_header(token))

        assert resp.status_code == 200
        body = resp.json()
        assert set(body["columns"].keys()) == {"escalated", "pending", "approved", "rejected"}
        assert body["totals"] == {"escalated": 1, "pending": 2, "approved": 1, "rejected": 0}
        assert body["truncated"] == {
            "escalated": False, "pending": False, "approved": False, "rejected": False,
        }
        assert body["window_days"] == 14

        # Cross-dept aggregation: pending column contains both cac and risk
        pending_depts = {p["dept"] for p in body["columns"]["pending"]}
        assert pending_depts == {"cac", "risk"}

        # Escalations column contains a legal entry
        assert body["columns"]["escalated"][0]["dept"] == "legal"
        assert body["columns"]["escalated"][0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_pending_query_has_no_dept_filter(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """The pending query must aggregate across departments, not filter by one."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem)
        pool, conn = _mock_pool()
        conn.fetch = AsyncMock(side_effect=[[], [], [], []])

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            mock_validate.return_value = _ceo_claims()

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/ceo/board", headers=_auth_header(token))

        assert resp.status_code == 200
        first_sql = conn.fetch.call_args_list[0][0][0].lower()
        assert "status = 'pending'" in first_sql
        # Critically: no dept filter — the board is enterprise-wide.
        assert "dept =" not in first_sql

    @pytest.mark.asyncio
    async def test_escalation_query_excludes_resolved(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem)
        pool, conn = _mock_pool()
        conn.fetch = AsyncMock(side_effect=[[], [], [], []])

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            mock_validate.return_value = _ceo_claims()

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/ceo/board", headers=_auth_header(token))

        assert resp.status_code == 200
        esc_sql = conn.fetch.call_args_list[3][0][0].lower()
        assert "resolved_at is null" in esc_sql

    @pytest.mark.asyncio
    async def test_approved_window_uses_decided_at_join(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Review #2: the 14d window must filter on approval_decisions.decided_at,
        not staging_proposals.created_at. A proposal created long ago but decided
        yesterday should still appear in the approved column."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem)
        pool, conn = _mock_pool()

        # Old created_at (30 days ago) but recent decided_at (yesterday) — should appear.
        now = datetime.now(UTC)
        old_proposal = _proposal_row(
            id_="chg_old",
            dept="cac",
            status="approved",
            created_at=now - timedelta(days=30),
            decided_at=now - timedelta(days=1),
        )
        conn.fetch = AsyncMock(side_effect=[[], [old_proposal], [], []])

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            mock_validate.return_value = _ceo_claims()

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/ceo/board", headers=_auth_header(token))

        assert resp.status_code == 200
        # Approved column contains the old-but-recently-decided proposal
        body = resp.json()
        assert body["totals"]["approved"] == 1
        assert body["columns"]["approved"][0]["id"] == "chg_old"

        # Approved SQL JOINs approval_decisions and filters on ad.decided_at
        approved_sql = conn.fetch.call_args_list[1][0][0].lower()
        assert "approval_decisions" in approved_sql
        assert "ad.decided_at" in approved_sql
        assert "interval '1 day'" in approved_sql
        # Window is parameterised, not f-string interpolated
        approved_args = conn.fetch.call_args_list[1][0]
        assert 14 in approved_args  # _RESOLVED_WINDOW_DAYS passed as $1

    @pytest.mark.asyncio
    async def test_severity_ordering_is_urgency_not_alphabetical(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Review #3: ORDER BY must use a CASE expression mapping severity
        strings to urgency rank — not lexicographic sort."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem)
        pool, conn = _mock_pool()
        conn.fetch = AsyncMock(side_effect=[[], [], [], []])

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            mock_validate.return_value = _ceo_claims()

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/ceo/board", headers=_auth_header(token))

        assert resp.status_code == 200
        # Collapse whitespace so the column-aligned CASE WHEN matches regardless
        # of how SEVERITY_ORDER_SQL formats its lines.
        esc_sql = " ".join(conn.fetch.call_args_list[3][0][0].lower().split())
        # Must contain explicit CASE-WHEN mapping, not bare "ORDER BY severity ASC"
        assert "case severity" in esc_sql
        assert "when 'critical' then 0" in esc_sql
        assert "when 'high' then 1" in esc_sql
        assert "when 'medium' then 2" in esc_sql
        assert "when 'low' then 3" in esc_sql
        # Sanity: lexicographic anti-pattern is gone
        assert "order by severity asc" not in esc_sql

    @pytest.mark.asyncio
    async def test_pending_query_has_limit_and_truncated_flag(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Review #4: pending column must be bounded by LIMIT and surface a
        `truncated` flag when the cap is hit."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem)
        pool, conn = _mock_pool()

        # Return 201 rows so we exceed the 200 cap (endpoint fetches limit+1
        # to detect overflow).
        many = [_proposal_row(id_=f"chg_{i:03d}") for i in range(201)]
        conn.fetch = AsyncMock(side_effect=[many, [], [], []])

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            mock_validate.return_value = _ceo_claims()

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/ceo/board", headers=_auth_header(token))

        assert resp.status_code == 200
        body = resp.json()
        # Capped at 200
        assert body["totals"]["pending"] == 200
        assert len(body["columns"]["pending"]) == 200
        # truncated flag flipped
        assert body["truncated"]["pending"] is True

        # SQL contains LIMIT clause
        pending_sql = conn.fetch.call_args_list[0][0][0].lower()
        assert "limit 201" in pending_sql  # _COLUMN_LIMIT + 1 to detect overflow


class TestCeoBoardAuthz:
    """Only roles with canRead='*' may access the board."""

    @pytest.mark.asyncio
    async def test_hod_role_forbidden(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem, role="hod", dept="cac")

        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            mock_validate.return_value = _hod_claims()

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/ceo/board", headers=_auth_header(token))

        assert resp.status_code == 403
        body = resp.json()
        assert body["code"] == "CEO_BOARD_FORBIDDEN"

    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/ceo/board")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_brooker_ceo_token_reaches_board(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Review #1: A Brooker-issued (HS256) CEO token must reach the board
        without an agent_access row scoped to 'cac'. The middleware
        wildcard-read branch should short-circuit the per-dept lookup."""
        # Patch validate_jwt to return a Brooker-source CEO claim. We don't
        # actually need to sign a real HS256 token because validate_jwt itself
        # is mocked — but we still send *a* token to satisfy the auth header
        # presence check in extract_claims.
        token = "fake.brooker.token"
        pool, conn = _mock_pool()
        conn.fetch = AsyncMock(side_effect=[[], [], [], []])

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            mock_validate.return_value = _ceo_claims(source="brooker")

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/ceo/board", headers=_auth_header(token))

        # Brooker CEO must get 200 — the middleware should NOT call
        # resolve_agent_permissions(department_name="cac") for wildcard-read roles.
        assert resp.status_code == 200, (
            f"Brooker CEO should reach the board; got {resp.status_code}: {resp.text}"
        )
