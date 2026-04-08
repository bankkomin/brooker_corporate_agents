"""Standardized error response model and FastAPI exception handlers for the gateway."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.gateway.src.auth import AuthError


class ErrorResponse(BaseModel):
    """Standardized error response body returned by the gateway on failures.

    Attributes:
        error: Short human-readable summary of the error type.
        code: Machine-readable error code (e.g. TOKEN_EXPIRED, DEPT_MISMATCH).
        detail: Optional extended description or diagnostic information.
    """

    error: str
    code: str
    detail: str | None = None


async def auth_error_handler(request: Request, exc: AuthError) -> JSONResponse:
    """FastAPI exception handler that serialises :class:`AuthError` to JSON.

    Register with::

        app.add_exception_handler(AuthError, auth_error_handler)

    Args:
        request: The incoming FastAPI request (unused but required by FastAPI).
        exc: The :class:`AuthError` instance raised during request processing.

    Returns:
        A :class:`~fastapi.responses.JSONResponse` containing an
        :class:`ErrorResponse` payload with the appropriate HTTP status code.
    """
    body = ErrorResponse(
        error=exc.message,
        code=exc.code,
        detail=None,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=body.model_dump(),
    )
