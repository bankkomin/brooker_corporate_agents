"""Authentication middleware for Paperclip service."""
import structlog
from fastapi import HTTPException, Request

from src.settings import settings

logger = structlog.get_logger()

PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


async def verify_api_key(request: Request):
    """Verify API key for non-public endpoints."""
    if request.url.path in PUBLIC_PATHS:
        return

    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    if api_key != settings.paperclip_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


async def verify_webhook_auth(request: Request):
    """Verify authentication for webhook endpoints.

    Stage 7: uses API key. JWT signature validation added when
    approval-ui JWT signing is implemented.
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != settings.paperclip_api_key:
        raise HTTPException(status_code=401, detail="Webhook authentication failed")
