"""slack-bot service — FastAPI + Slack Bolt (HTTP mode)."""
from __future__ import annotations

import contextlib
from datetime import UTC, datetime

import httpx
import structlog
from fastapi import FastAPI, Request, Response
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp

from .clients import OrchestratorClient, RAGIngestionClient
from .config import SlackBotSettings
from .events import register_event_handlers
from .models import PostEscalationRequest

logger = structlog.get_logger("slack-bot")

settings = SlackBotSettings()


# ── Bolt app ──────────────────────────────────────────────────────────

bolt_app = AsyncApp(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret,
)

bolt_handler = AsyncSlackRequestHandler(bolt_app)


# ── Lifespan ──────────────────────────────────────────────────────────

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Create shared httpx client and register event handlers."""
    http_client = httpx.AsyncClient(timeout=settings.http_timeout_seconds)
    app.state.http_client = http_client

    rag_client = RAGIngestionClient(http=http_client, base_url=settings.rag_ingestion_url)
    orch_client = OrchestratorClient(
        http=http_client,
        base_url=settings.cac_orchestrator_url,
        enabled=settings.orchestrator_enabled,
    )
    app.state.rag_client = rag_client
    app.state.orch_client = orch_client

    register_event_handlers(bolt_app, rag_client, orch_client, settings.slack_bot_token)

    logger.info("slack-bot.startup", port=3003)
    yield
    await http_client.aclose()
    logger.info("slack-bot.shutdown")


# ── FastAPI app ───────────────────────────────────────────────────────

app = FastAPI(
    title="Slack Bot",
    version="0.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)


@app.post("/slack/events")
async def slack_events(req: Request) -> Response:
    """Bolt request handler — all Slack Events API traffic."""
    return await bolt_handler.handle(req)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "slack-bot",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.post("/post-escalation")
async def post_escalation(body: PostEscalationRequest) -> dict:
    """Post an escalation alert to the #escalations Slack channel.

    Called by paperclip event_router when an agent triggers an escalation.
    """
    severity_emoji = ":rotating_light:" if body.severity.lower() == "high" else ":warning:"
    text = (
        f"{severity_emoji} *Escalation — {body.department.upper()}*\n"
        f"*Agent:* {body.agent_name or 'unknown'}\n"
        f"*Severity:* {body.severity}\n"
        f"*Detail:* {body.escalation_detail}"
    )
    channel = settings.escalations_channel_id

    try:
        await bolt_app.client.chat_postMessage(
            channel=channel,
            text=text,
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text},
                }
            ],
        )
        logger.info(
            "slack-bot.escalation_posted",
            channel=channel,
            department=body.department,
            severity=body.severity,
        )
        return {"status": "posted", "channel": channel}
    except Exception as exc:
        logger.error("slack-bot.escalation_post_failed", error=str(exc))
        raise


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3003)
