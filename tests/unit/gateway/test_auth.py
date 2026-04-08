"""Unit tests for gateway JWT authentication middleware."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from services.gateway.src.auth import (
    AuthError,
    JWTClaims,
    check_dept_access,
    extract_claims,
    validate_jwt,
)
from services.gateway.src.main import app


def _make_token(
    private_pem: bytes,
    *,
    sub: str = "user-123",
    dept: str = "cac",
    role: str = "analyst",
    permissions: list[str] | None = None,
    proposal_id: str | None = None,
    exp_delta: timedelta = timedelta(hours=1),
) -> str:
    """Helper to create a signed JWT for testing."""
    payload: dict = {
        "sub": sub,
        "dept": dept,
        "role": role,
        "permissions": permissions or ["read", "propose"],
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + exp_delta,
    }
    if proposal_id is not None:
        payload["proposal_id"] = proposal_id
    return jwt.encode(payload, private_pem, algorithm="RS256")


class TestValidateJwt:
    """Tests for validate_jwt()."""

    def test_valid_token_returns_correct_claims(self, rsa_keypair: tuple[bytes, bytes]) -> None:
        """A valid RS256 token decodes to the correct JWTClaims."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(
            private_pem,
            sub="emp-42",
            dept="finance",
            role="hod",
            permissions=["read", "approve"],
            proposal_id="chg_0001",
        )

        claims = validate_jwt(token, public_key=public_pem)

        assert isinstance(claims, JWTClaims)
        assert claims.sub == "emp-42"
        assert claims.dept == "finance"
        assert claims.role == "hod"
        assert list(claims.permissions) == ["read", "approve"]
        assert claims.proposal_id == "chg_0001"

    def test_valid_token_without_proposal_id(self, rsa_keypair: tuple[bytes, bytes]) -> None:
        """A valid token with no proposal_id sets proposal_id to None."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, dept="cac", role="analyst")

        claims = validate_jwt(token, public_key=public_pem)

        assert claims.proposal_id is None

    def test_expired_token_raises_token_expired(self, rsa_keypair: tuple[bytes, bytes]) -> None:
        """An expired token raises AuthError with code TOKEN_EXPIRED."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, exp_delta=timedelta(seconds=-10))

        with pytest.raises(AuthError) as exc_info:
            validate_jwt(token, public_key=public_pem)

        assert exc_info.value.code == "TOKEN_EXPIRED"
        assert exc_info.value.status_code == 401

    def test_invalid_signature_raises_token_invalid(self, rsa_keypair: tuple[bytes, bytes]) -> None:
        """A token signed with a different key raises AuthError with code TOKEN_INVALID."""
        private_pem, _public_pem = rsa_keypair

        # Generate a second key pair — use its public key to verify the first token
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa as rsa_module

        other_private = rsa_module.generate_private_key(public_exponent=65537, key_size=2048)
        other_public_pem = other_private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        token = _make_token(private_pem)

        with pytest.raises(AuthError) as exc_info:
            validate_jwt(token, public_key=other_public_pem)

        assert exc_info.value.code == "TOKEN_INVALID"
        assert exc_info.value.status_code == 401

    def test_malformed_token_raises_token_invalid(self, rsa_keypair: tuple[bytes, bytes]) -> None:
        """A garbage string raises AuthError with code TOKEN_INVALID."""
        _, public_pem = rsa_keypair

        with pytest.raises(AuthError) as exc_info:
            validate_jwt("not.a.jwt", public_key=public_pem)

        assert exc_info.value.code == "TOKEN_INVALID"


class TestCheckDeptAccess:
    """Tests for check_dept_access()."""

    @pytest.fixture(autouse=True)
    def mock_global_roles(self):
        """Provide the standard globalAccess.roles for testing."""
        roles = {
            "ceo": {"canRead": ["*"], "canApprove": ["*"]},
            "cfo": {"canRead": ["cac", "risk"], "canApprove": ["cac"]},
        }
        with patch("services.gateway.src.auth._load_global_access_roles", return_value=roles):
            yield

    def test_matching_dept_passes(self) -> None:
        """No exception raised when claims.dept matches resource_dept."""
        claims = JWTClaims(
            sub="u1",
            dept="finance",
            role="analyst",
            permissions=["read"],
            proposal_id=None,
        )
        # Should not raise
        check_dept_access(claims, "finance")

    def test_dept_mismatch_raises_dept_mismatch(self) -> None:
        """Different dept raises AuthError with code DEPT_MISMATCH and 403."""
        claims = JWTClaims(
            sub="u1",
            dept="finance",
            role="analyst",
            permissions=["read"],
            proposal_id=None,
        )
        with pytest.raises(AuthError) as exc_info:
            check_dept_access(claims, "treasury")

        assert exc_info.value.code == "DEPT_MISMATCH"
        assert exc_info.value.status_code == 403

    def test_ceo_role_bypasses_dept_check(self) -> None:
        """CEO role can access any department without raising."""
        claims = JWTClaims(
            sub="ceo-1",
            dept="executive",
            role="ceo",
            permissions=["read", "approve", "override"],
            proposal_id=None,
        )
        # Should not raise even though dept differs
        check_dept_access(claims, "finance")
        check_dept_access(claims, "treasury")
        check_dept_access(claims, "risk")

    def test_non_ceo_mismatch_raises(self) -> None:
        """Non-CEO roles do NOT bypass the dept check."""
        for role in ("analyst", "hod", "admin", "viewer"):
            claims = JWTClaims(
                sub="u1",
                dept="finance",
                role=role,
                permissions=[],
                proposal_id=None,
            )
            with pytest.raises(AuthError) as exc_info:
                check_dept_access(claims, "treasury")
            assert exc_info.value.code == "DEPT_MISMATCH"

    def test_cfo_can_read_cac(self) -> None:
        """CFO with dept='executive' can access 'cac' (listed in canRead)."""
        claims = JWTClaims(
            sub="cfo-1",
            dept="executive",
            role="cfo",
            permissions=["read"],
            proposal_id=None,
        )
        # Should not raise
        check_dept_access(claims, "cac")

    def test_cfo_can_read_risk(self) -> None:
        """CFO with dept='executive' can access 'risk' (listed in canRead)."""
        claims = JWTClaims(
            sub="cfo-1",
            dept="executive",
            role="cfo",
            permissions=["read"],
            proposal_id=None,
        )
        # Should not raise
        check_dept_access(claims, "risk")

    def test_cfo_cannot_read_hr(self) -> None:
        """CFO cannot access 'hr' — not in canRead list."""
        claims = JWTClaims(
            sub="cfo-1",
            dept="executive",
            role="cfo",
            permissions=["read"],
            proposal_id=None,
        )
        with pytest.raises(AuthError) as exc_info:
            check_dept_access(claims, "hr")
        assert exc_info.value.code == "DEPT_MISMATCH"
        assert exc_info.value.status_code == 403

    def test_cfo_cannot_read_legal(self) -> None:
        """CFO cannot access 'legal' — not in canRead list."""
        claims = JWTClaims(
            sub="cfo-1",
            dept="executive",
            role="cfo",
            permissions=["read"],
            proposal_id=None,
        )
        with pytest.raises(AuthError) as exc_info:
            check_dept_access(claims, "legal")
        assert exc_info.value.code == "DEPT_MISMATCH"
        assert exc_info.value.status_code == 403

    def test_ceo_wildcard_any_dept(self) -> None:
        """CEO role with wildcard canRead='*' can access any department."""
        claims = JWTClaims(
            sub="ceo-1",
            dept="executive",
            role="ceo",
            permissions=["read", "approve", "override"],
            proposal_id=None,
        )
        for dept in ("finance", "treasury", "risk", "hr", "legal", "operations"):
            check_dept_access(claims, dept)

    def test_unknown_role_no_cross_access(self) -> None:
        """A role not listed in globalAccess.roles cannot access other departments."""
        claims = JWTClaims(
            sub="u1",
            dept="finance",
            role="analyst",
            permissions=["read"],
            proposal_id=None,
        )
        with pytest.raises(AuthError) as exc_info:
            check_dept_access(claims, "cac")
        assert exc_info.value.code == "DEPT_MISMATCH"
        assert exc_info.value.status_code == 403

    def test_missing_config_graceful(self) -> None:
        """When _load_global_access_roles returns {}, only same-dept access passes."""
        claims_same_dept = JWTClaims(
            sub="u1",
            dept="cac",
            role="cfo",
            permissions=["read"],
            proposal_id=None,
        )
        claims_other_dept = JWTClaims(
            sub="u2",
            dept="executive",
            role="cfo",
            permissions=["read"],
            proposal_id=None,
        )
        with patch("services.gateway.src.auth._load_global_access_roles", return_value={}):
            # Same dept still passes
            check_dept_access(claims_same_dept, "cac")
            # Cross-dept now blocked since config is empty
            with pytest.raises(AuthError) as exc_info:
                check_dept_access(claims_other_dept, "cac")
            assert exc_info.value.code == "DEPT_MISMATCH"


class TestAuthValidateEndpoint:
    """POST /api/auth/validate — token validation endpoint."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_claims(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """A valid token returns claims with valid=True."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, dept="cac", role="hod")

        with patch("services.gateway.src.main.validate_jwt") as mock_validate:
            mock_validate.return_value = JWTClaims(
                sub="user-123",
                dept="cac",
                role="hod",
                permissions=["read", "propose"],
                proposal_id=None,
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/auth/validate",
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert body["dept"] == "cac"
        assert body["role"] == "hod"
        assert body["sub"] == "user-123"
        assert isinstance(body["permissions"], list)

    @pytest.mark.asyncio
    async def test_no_token_returns_401(self) -> None:
        """Missing Authorization header returns 401 TOKEN_INVALID."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post("/api/auth/validate")

        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "TOKEN_INVALID"

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """An expired token returns 401 TOKEN_EXPIRED."""
        private_pem, _public_pem = rsa_keypair
        token = _make_token(private_pem, exp_delta=timedelta(seconds=-10))

        with patch("services.gateway.src.main.validate_jwt") as mock_validate:
            mock_validate.side_effect = AuthError(
                "TOKEN_EXPIRED", "Token has expired", 401
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/auth/validate",
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "TOKEN_EXPIRED"


class TestExtractClaims:
    """Tests for extract_claims()."""

    def test_extract_claims_valid_token(self, rsa_keypair: tuple[bytes, bytes]) -> None:
        """A request with a valid Bearer token returns JWTClaims."""
        from unittest.mock import MagicMock, patch

        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, sub="emp-1", dept="cac", role="hod")

        request = MagicMock()
        request.headers.get.return_value = f"Bearer {token}"

        expected_claims = JWTClaims(
            sub="emp-1",
            dept="cac",
            role="hod",
            permissions=["read", "propose"],
            proposal_id=None,
        )

        target = "services.gateway.src.auth.validate_jwt"
        with patch(target, return_value=expected_claims) as mock_jwt:
            result = extract_claims(request)

        mock_jwt.assert_called_once_with(token)
        assert result == expected_claims

    def test_extract_claims_missing_header(self) -> None:
        """A request with no Authorization header raises AuthError TOKEN_MISSING."""
        from unittest.mock import MagicMock

        request = MagicMock()
        request.headers.get.return_value = ""

        with pytest.raises(AuthError) as exc_info:
            extract_claims(request)

        assert exc_info.value.code == "TOKEN_MISSING"
        assert exc_info.value.status_code == 401

    def test_extract_claims_empty_bearer(self) -> None:
        """A request with 'Bearer ' and no token raises AuthError TOKEN_MISSING."""
        from unittest.mock import MagicMock

        request = MagicMock()
        request.headers.get.return_value = "Bearer "

        with pytest.raises(AuthError) as exc_info:
            extract_claims(request)

        assert exc_info.value.code == "TOKEN_MISSING"
        assert exc_info.value.status_code == 401
