"""Routes events to downstream services with retry logic."""
import asyncio
import json
import os
import shutil
from pathlib import Path

import httpx
import structlog

from src.settings import settings

logger = structlog.get_logger()

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
STAGING_BASE = os.getenv("STAGING_PATH", "/data/staging")

# departments.json is mounted/copied into the container at this path
_DEPARTMENTS_JSON_PATH = os.getenv(
    "DEPARTMENTS_JSON_PATH",
    str(Path(__file__).resolve().parents[4] / "config" / "departments.json"),
)

# Lazily built agent-to-department mapping: {"liquidity": "cac", "recruitment": "hr", ...}
_agent_dept_map: dict[str, str] | None = None


def _build_agent_dept_map() -> dict[str, str]:
    """Build an agent-name → department-id lookup from departments.json.

    Returns an empty dict if the file cannot be read, so the caller can
    fall back gracefully.
    """
    try:
        with open(_DEPARTMENTS_JSON_PATH) as f:
            data = json.load(f)
        mapping: dict[str, str] = {}
        for dept_id, dept_cfg in data.get("departments", {}).items():
            for agent_name in dept_cfg.get("agents", []):
                mapping[agent_name] = dept_id
        logger.debug("agent_dept_map_built", entries=len(mapping))
        return mapping
    except Exception as exc:
        logger.warning("agent_dept_map_load_failed", error=str(exc), path=_DEPARTMENTS_JSON_PATH)
        return {}


def _agent_dept_map_cached() -> dict[str, str]:
    """Return the cached agent→department map, building it on first call."""
    global _agent_dept_map  # noqa: PLW0603
    if _agent_dept_map is None:
        _agent_dept_map = _build_agent_dept_map()
    return _agent_dept_map


def _resolve_dept_from_proposal(proposal_id: str) -> str:
    """Determine the department for a proposal by inspecting its staging manifest.

    Resolution order:
    1. Read {STAGING_BASE}/pending/{proposal_id}/manifest.json and extract ``agent``.
    2. Map agent name → department via departments.json.
    3. Fall back to ``"cac"`` if the manifest is missing or the agent is unknown.

    The fallback ensures the approval flow is never blocked by a missing mapping.
    """
    # Try the directory-per-proposal layout written by staging_writer.py
    manifest_path = os.path.join(STAGING_BASE, "pending", proposal_id, "manifest.json")
    # Also try the flat-file layout (legacy / sync-back path)
    flat_path = os.path.join(STAGING_BASE, "pending", f"{proposal_id}.json")

    manifest: dict = {}
    for candidate in (manifest_path, flat_path):
        if os.path.exists(candidate):
            try:
                with open(candidate) as f:
                    manifest = json.load(f)
                break
            except Exception as exc:
                logger.warning(
                    "staging_manifest_read_failed",
                    path=candidate, error=str(exc),
                )

    if not manifest:
        logger.warning(
            "dept_resolution_manifest_missing",
            proposal_id=proposal_id,
            fallback="cac",
        )
        return "cac"

    agent_name: str = manifest.get("agent", "")
    dept = _agent_dept_map_cached().get(agent_name, "")
    if dept:
        logger.debug(
            "dept_resolved_from_agent",
            proposal_id=proposal_id, agent=agent_name, dept=dept,
        )
        return dept

    logger.warning(
        "dept_resolution_agent_unknown",
        proposal_id=proposal_id, agent=agent_name, fallback="cac",
    )
    return "cac"


async def move_staging_file(staging_dir: str, proposal_id: str, target: str) -> None:
    """Move a staging proposal directory from pending/ to target/ (approved/rejected).

    staging_writer.py creates pending/{proposal_id}/manifest.json, so we move
    the entire directory rather than a single flat file.  The blocking
    shutil.move() call is offloaded to a thread so the event loop is not stalled.
    """
    src = os.path.join(staging_dir, "pending", proposal_id)
    dst = os.path.join(staging_dir, target, proposal_id)

    if not os.path.exists(src):
        logger.warning("staging_dir_not_found", proposal_id=proposal_id, path=src)
        return

    # Validate no path traversal
    real_src = os.path.realpath(src)
    real_base = os.path.realpath(staging_dir)
    if not real_src.startswith(real_base):
        logger.error("staging_path_traversal_blocked", path=src)
        return

    await asyncio.to_thread(shutil.move, src, dst)
    logger.info("staging_dir_moved", proposal_id=proposal_id, from_="pending", to=target)


def update_staging_manifest(staging_dir: str, proposal_id: str, edited_values: dict) -> None:
    """Update staging manifest with HOD-edited values before approval."""
    path = os.path.join(staging_dir, "pending", proposal_id, "manifest.json")

    if not os.path.exists(path):
        logger.warning("staging_manifest_not_found", proposal_id=proposal_id, path=path)
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
            await move_staging_file(STAGING_BASE, proposal_id, "rejected")

        dept = _resolve_dept_from_proposal(proposal_id)
        await self._post_with_retry(
            f"{settings.email_notifier_url}/notify/confirmed",
            {"proposal_id": proposal_id, "decision": decision, "dept": dept},
            context="email_notify_confirmed",
        )

        # Non-blocking wiki compilation (fire-and-forget)
        await self.route_wiki_compile(
            event_type="proposal_approved",
            dept_id=dept,
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
        """Notify HOD about a new staging proposal.

        Reads the manifest from staging to populate all fields required by
        ProposalNotification.  Falls back gracefully if the manifest cannot be
        read so the approval flow is never blocked.
        """
        manifest_path = os.path.join(
            STAGING_BASE, "pending", proposal_id, "manifest.json"
        )
        manifest: dict = {}
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
        except Exception as exc:
            logger.warning(
                "proposal_manifest_read_failed",
                proposal_id=proposal_id,
                path=manifest_path,
                error=str(exc),
            )

        payload: dict = {
            "proposal_id": proposal_id,
            "agent_name": manifest.get("agent", "unknown"),
            "file": manifest.get("file", ""),
            "tab": manifest.get("tab", ""),
            "cell": manifest.get("cell", ""),
            "new_value": str(manifest.get("new_value", "")),
            "confidence": float(manifest.get("confidence", 0.0)),
            "dept": manifest.get("dept") or department,
        }

        await self._post_with_retry(
            f"{settings.email_notifier_url}/notify/proposal",
            payload,
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
