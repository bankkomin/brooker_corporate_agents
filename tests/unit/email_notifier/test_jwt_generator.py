"""Tests for JWT token generation."""
from __future__ import annotations

import time

import jwt as pyjwt
import pytest


class TestGenerateProposalToken:
    """Tests for generate_proposal_token."""

    def test_token_contains_expected_claims(self, rsa_keypair: tuple[bytes, bytes]) -> None:
        """Generated token should decode to payload with dept, proposal_id, sub, role, perms."""
        from services.email_notifier.src.jwt_generator import generate_proposal_token

        private_pem, public_pem = rsa_keypair
        token = generate_proposal_token(
            proposal_id="chg_0001",
            dept="cac",
            hod_email="hod@brooker.test",
            private_key=private_pem,
            ttl_hours=24,
        )
        claims = pyjwt.decode(token, public_pem, algorithms=["RS256"])
        assert claims["sub"] == "hod@brooker.test"
        assert claims["dept"] == "cac"
        assert claims["proposal_id"] == "chg_0001"
        assert claims["role"] == "hod"
        assert "read:cac" in claims["permissions"]
        assert "approve:cac" in claims["permissions"]
        assert "iat" in claims
        assert "exp" in claims

    def test_token_expires_after_ttl(self, rsa_keypair: tuple[bytes, bytes]) -> None:
        """Token with ttl_hours=0 should be expired immediately (or within seconds)."""
        from services.email_notifier.src.jwt_generator import generate_proposal_token

        private_pem, public_pem = rsa_keypair
        # Generate a token that expires in 0 hours (already expired)
        token = generate_proposal_token(
            proposal_id="chg_0002",
            dept="cac",
            hod_email="hod@brooker.test",
            private_key=private_pem,
            ttl_hours=0,
        )
        # Allow 1 second for execution time
        time.sleep(1)
        with pytest.raises(pyjwt.ExpiredSignatureError):
            pyjwt.decode(token, public_pem, algorithms=["RS256"])

    def test_different_dept_produces_different_permissions(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Different dept values produce different permission scopes."""
        from services.email_notifier.src.jwt_generator import generate_proposal_token

        private_pem, public_pem = rsa_keypair
        token_cac = generate_proposal_token(
            proposal_id="chg_0001",
            dept="cac",
            hod_email="hod@brooker.test",
            private_key=private_pem,
        )
        token_risk = generate_proposal_token(
            proposal_id="chg_0001",
            dept="risk",
            hod_email="risk-hod@brooker.test",
            private_key=private_pem,
        )
        claims_cac = pyjwt.decode(token_cac, public_pem, algorithms=["RS256"])
        claims_risk = pyjwt.decode(token_risk, public_pem, algorithms=["RS256"])

        assert claims_cac["permissions"] == ["read:cac", "approve:cac"]
        assert claims_risk["permissions"] == ["read:risk", "approve:risk"]
        assert claims_cac["permissions"] != claims_risk["permissions"]
