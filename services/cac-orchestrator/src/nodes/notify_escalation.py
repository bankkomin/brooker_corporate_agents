"""Escalation email notification node.

Two side effects when an escalation fires:
  1. POST to email-notifier (HOD email)               — fire-and-forget
  2. INSERT into the `escalations` table via db_client — audit trail
"""
from __future__ import annotations

import httpx
import structlog

from ..tools.db_client import DBClient

logger = structlog.get_logger("cac-orchestrator.notify")


async def notify_escalation(state: dict, *, email_notifier_url: str,
                            db_client: DBClient | None = None) -> dict:
    """POST escalation to email-notifier + record to DB if triggered."""
    if not state.get("escalation_triggered"):
        return {}

    detail = state.get("escalation_detail", "")
    agent = state.get("agent_name", "")
    # dept_id was the conventional state key; older code used "dept" — accept both.
    dept = state.get("dept_id") or state.get("dept", "cac")
    interaction_id = state.get("interaction_id")
    trigger_type = state.get("escalation_rule_type", "rule_breach")
    severity = state.get("escalation_severity", "high")

    payload = {
        "escalation_detail": detail,
        "agent_name": agent,
        "query": state.get("query", ""),
        "user_id": state.get("user_id", ""),
        "channel": state.get("channel", ""),
        "dept": dept,
    }

    # Side effect A: email notification (fire-and-forget).
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{email_notifier_url}/notify/escalation", json=payload
            )
            logger.info(
                "escalation_notified",
                status=resp.status_code, agent=agent,
            )
    except Exception as exc:
        logger.warning("escalation_notify_failed", error=str(exc))

    # Side effect B: audit row in the escalations table. Best-effort —
    # never break the request flow if the DB write fails.
    if db_client is not None:
        try:
            await db_client.log_escalation(
                interaction_id=interaction_id,
                severity=severity,
                trigger_type=trigger_type,
                detail=detail,
            )
        except Exception as exc:
            logger.warning("escalation_db_write_failed", error=str(exc))

    return {}
