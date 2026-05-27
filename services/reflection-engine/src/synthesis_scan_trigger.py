"""Nightly scheduler trigger for B4 synthesis scan.

reflection-engine doesn't have direct Qdrant or embedder access, so it
fires `POST /synthesis/scan` against rag-ingestion (which does) instead
of running the proposer in-process. Fire-and-forget by design — the
scheduler logs the outcome but never raises.

This module is consumed by `scheduler.py` (registers the cron job) and
indirectly by the manual trigger endpoint in `main.py`.
"""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


async def trigger_synthesis_scan(
    *,
    rag_ingestion_url: str,
    timeout_seconds: float,
) -> dict:
    """POST /synthesis/scan and return the parsed JSON response.

    On any network or HTTP-status failure returns a {status: 'failed',
    error: ...} dict — never raises, so the scheduler keeps running.
    """
    url = f"{rag_ingestion_url.rstrip('/')}/synthesis/scan"
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(url)
    except httpx.RequestError as exc:
        log.warning("synthesis_scan_trigger.network_error url=%s err=%s", url, exc)
        return {"status": "failed", "reason": "network_error", "error": str(exc)}
    if resp.status_code >= 400:
        log.warning(
            "synthesis_scan_trigger.http_error status=%d url=%s body_head=%r",
            resp.status_code, url, resp.text[:200],
        )
        return {"status": "failed", "reason": f"http_{resp.status_code}", "body": resp.text[:200]}
    try:
        body = resp.json()
    except ValueError:
        log.warning("synthesis_scan_trigger.bad_json status=%d", resp.status_code)
        return {"status": "failed", "reason": "bad_json"}
    log.info(
        "synthesis_scan_trigger.ok candidates=%s proposed=%s",
        body.get("candidates"), body.get("proposed"),
    )
    return body
