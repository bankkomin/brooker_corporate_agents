"""JWT authentication middleware for the gateway service.

Validates RS256 JSON Web Tokens and enforces department-level access control.
"""
from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import jwt
import structlog
from fastapi import Request

logger = structlog.get_logger(__name__)

_DEFAULT_PUBLIC_KEY_PATH = "secrets/jwt_public.pem"


@dataclass(frozen=True)
class JWTClaims:
    """Decoded, validated claims extracted from a JWT.

    Attributes:
        sub: Subject identifier (employee/user ID).
        dept: Department the token was issued for.
        role: Role of the subject within the department.
        permissions: Sequence of permission strings granted to the subject.
        proposal_id: Optional proposal ID associated with the request.
    """

    sub: str
    dept: str
    role: str
    permissions: Sequence[str]
    proposal_id: str | None


class AuthError(Exception):
    """Raised when JWT validation or access-control checks fail.

    Attributes:
        code: Machine-readable error code (e.g. TOKEN_EXPIRED, DEPT_MISMATCH).
        message: Human-readable description of the error.
        status_code: HTTP status code to return to the caller.
    """

    def __init__(self, code: str, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _load_public_key() -> bytes:
    """Load the RS256 public key from the configured path.

    Reads the path from the ``JWT_PUBLIC_KEY_PATH`` environment variable,
    falling back to ``secrets/jwt_public.pem`` when the variable is absent.

    Returns:
        Raw PEM bytes of the public key.

    Raises:
        AuthError: If the file cannot be read.
    """
    path = os.getenv("JWT_PUBLIC_KEY_PATH", _DEFAULT_PUBLIC_KEY_PATH)
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError as exc:
        logger.warning("jwt_public_key_load_failed", path=path, error=str(exc))
        raise AuthError("CONFIG_ERROR", f"Cannot read public key from {path}") from exc


def validate_jwt(token: str, public_key: bytes | None = None) -> JWTClaims:
    """Decode and validate an RS256 JWT.

    Args:
        token: Raw JWT string (header.payload.signature).
        public_key: PEM-encoded RS256 public key bytes. When *None* the key is
            loaded from disk via :func:`_load_public_key`.

    Returns:
        :class:`JWTClaims` populated from the verified token payload.

    Raises:
        AuthError: With code ``TOKEN_EXPIRED`` if the token has expired, or
            ``TOKEN_INVALID`` for any other validation failure (bad signature,
            wrong algorithm, malformed structure, missing required claims, …).
    """
    key: bytes = public_key if public_key is not None else _load_public_key()

    try:
        payload: dict = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options={"require": ["sub", "dept", "role", "exp", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        logger.warning("jwt_expired", error=str(exc))
        raise AuthError("TOKEN_EXPIRED", "Token has expired") from exc
    except jwt.PyJWTError as exc:
        logger.warning("jwt_invalid", error=str(exc))
        raise AuthError("TOKEN_INVALID", f"Token validation failed: {exc}") from exc

    try:
        claims = JWTClaims(
            sub=str(payload["sub"]),
            dept=str(payload["dept"]),
            role=str(payload["role"]),
            permissions=list(payload.get("permissions", [])),
            proposal_id=payload.get("proposal_id"),
        )
    except (KeyError, TypeError) as exc:
        logger.warning("jwt_claims_parse_failed", error=str(exc))
        raise AuthError("TOKEN_INVALID", f"Missing required claim: {exc}") from exc

    return claims


_DEPARTMENTS_PATH = os.environ.get(
    "DEPARTMENTS_JSON_PATH",
    str(Path(__file__).resolve().parents[3] / "config" / "departments.json"),
)


@lru_cache(maxsize=1)
def _load_global_access_roles() -> dict[str, dict[str, list[str]]]:
    """Load globalAccess.roles from departments.json. Cached after first load."""
    try:
        with open(_DEPARTMENTS_PATH) as f:
            data = json.load(f)
        return data.get("globalAccess", {}).get("roles", {})
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("departments_json_load_failed", path=_DEPARTMENTS_PATH, error=str(exc))
        return {}


def check_dept_access(claims: JWTClaims, resource_dept: str) -> None:
    """Assert that claims grant access to resource_dept.

    Access is granted if:
    1. claims.dept matches resource_dept (same department), OR
    2. claims.role appears in globalAccess.roles and resource_dept is in canRead
       (or canRead contains "*")

    Args:
        claims: Validated JWT claims for the requesting user.
        resource_dept: Department identifier of the resource being accessed.

    Raises:
        AuthError: With code ``DEPT_MISMATCH`` and HTTP 403 when neither
            condition is satisfied.
    """
    # Same department always passes
    if claims.dept == resource_dept:
        return

    # Check globalAccess roles from departments.json
    global_roles = _load_global_access_roles()
    role_config = global_roles.get(claims.role)
    if role_config is not None:
        can_read = role_config.get("canRead", [])
        if "*" in can_read or resource_dept in can_read:
            return

    logger.warning(
        "dept_access_denied",
        subject=claims.sub,
        claims_dept=claims.dept,
        resource_dept=resource_dept,
        role=claims.role,
    )
    raise AuthError(
        "DEPT_MISMATCH",
        f"Department '{claims.dept}' cannot access resource in '{resource_dept}'",
        status_code=403,
    )


def extract_claims(request: Request) -> JWTClaims:
    """Extract and validate JWT from the Authorization header."""
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token:
        raise AuthError("TOKEN_MISSING", "Authorization header required", status_code=401)
    return validate_jwt(token)
