"""Venture-monitor integration bridge — connects corporate agents with VC monitoring data."""
import logging

import httpx

log = logging.getLogger(__name__)

VM_BASE_URL = "http://localhost:8000"  # venture-monitor API


class VentureMonitorBridge:
    """Bridge between corporate agents and venture-monitor system."""

    def __init__(self, base_url: str = VM_BASE_URL):
        self.base_url = base_url.rstrip("/")

    async def get_fund_scores(self) -> list[dict]:
        """Get latest composite risk scores for all funds."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self.base_url}/api/scores")
            resp.raise_for_status()
            return resp.json().get("scores", [])

    async def get_fund_score(self, fund_id: int) -> dict:
        """Get score history for a specific fund."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self.base_url}/api/scores/{fund_id}")
            resp.raise_for_status()
            return resp.json()

    async def get_high_severity_signals(self, min_severity: str = "high") -> list[dict]:
        """Get high-severity signals for forwarding to corporate channels."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/api/social-signals",
                params={"severity": min_severity, "days": 7},
            )
            resp.raise_for_status()
            return resp.json().get("signals", [])

    async def get_fund_briefing(self, fund_id: int) -> dict | None:
        """Get the latest GP call briefing for a fund."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self.base_url}/api/briefings/{fund_id}")
            if resp.status_code == 200:
                briefings = resp.json().get("briefings", [])
                return briefings[0] if briefings else None
            return None

    async def search_fund_data(self, query: str) -> dict:
        """Search across venture-monitor fund data (for cross-system queries)."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/api/funds",
                params={"search": query},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_reconciliation_summary(self) -> list[dict]:
        """Get latest reconciliation status for all funds."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self.base_url}/api/reconciliations/summary")
            resp.raise_for_status()
            return resp.json().get("reconciliations", [])

    async def forward_signals_to_slack(
        self,
        signals: list[dict],
        slack_webhook_url: str,
    ) -> int:
        """Forward high-severity VM signals to corporate Slack channels."""
        forwarded = 0
        async with httpx.AsyncClient(timeout=10.0) as client:
            for signal in signals:
                severity = signal.get("severity", "info")
                emoji = {"critical": "\U0001f534", "high": "\U0001f7e0"}.get(severity, "\U0001f7e1")

                message = {
                    "text": (
                        f"{emoji} *Venture Monitor Alert*\n"
                        f"*{signal.get('entity_name', 'Unknown')}*: "
                        f"{signal.get('description', '')}\n"
                        f"Severity: {severity.upper()} | "
                        f"Source: {signal.get('source', 'unknown')}"
                    ),
                }

                try:
                    resp = await client.post(slack_webhook_url, json=message)
                    if resp.status_code == 200:
                        forwarded += 1
                except Exception:
                    log.warning("Failed to forward signal to Slack")

        return forwarded
