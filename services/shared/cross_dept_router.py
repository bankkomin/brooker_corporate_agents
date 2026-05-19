"""Cross-department query router — routes questions that span multiple departments."""
import logging

import httpx

log = logging.getLogger(__name__)

# Keywords that suggest cross-department queries
DEPT_KEYWORDS = {
    "cac": ["LCR", "NSFR", "ALCO", "liquidity", "capital adequacy", "covenant", "funding facility"],
    "finance": ["annual report", "financial statement", "networth", "P&L", "balance sheet"],
    "risk": ["risk policy", "credit risk", "market risk", "operational risk", "VaR"],
    "legal": ["AML", "compliance", "contract", "regulatory", "legal opinion"],
    "cio": ["NAV", "custodian", "fund performance", "AUM", "portfolio"],
    "vcc": ["client", "subscription", "VCC", "newsletter"],
    "hr": ["headcount", "compensation", "HR policy", "talent", "hiring"],
    "ic": ["investment", "due diligence", "portfolio company", "IC minutes"],
    "it": ["IT policy", "infrastructure", "security", "DevOps"],
    "comms": ["press release", "IR", "branding", "marketing"],
}

ORCHESTRATOR_PORTS = {
    "cac": 3001, "hr": 3002, "finance": 3010,
    "risk": 3011, "legal": 3012, "it": 3013,
    "comms": 3014, "ic": 3015, "cio": 3016,
    "vcc": 3017, "ib": 3018,
}


def detect_departments(query: str) -> list[str]:
    """Detect which departments a query is relevant to."""
    query_lower = query.lower()
    matched = []

    for dept, keywords in DEPT_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in query_lower:
                if dept not in matched:
                    matched.append(dept)
                break

    return matched if matched else ["cac"]  # default to CAC


async def route_cross_dept(
    query: str,
    departments: list[str],
    user_id: str = "unknown",
    timeout: float = 60.0,
) -> dict:
    """Route a query to multiple departments and synthesize results."""
    if len(departments) <= 1:
        dept = departments[0] if departments else "cac"
        return await _query_single_dept(dept, query, user_id, timeout)

    # Query all departments in parallel
    results = {}
    async with httpx.AsyncClient(timeout=timeout) as client:
        for dept in departments:
            port = ORCHESTRATOR_PORTS.get(dept)
            if not port:
                continue
            try:
                resp = await client.post(
                    f"http://{dept}-orchestrator:{port}/query",
                    json={"query": query, "user_id": user_id},
                )
                if resp.status_code == 200:
                    results[dept] = resp.json()
                else:
                    results[dept] = {"error": f"HTTP {resp.status_code}"}
            except Exception as e:
                results[dept] = {"error": str(e)}
                log.warning("Cross-dept query to %s failed: %s", dept, e)

    # Synthesize
    return {
        "query": query,
        "departments_queried": departments,
        "results": results,
        "synthesized_response": _synthesize_results(query, results),
    }


async def _query_single_dept(dept: str, query: str, user_id: str, timeout: float) -> dict:
    port = ORCHESTRATOR_PORTS.get(dept)
    if not port:
        return {"error": f"Unknown department: {dept}"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"http://{dept}-orchestrator:{port}/query",
            json={"query": query, "user_id": user_id},
        )
        return resp.json()


def _synthesize_results(query: str, results: dict) -> str:
    """Combine results from multiple departments into a unified response."""
    parts = []
    for dept, result in results.items():
        if "error" in result:
            parts.append(f"**{dept.upper()}**: Unable to retrieve ({result['error']})")
        else:
            response = result.get("response", "No response")
            parts.append(f"**{dept.upper()}**: {response}")

    if not parts:
        return "No departments returned results for this query."

    return "\n\n---\n\n".join(parts)
