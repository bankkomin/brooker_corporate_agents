"""Generate RS256 JWTs for proposal deep-links."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import jwt

_private_key: bytes | None = None


def _load_private_key() -> bytes:
    """Load RSA private key from file path specified in JWT_PRIVATE_KEY_PATH env var."""
    global _private_key  # noqa: PLW0603
    if _private_key is None:
        key_path = os.environ.get("JWT_PRIVATE_KEY_PATH", "secrets/jwt_private.pem")
        with open(key_path, "rb") as f:
            _private_key = f.read()
    return _private_key


def generate_proposal_token(
    proposal_id: str,
    dept: str,
    hod_email: str,
    private_key: bytes | None = None,
    ttl_hours: int = 24,
) -> str:
    """Generate an RS256 JWT for a proposal approval deep-link.

    Args:
        proposal_id: The staging proposal ID (e.g. "chg_0001").
        dept: Department code (e.g. "cac").
        hod_email: HOD email address (becomes the JWT subject).
        private_key: RSA private key PEM bytes. If None, loads from env path.
        ttl_hours: Token time-to-live in hours.

    Returns:
        Encoded JWT string.
    """
    key = private_key or _load_private_key()
    now = datetime.now(UTC)
    payload = {
        "sub": hod_email,
        "dept": dept,
        "proposal_id": proposal_id,
        "role": "hod",
        "permissions": [f"read:{dept}", f"approve:{dept}"],
        "iat": now,
        "exp": now + timedelta(hours=ttl_hours),
    }
    return jwt.encode(payload, key, algorithm="RS256")
