"""Reverse proxy for Slack Events API.

Slack signs the raw request body with SLACK_SIGNING_SECRET, so this proxy
forwards the body bytes verbatim and preserves the X-Slack-* headers.
Re-serializing JSON would break the signature check on slack-bot.
"""
from __future__ import annotations

import os
from typing import Final

import httpx
import structlog
from fastapi import APIRouter, Request, Response

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["slack"])

SLACK_BOT_URL: Final[str] = os.getenv("SLACK_BOT_URL", "http://slack-bot:3003").rstrip("/")
_PROXY_TIMEOUT_SECONDS: Final[float] = 10.0

# Headers we strip when forwarding (hop-by-hop or host-specific).
_DROP_REQUEST_HEADERS = {"host", "content-length", "connection"}
_DROP_RESPONSE_HEADERS = {"content-encoding", "transfer-encoding", "connection"}


@router.post("/slack/events")
async def slack_events_proxy(request: Request) -> Response:
    body = await request.body()
    fwd_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in _DROP_REQUEST_HEADERS
    }

    async with httpx.AsyncClient(timeout=_PROXY_TIMEOUT_SECONDS) as client:
        try:
            upstream = await client.post(
                f"{SLACK_BOT_URL}/slack/events",
                content=body,
                headers=fwd_headers,
            )
        except httpx.RequestError as exc:
            logger.error("slack_proxy_upstream_unreachable", error=str(exc))
            return Response(status_code=502, content=b"slack-bot unreachable")

    resp_headers = {
        k: v for k, v in upstream.headers.items() if k.lower() not in _DROP_RESPONSE_HEADERS
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=resp_headers,
        media_type=upstream.headers.get("content-type"),
    )
