"""Monthly CFO report: fetch from cac-orchestrator and send via SMTP."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import httpx
import structlog
from jinja2 import Environment, FileSystemLoader

from .email_sender import send_email_with_retry

logger = structlog.get_logger("email-notifier.cfo-report")

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)


def _resolve_cfo_recipient() -> str | None:
    """Return MONTHLY_CFO_EMAIL, falling back to CAC_HOD_EMAIL.

    Returns None when neither variable is set — callers must treat this as
    'not configured' and refuse to send.
    """
    addr = os.environ.get("MONTHLY_CFO_EMAIL", "").strip()
    if addr:
        return addr
    addr = os.environ.get("CAC_HOD_EMAIL", "").strip()
    return addr or None


async def _fetch_monthly_report(cac_url: str) -> dict:
    """Call GET /report/monthly-cfo on the cac-orchestrator and return the JSON body.

    Args:
        cac_url: Base URL of the cac-orchestrator service.

    Raises:
        httpx.HTTPStatusError: if the orchestrator returns a non-2xx response.
        httpx.RequestError: on network failure.
    """
    url = cac_url.rstrip("/") + "/report/monthly-cfo"
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    data: dict = resp.json()
    logger.info(
        "cfo_report.fetched",
        month=data.get("month"),
        source_count=len(data.get("sources", [])),
    )
    return data


async def send_monthly_cfo_report(
    *,
    pool=None,
    dry_run: bool = False,
) -> dict:
    """Fetch the monthly CAC report and email it to the CFO recipient.

    This is the single entry-point called both by the HTTP endpoint and the
    APScheduler monthly job.

    Args:
        pool: asyncpg connection pool for DB logging (optional; skipped if None).
        dry_run: When True, fetches the report but does NOT send the email.
                 Returns ``{"status": "dry_run", ...}`` instead.

    Returns:
        A dict with keys: status, recipient (or None), month, source_count.

    Raises:
        ValueError: when neither MONTHLY_CFO_EMAIL nor CAC_HOD_EMAIL is set.
        httpx.HTTPStatusError / httpx.RequestError: on orchestrator failure.
    """
    recipient = _resolve_cfo_recipient()
    if not recipient:
        logger.warning(
            "cfo_report.no_recipient",
            message=(
                "MONTHLY_CFO_EMAIL and CAC_HOD_EMAIL are both unset. "
                "Set MONTHLY_CFO_EMAIL to enable monthly CFO emails."
            ),
        )
        raise ValueError(
            "CFO report recipient not configured. "
            "Set MONTHLY_CFO_EMAIL (or CAC_HOD_EMAIL as fallback) in the environment."
        )

    cac_url = os.environ.get("CAC_ORCHESTRATOR_URL", "http://cac-orchestrator:3001")
    report_data = await _fetch_monthly_report(cac_url)

    month: str = report_data.get("month", date.today().strftime("%B %Y"))
    report_text: str = report_data.get("report", "(report unavailable)")
    sources: list[dict] = report_data.get("sources", [])
    prepared_date: str = date.today().isoformat()

    if dry_run:
        logger.info(
            "cfo_report.dry_run",
            recipient=recipient,
            month=month,
            source_count=len(sources),
        )
        return {
            "status": "dry_run",
            "recipient": recipient,
            "month": month,
            "source_count": len(sources),
            "report_preview": report_text[:500],
        }

    subject = f"CAC Monthly Report — {month}"
    template = _jinja_env.get_template("cfo_report.html")
    html_body = template.render(
        month=month,
        report=report_text,
        sources=sources,
        prepared_date=prepared_date,
    )

    await send_email_with_retry(
        to=recipient,
        subject=subject,
        html_body=html_body,
        pool=pool,
        event_type="monthly_cfo_report",
        proposal_id=None,
        dept="cac",
    )

    logger.info(
        "cfo_report.sent",
        recipient=recipient,
        month=month,
        source_count=len(sources),
    )
    return {
        "status": "sent",
        "recipient": recipient,
        "month": month,
        "source_count": len(sources),
    }
