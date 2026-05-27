"""Build the CAC meeting report FIRST DRAFT from the live Excel Online data pack.

Numbers come straight from the workbook cells (deterministic, no fabrication);
the LLM only writes narrative commentary grounded in those numbers and the
Board-approved limits. Limit breaches are computed in code and handed to the LLM.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger("cac-orchestrator.cac-meeting-report")

# Board-approved limits (Khao Yai retreat §2.8). label-substring -> (limit, breach-check)
_LIMITS = {
    "investment / total assets": ("< 40% (binding Jun 2026)", lambda v: v is not None and v >= 40),
    "debt-to-equity": ("< 0.5x", lambda v: v is not None and v > 0.5),
    "cost of funds": ("< 3-4%", lambda v: v is not None and v > 4),
    "aggregate on-chain dtv": ("<= 25% hard cap", lambda v: v is not None and v > 25),
    "liquidity runway": (">= 6 months", lambda v: v is not None and v < 6),
    "months of runway": (">= 6 months", lambda v: v is not None and v < 6),
    "sovereignty buffer": (">= 100 BTC", lambda v: v is not None and v < 100),
}


def _num(v):
    try:
        return float(str(v).replace("%", "").replace("x", "").replace(",", "").strip())
    except Exception:
        return None


def format_workbook(workbook: dict[str, list[list]]) -> tuple[str, list[str]]:
    """Flatten the workbook into a compact data block + detect limit breaches."""
    lines: list[str] = []
    breaches: list[str] = []
    for sheet, rows in workbook.items():
        if sheet.lower() == "instructions" or not rows:
            continue
        lines.append(f"### {sheet}")
        for row in rows:
            cells = [("" if c is None else str(c)).strip() for c in row]
            if not any(cells):
                continue
            label = cells[0]
            values = [c for c in cells[1:] if c]
            if label:
                lines.append(f"- {label}: {' | '.join(values)}" if values else f"- {label}")
            # breach check on the first value cell
            val = _num(cells[1]) if len(cells) > 1 else None
            for key, (limit, check) in _LIMITS.items():
                if key in label.lower() and check(val):
                    breaches.append(f"{label} = {cells[1]} (limit {limit})")
    # dedup breaches preserving order
    seen = set()
    breaches = [b for b in breaches if not (b in seen or seen.add(b))]
    return "\n".join(lines), breaches


async def build_report(workbook: dict[str, list[list]], llm_client, month: str,
                       source_url: str = "") -> dict:
    data_block, breaches = format_workbook(workbook)
    from datetime import date

    breach_text = ("\n".join(f"- {b}" for b in breaches)
                   if breaches else "None — all reported metrics within Board limits.")

    system_prompt = (
        "You are the Capital Allocation & ALCO Committee (CAC) secretary preparing the "
        "FIRST DRAFT of the monthly CAC committee meeting report. Write in markdown.\n"
        "RULES:\n"
        "- Use ONLY the figures in the data block. NEVER invent or alter a number.\n"
        "- Lead the Executive Summary with any limit breaches (these are pre-computed).\n"
        "- Be concise and decision-oriented; this goes to the committee for review.\n"
        "- Mark the document a DRAFT for committee review.\n\n"
        "Structure:\n"
        f"# CAC Meeting Report — First Draft — {month}\n"
        f"*Status: DRAFT for committee review · Prepared {date.today().isoformat()} · "
        "Source: live CAC Data Pack (Excel Online)*\n"
        "1. Executive Summary  2. Balance Sheet  3. Capital Allocation  "
        "4. Liquidity (Stay Liquid)  5. Funding & Covenants  6. Asset-Liability Risk  "
        "7. On-Chain Collateral  8. Risk Appetite vs Limits  9. Policy Compliance  "
        "10. Recommendations (tag each by approval level per R-05)."
    )
    user_msg = (
        f"Month: {month}\n\n"
        f"PRE-COMPUTED LIMIT BREACHES:\n{breach_text}\n\n"
        f"DATA PACK (authoritative figures from the live Excel Online workbook):\n{data_block}"
    )

    logger.info("cac_meeting_report.generating", month=month, breaches=len(breaches))
    try:
        report = await llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.15,
            max_tokens=2048,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("cac_meeting_report.llm_failed", error=str(exc))
        report = (f"# CAC Meeting Report — First Draft — {month}\n\n"
                  f"Report generation error: {exc}\n\nPre-computed breaches:\n{breach_text}")

    return {"report": report, "breaches": breaches, "month": month, "source": source_url}
