import logging

log = logging.getLogger(__name__)


async def gather_context(dept_id: str, context_sources: list[str]) -> str:
    """Gather context from configured sources for a department's proactive heartbeat.

    Supported URI prefixes (stubs for now):
    - slack:#channel-name — read recent messages from Slack channel
    - sharepoint://Path/To/Folder — read recent files from SharePoint

    Returns concatenated context string.
    """
    parts = []

    for source in context_sources:
        try:
            if source.startswith("slack:"):
                channel = source.split(":", 1)[1]
                content = await _gather_slack(channel)
                parts.append(f"[Slack #{channel}]\n{content}")
            elif source.startswith("sharepoint:"):
                path = source.split(":", 1)[1]
                content = await _gather_sharepoint(path)
                parts.append(f"[SharePoint {path}]\n{content}")
            else:
                log.warning("Unknown context source URI: %s", source)
        except Exception:
            log.exception("Failed to gather from %s for %s", source, dept_id)

    return "\n\n---\n\n".join(parts) if parts else "(no context available)"


async def _gather_slack(channel: str) -> str:
    """Stub: read recent Slack messages. Real implementation deferred."""
    log.info("Slack context gather stub for #%s", channel)
    return f"(Slack #{channel} — stub: real implementation requires Slack API credentials)"


async def _gather_sharepoint(path: str) -> str:
    """Stub: read recent SharePoint files. Real implementation deferred."""
    log.info("SharePoint context gather stub for %s", path)
    return f"(SharePoint {path} — stub: real implementation requires SharePoint API credentials)"
