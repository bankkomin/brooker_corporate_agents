"""Routes events to downstream services with retry logic."""
import asyncio
import json
import os
import shutil

import httpx
import structlog

from src.settings import settings

logger = structlog.get_logger()

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
STAGING_BASE = os.getenv("STAGING_DIR", "/data/staging")


def move_staging_file(staging_dir: str, proposal_id: str, target: str) -> None:
    """Move a staging file from pending/ to target/ (approved/rejected)."""
    src = os.path.join(staging_dir, "pending", f"{proposal_id}.json")
    dst = os.path.join(staging_dir, target, f"{proposal_id}.json")

    if not os.path.exists(src):
        logger.warning("staging_file_not_found", proposal_id=proposal_id, path=src)
        return

    # Validate no path traversal
    real_src = os.path.realpath(src)
    real_base = os.path.realpath(staging_dir)
    if not real_src.startswith(real_base):
        logger.error("staging_path_traversal_blocked", path=src)
        return

    shutil.move(src, dst)
    logger.info("staging_file_moved", proposal_id=proposal_id, from_="pending", to=target)


def update_staging_manifest(staging_dir: str, proposal_id: str, edited_values: dict) -> None:
    """Update staging manifest with HOD-edited values before approval."""
    path = os.path.join(staging_dir, "pending", f"{proposal_id}.json")

    if not os.path.exists(path):
        logger.warning("staging_manifest_not_found", proposal_id=proposal_id)
        return

    with open(path) as f:
        manifest = json.load(f)

    manifest.update(edited_values)

    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info(
        "staging_manifest_updated",
        proposal_id=proposal_id, edits=list(edited_values.keys()),
    )


class EventRouter:
    """Routes Paperclip events to downstream services."""

    async def route_approval(
        self, proposal_id: str, decision: str, reviewer: str,
        edited_values: dict | None = None,
    ) -> None:
        """Route an approval decision to downstream services."""
        if decision == "deferred":
            logger.info("approval_deferred", proposal_id=proposal_id, reviewer=reviewer)
            return

        if decision == "approved":
            if edited_values:
                update_staging_manifest(STAGING_BASE, proposal_id, edited_values)

            payload = {"proposal_id": proposal_id}
            if edited_values:
                payload["edited_values"] = edited_values

            await self._post_with_retry(
                f"{settings.sync_back_url}/process-approved",
                payload,
                context="sync_back_approve",
            )

        if decision == "rejected":
            move_staging_file(STAGING_BASE, proposal_id, "rejected")

        await self._post_with_retry(
            f"{settings.email_notifier_url}/notify/confirmed",
            {"proposal_id": proposal_id, "event": decision, "reviewer": reviewer},
            context="email_notify_confirmed",
        )

        # Non-blocking wiki compilation (fire-and-forget)
        await self.route_wiki_compile(
            event_type="proposal_approved",
            dept_id="cac",  # TODO: extract from proposal metadata when multi-dept
            payload={"proposal_id": proposal_id, "decision": decision, "reviewer": reviewer},
        )

    async def route_escalation(self, department: str, escalation_data: dict) -> None:
        """Route an escalation to email-notifier and Slack #escalations."""
        await self._post_with_retry(
            f"{settings.email_notifier_url}/notify/escalation",
            {"department": department, **escalation_data},
            context="email_notify_escalation",
        )
        await self._post_with_retry(
            f"{settings.slack_bot_url}/post-escalation",
            {"channel": "#escalations", "department": department, **escalation_data},
            context="slack_escalation",
        )
        logger.info("escalation_routed", department=department)

        # Non-blocking wiki compilation (fire-and-forget)
        await self.route_wiki_compile(
            event_type="escalation_triggered",
            dept_id=department,
            payload=escalation_data,
        )

    async def route_proposal_notification(self, proposal_id: str, department: str) -> None:
        """Notify HOD about a new staging proposal."""
        await self._post_with_retry(
            f"{settings.email_notifier_url}/notify/proposal",
            {"proposal_id": proposal_id, "department": department},
            context="email_notify_proposal",
        )

    async def route_wiki_compile(self, event_type: str, dept_id: str, payload: dict) -> None:
        """Fire-and-forget wiki compilation — failure does NOT block approval flow."""
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{settings.wiki_compiler_url}/compile",
                    json={
                        "event_type": event_type,
                        "dept_id": dept_id,
                        "payload": payload,
                    },
                    timeout=5.0,
                )
            logger.info("wiki_compile_triggered", event_type=event_type, dept_id=dept_id)
        except Exception as exc:
            logger.warning("wiki_compile_failed", error=str(exc), event_type=event_type)

    async def _post_with_retry(self, url: str, payload: dict, context: str) -> None:
        """POST with exponential backoff retry."""
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=payload, timeout=10.0)
                    response.raise_for_status()
                logger.info("event_routed", url=url, context=context)
                return
            except Exception as exc:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "event_route_retry",
                    url=url, attempt=attempt + 1, error=str(exc), delay=delay,
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(delay)

        logger.error("event_route_failed", url=url, context=context, max_retries=MAX_RETRIES)
