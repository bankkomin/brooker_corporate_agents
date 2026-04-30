import logging

import httpx

log = logging.getLogger(__name__)

# Port registry for department orchestrators
DEPT_PORTS = {
    "cac": 3001,
    "hr": 3002,
    "finance": 3010,
    "risk": 3011,
    "legal": 3012,
    "it": 3013,
    "comms": 3014,
    "ic": 3015,
    "cio": 3016,
    "vcc": 3017,
    "ib": 3018,
}


async def invoke_proactive(dept_id: str, context: str) -> dict | None:
    """POST assembled context to the department's orchestrator /proactive endpoint.

    Returns the orchestrator's response, or None if the call fails.
    """
    port = DEPT_PORTS.get(dept_id)
    if not port:
        log.warning("No known port for dept %s", dept_id)
        return None

    url = f"http://{dept_id}-orchestrator:{port}/proactive"

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(url, json={"context": context, "mode": "proactive"})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError:
            log.exception("Proactive call to %s failed", url)
            return None
