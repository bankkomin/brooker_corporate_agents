"""Email-notifier service — JWT generation + SMTP sending."""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

import json
import os
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Request

from .email_sender import send_confirmed, send_escalation, send_proposal_notification, send_reminder
from .jwt_generator import generate_proposal_token
from .models import (
    ConfirmedNotification,
    EscalationNotification,
    ProposalNotification,
    ReminderNotification,
)
from .scheduler import check_overdue_proposals

logger = structlog.get_logger("email-notifier")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://agents:changeme@localhost:5432/corporate_agents",
)

# Load departments config for HOD email resolution
_DEPARTMENTS_PATH = os.environ.get(
    "DEPARTMENTS_JSON_PATH",
    str(Path(__file__).resolve().parents[3] / "config" / "departments.json"),
)
_departments: dict | None = None


def _load_departments() -> dict:
    """Load and cache departments.json."""
    global _departments  # noqa: PLW0603
    if _departments is None:
        try:
            with open(_DEPARTMENTS_PATH) as f:
                _departments = json.load(f)
        except FileNotFoundError:
            logger.warning("departments.json not found", path=_DEPARTMENTS_PATH)
            _departments = {"departments": {}}
    return _departments


def _resolve_hod_email(dept: str) -> str | None:
    """Resolve the first HOD email for a department from departments.json."""
    depts = _load_departments()
    dept_config = depts.get("departments", {}).get(dept, {})
    hod_emails = dept_config.get("escalation", {}).get("hodEmails", [])
    if hod_emails:
        # hodEmails may contain env var placeholders like ${CAC_HOD_EMAIL}
        email = hod_emails[0]
        if email.startswith("${") and email.endswith("}"):
            env_var = email[2:-1]
            return os.environ.get(env_var)
        return email
    return None


def _smtp_configured() -> bool:
    """Return True if SMTP_HOST is set in the environment."""
    return bool(os.environ.get("SMTP_HOST"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create and tear down the asyncpg connection pool and APScheduler."""
    logger.info("email_notifier.startup")

    # Warn loudly if email delivery is disabled — proposals will accumulate
    # silently with no HOD notification until this is fixed.
    smtp_enabled = _smtp_configured()
    app.state.smtp_enabled = smtp_enabled
    if not smtp_enabled:
        logger.warning(
            "email_notifier.smtp_disabled",
            message=(
                "SMTP_HOST is not configured. All email notifications will be "
                "silently dropped. HODs will NOT receive proposal or escalation "
                "emails until SMTP_HOST (and optionally SMTP_PORT, SMTP_USER, "
                "SMTP_PASSWORD, SMTP_FROM) are set."
            ),
        )

    try:
        app.state.db_pool = await asyncpg.create_pool(
            DATABASE_URL, min_size=1, max_size=3
        )
        logger.info("email_notifier.db_pool_ready")
    except Exception as exc:
        logger.warning("email_notifier.db_pool_failed", error=str(exc))
        app.state.db_pool = None

    # Start APScheduler for 24h overdue proposal reminders
    scheduler = AsyncIOScheduler()
    if app.state.db_pool is not None:
        scheduler.add_job(
            check_overdue_proposals,
            "interval",
            hours=1,
            args=[app.state.db_pool, _resolve_hod_email],
            id="overdue_reminder",
            name="24h overdue proposal reminder",
        )
        scheduler.start()
        logger.info("email_notifier.scheduler_started")
    else:
        logger.warning("email_notifier.scheduler_skipped", reason="no db pool")

    yield

    scheduler.shutdown(wait=False)
    if getattr(app.state, "db_pool", None):
        await app.state.db_pool.close()
    logger.info("email_notifier.shutdown")


app = FastAPI(
    title="email-notifier",
    version="0.3.0",
    description="Email notification service",
    lifespan=lifespan,
)


@app.get("/health")
async def health(request: Request) -> dict:
    smtp_enabled = getattr(request.app.state, "smtp_enabled", _smtp_configured())
    return {
        "status": "healthy",
        "service": "email-notifier",
        "smtp_configured": smtp_enabled,
        "email_delivery": "enabled" if smtp_enabled else "disabled — set SMTP_HOST to enable",
    }


@app.post("/notify/escalation")
async def notify_escalation(payload: EscalationNotification, request: Request) -> dict:
    nid = str(uuid.uuid4())[:8]

    # Build recipient list: dept HOD + CEO
    recipients: list[str] = []
    hod_email = _resolve_hod_email(payload.dept)
    if hod_email:
        recipients.append(hod_email)

    ceo_email = os.environ.get("CEO_EMAIL", "")
    if ceo_email and ceo_email not in recipients:
        recipients.append(ceo_email)

    if not recipients:
        logger.warning("no_escalation_recipients", dept=payload.dept)
        raise HTTPException(
            status_code=422,
            detail=f"No escalation recipients configured for department '{payload.dept}'",
        )

    pool = getattr(request.app.state, "db_pool", None)
    await send_escalation(payload=payload, recipients=recipients, pool=pool)

    logger.info(
        "escalation_sent",
        id=nid,
        severity=payload.severity,
        agent=payload.agent_name,
        recipients=recipients,
    )
    return {"status": "sent", "notification_id": nid, "recipients": len(recipients)}


@app.post("/notify/proposal")
async def notify_proposal(payload: ProposalNotification, request: Request) -> dict:
    nid = str(uuid.uuid4())[:8]

    # Resolve HOD email from departments config
    hod_email = _resolve_hod_email(payload.dept)
    if not hod_email:
        logger.warning(
            "no_hod_email_configured",
            dept=payload.dept,
            proposal_id=payload.proposal_id,
        )
        raise HTTPException(
            status_code=422,
            detail=f"No HOD email configured for department '{payload.dept}'",
        )

    # Generate JWT for approval deep-link
    token = generate_proposal_token(
        proposal_id=payload.proposal_id,
        dept=payload.dept,
        hod_email=hod_email,
    )

    # Send email with retry + DB logging (gracefully degrades if SMTP not configured)
    pool = getattr(request.app.state, "db_pool", None)
    await send_proposal_notification(
        proposal=payload,
        token=token,
        hod_email=hod_email,
        pool=pool,
    )

    logger.info(
        "proposal_sent",
        id=nid,
        proposal_id=payload.proposal_id,
        dept=payload.dept,
        hod_email=hod_email,
    )
    return {"status": "sent", "notification_id": nid}


@app.post("/notify/reminder")
async def notify_reminder(payload: ReminderNotification, request: Request) -> dict:
    nid = str(uuid.uuid4())[:8]
    token = generate_proposal_token(
        proposal_id=payload.proposal_id,
        dept=payload.dept,
        hod_email=payload.recipient,
    )
    pool = getattr(request.app.state, "db_pool", None)
    await send_reminder(
        proposal_id=payload.proposal_id,
        recipient=payload.recipient,
        token=token,
        pool=pool,
    )
    logger.info("reminder_sent", id=nid, proposal_id=payload.proposal_id)
    return {"status": "sent", "notification_id": nid}


@app.post("/notify/confirmed")
async def notify_confirmed(payload: ConfirmedNotification, request: Request) -> dict:
    nid = str(uuid.uuid4())[:8]

    # Resolve recipient: use explicit if provided, else look up HOD from dept
    recipient = payload.recipient
    if not recipient:
        recipient = _resolve_hod_email(payload.dept)
    if not recipient:
        logger.warning(
            "no_recipient_for_confirmed",
            dept=payload.dept,
            proposal_id=payload.proposal_id,
        )
        raise HTTPException(
            status_code=422,
            detail=f"No recipient configured for department '{payload.dept}'",
        )

    pool = getattr(request.app.state, "db_pool", None)
    await send_confirmed(
        proposal_id=payload.proposal_id,
        decision=payload.decision,
        recipient=recipient,
        pool=pool,
    )

    logger.info(
        "confirmed_sent",
        id=nid,
        proposal_id=payload.proposal_id,
        recipient=recipient,
    )
    return {"status": "sent", "notification_id": nid}
