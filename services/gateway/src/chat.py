"""Chat endpoint — website users ask questions to the CAC AI agent.

Replaces Slack as the entry point for queries.  Validates agent_access
permissions (can_query) and proxies the request to cac-orchestrator.
"""
from __future__ import annotations

import asyncio
import contextlib
import os

import httpx
import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.gateway.src.auth import AuthError, extract_claims

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

CAC_ORCHESTRATOR_URL = os.getenv("CAC_ORCHESTRATOR_URL", "http://localhost:3001")

# Retry settings for orchestrator calls (handles slow startup)
_ORCHESTRATOR_MAX_RETRIES = 3
_ORCHESTRATOR_RETRY_DELAY = 2.0  # seconds, doubles each retry


class ChatRequest(BaseModel):
    """Question from the website user."""

    message: str
    thread_id: str | None = None  # for conversation continuity


class ChatResponse(BaseModel):
    """Response returned to the website."""

    answer: str
    sources: list[dict] = []
    confidence: str = "Low"
    proposal_id: str | None = None
    escalation: bool = False
    processing_time_ms: int = 0


@router.post("")
async def chat(request: Request, body: ChatRequest) -> JSONResponse:
    """Send a question to the CAC AI agent and return the answer.

    Requires: agent_access.can_query = true for the caller.
    """
    claims = extract_claims(request)

    # Check can_query permission
    agent_perms = getattr(request.state, "agent_permissions", None)
    if claims.source == "brooker" and (agent_perms is None or "query" not in agent_perms):
        raise AuthError("NO_QUERY_ACCESS", "You do not have query access", 403)

    # Build orchestrator request
    user_id = claims.email or claims.sub
    thread_id = body.thread_id or f"web:{user_id}"

    orchestrator_payload = {
        "query": body.message,
        "user_id": user_id,
        "channel": "web",
        "thread_ts": thread_id,
    }

    last_exc: Exception | None = None
    for attempt in range(_ORCHESTRATOR_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{CAC_ORCHESTRATOR_URL}/query",
                    json=orchestrator_payload,
                )
                resp.raise_for_status()
                data = resp.json()
            break  # success
        except httpx.TimeoutException:
            logger.error("orchestrator_timeout", user=user_id)
            return JSONResponse(
                status_code=504,
                content={"error": "AI agent did not respond in time", "code": "TIMEOUT"},
            )
        except httpx.HTTPStatusError as exc:
            detail = ""
            with contextlib.suppress(Exception):
                detail = exc.response.text[:500]
            logger.error(
                "orchestrator_error",
                status=exc.response.status_code,
                detail=detail,
                user=user_id,
            )
            return JSONResponse(
                status_code=502,
                content={
                    "error": "AI agent returned an error",
                    "code": "ORCHESTRATOR_ERROR",
                    "detail": detail or None,
                },
            )
        except Exception as exc:
            last_exc = exc
            delay = _ORCHESTRATOR_RETRY_DELAY * (2 ** attempt)
            logger.warning(
                "orchestrator_unreachable_retrying",
                error=str(exc), attempt=attempt + 1, retry_in=delay, user=user_id,
            )
            if attempt < _ORCHESTRATOR_MAX_RETRIES - 1:
                await asyncio.sleep(delay)
    else:
        logger.error("orchestrator_unreachable", error=str(last_exc), user=user_id)
        return JSONResponse(
            status_code=503,
            content={"error": "AI agent is unavailable", "code": "ORCHESTRATOR_DOWN"},
        )

    logger.info(
        "chat_query_processed",
        user=user_id,
        confidence=data.get("confidence"),
        processing_ms=data.get("processing_time_ms"),
    )

    return JSONResponse(content={
        "answer": data.get("answer", ""),
        "sources": data.get("sources", []),
        "confidence": data.get("confidence", "Low"),
        "proposal_id": data.get("staging_proposal_id"),
        "escalation": data.get("escalation_triggered", False),
        "processing_time_ms": data.get("processing_time_ms", 0),
    })


@router.get("/history")
async def chat_history(request: Request, limit: int = 20) -> JSONResponse:
    """Return recent chat interactions for the current user."""
    claims = extract_claims(request)
    pool = request.app.state.db_pool

    user_id = claims.email or claims.sub

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, created_at, query, intent, response, confidence, "
            "       sources_count, escalation, staging_proposal_id, processing_ms "
            "FROM agent_interactions "
            "WHERE user_id = $1 "
            "ORDER BY created_at DESC LIMIT $2",
            user_id, limit,
        )

    interactions = []
    for r in rows:
        interactions.append({
            "id": r["id"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "query": r["query"],
            "intent": r["intent"],
            "response": r["response"],
            "confidence": float(r["confidence"]) if r["confidence"] is not None else None,
            "sources_count": r["sources_count"],
            "escalation": r["escalation"],
            "proposal_id": r["staging_proposal_id"],
            "processing_ms": r["processing_ms"],
        })

    return JSONResponse(content={"interactions": interactions, "total": len(interactions)})
