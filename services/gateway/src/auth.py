"""JWT authentication middleware for the gateway service.

Validates two token types:
1. RS256 JWTs — issued by the CAC system (approval-ui email links).
2. HS256 JWTs — issued by brooker-internal-company (employee login).

Both are normalised into JWTClaims.  For Brooker tokens the caller's
permissions are resolved from the agent_access table.
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
        sub: Subject identifier (employee UUID or legacy user ID).
        dept: Department the token was issued for.
        role: Role of the subject within the department.
        permissions: Sequence of permission strings granted to the subject.
        proposal_id: Optional proposal ID associated with the request.
        email: Employee email (present for Brooker tokens).
        source: Which JWT issuer: "cac" or "brooker".
    """

    sub: str
    dept: str
    role: str
    permissions: Sequence[str]
    proposal_id: str | None
    email: str | None = None
    source: str = "cac"


class AuthError(Exception):
    """Raised when JWT validation or access-control checks fail."""

    def __init__(self, code: str, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Key loading
# ---------------------------------------------------------------------------

def _load_public_key() -> bytes | None:
    """Load the RS256 public key. Returns None if unavailable."""
    path = os.getenv("JWT_PUBLIC_KEY_PATH", _DEFAULT_PUBLIC_KEY_PATH)
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError as exc:
        logger.warning("jwt_public_key_load_failed", path=path, error=str(exc))
        return None


def _get_brooker_secret() -> str | None:
    """Return the HS256 secret shared with brooker-internal-company."""
    return os.getenv("BROOKER_JWT_SECRET")


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

def _try_rs256(token: str) -> JWTClaims | None:
    """Attempt RS256 (CAC-issued) validation.  Returns None on failure."""
    public_key = _load_public_key()
    if public_key is None:
        return None
    try:
        payload: dict = jwt.decode(
            token, public_key, algorithms=["RS256"],
            options={"require": ["sub", "dept", "role", "exp", "iat"]},
        )
        return JWTClaims(
            sub=str(payload["sub"]),
            dept=str(payload["dept"]),
            role=str(payload["role"]),
            permissions=list(payload.get("permissions", [])),
            proposal_id=payload.get("proposal_id"),
            source="cac",
        )
    except jwt.PyJWTError:
        return None


def _try_hs256(token: str) -> JWTClaims | None:
    """Attempt HS256 (Brooker-issued) validation.  Returns None on failure."""
    secret = _get_brooker_secret()
    if not secret:
        return None
    try:
        payload: dict = jwt.decode(
            token, secret, algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
        return JWTClaims(
            sub=str(payload["sub"]),
            dept=str(payload.get("departmentSlug", "")),
            role=str(payload.get("role", "employee")),
            permissions=[],          # resolved later from agent_access
            proposal_id=None,
            email=payload.get("email"),
            source="brooker",
        )
    except jwt.PyJWTError:
        return None


def validate_jwt(token: str, public_key: bytes | None = None) -> JWTClaims:
    """Decode and validate a JWT — tries RS256 first, then HS256.

    Args:
        token: Raw JWT string.
        public_key: Optional PEM key override (for tests).

    Returns:
        JWTClaims on success.

    Raises:
        AuthError on any failure.
    """
    # 1. Try RS256 (CAC system tokens — approval links, email-notifier)
    if public_key is not None:
        # Explicit key passed (tests / legacy call-sites)
        try:
            payload: dict = jwt.decode(
                token, public_key, algorithms=["RS256"],
                options={"require": ["sub", "dept", "role", "exp", "iat"]},
            )
            return JWTClaims(
                sub=str(payload["sub"]),
                dept=str(payload["dept"]),
                role=str(payload["role"]),
                permissions=list(payload.get("permissions", [])),
                proposal_id=payload.get("proposal_id"),
                source="cac",
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("TOKEN_EXPIRED", "Token has expired") from exc
        except jwt.PyJWTError as exc:
            raise AuthError("TOKEN_INVALID", f"Token validation failed: {exc}") from exc

    # Auto-detect: try RS256, then HS256
    claims = _try_rs256(token)
    if claims is not None:
        return claims

    claims = _try_hs256(token)
    if claims is not None:
        return claims

    raise AuthError("TOKEN_INVALID", "Token could not be validated with any known method")


# ---------------------------------------------------------------------------
# Agent access resolution (for Brooker tokens)
# ---------------------------------------------------------------------------

async def resolve_agent_permissions(
    pool, employee_id: str | None, email: str | None, department_name: str = "cac",
) -> dict:
    """Look up agent_access row for an employee.

    Tries employee_id first, falls back to email.
    Returns a dict of permissions or raises AuthError if no access.
    """
    if pool is None:
        raise AuthError("CONFIG_ERROR", "Database pool not available", 500)

    async with pool.acquire() as conn:
        row = None

        if employee_id:
            row = await conn.fetchrow(
                "SELECT can_query, can_approve, can_view_proposals, can_escalate "
                "FROM agent_access "
                "WHERE employee_id = $1 AND department_name = $2 AND revoked_at IS NULL",
                employee_id, department_name,
            )

        if row is None and email:
            row = await conn.fetchrow(
                "SELECT can_query, can_approve, can_view_proposals, can_escalate "
                "FROM agent_access "
                "WHERE employee_email = $1 AND department_name = $2 AND revoked_at IS NULL",
                email, department_name,
            )

    if row is None:
        raise AuthError(
            "NO_AGENT_ACCESS",
            f"No agent access granted for department '{department_name}'",
            status_code=403,
        )

    return dict(row)


def permissions_from_access(access: dict) -> list[str]:
    """Convert agent_access booleans to permission strings."""
    perms = []
    if access.get("can_query"):
        perms.append("query")
    if access.get("can_approve"):
        perms.append("approve")
    if access.get("can_view_proposals"):
        perms.append("view_proposals")
    if access.get("can_escalate"):
        perms.append("escalate")
    return perms


# ---------------------------------------------------------------------------
# Department RBAC
# ---------------------------------------------------------------------------

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
       (or canRead contains "*"), OR
    3. Token is from Brooker (agent_access already checked upstream).
    """
    # Brooker tokens: agent_access was already verified by the middleware
    if claims.source == "brooker":
        return

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
