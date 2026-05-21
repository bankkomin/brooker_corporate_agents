"""Escalation check node — checks agent response against escalation rules."""
from __future__ import annotations

import json
import re

import structlog

logger = structlog.get_logger("cac-orchestrator.escalation")


def _load_rules(rules_path: str) -> list[dict]:
    """Load escalation rules from JSON config file."""
    try:
        with open(rules_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("triggers", [])
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("escalation_rules_load_failed", path=rules_path, error=str(exc))
        return []


_NUMBER_RE = re.compile(r'\b\d+(?:\.\d+)?\b')

# Words that signal the agent is reporting an ACTUAL breach (not just
# describing a rule, or quoting a regulation that mentions thresholds).
_BREACH_LANGUAGE = re.compile(
    r"\b(breach(?:ed|ing|es)?|"
    r"violat(?:es|ed|ion)?|"
    r"exceed(?:s|ed|ing)?|"
    r"above\s+the\s+(?:limit|threshold|cap|max|ceiling)|"
    r"below\s+the\s+(?:floor|minimum|min|requirement)|"
    r"fell\s+below|fall(?:s|en)?\s+below|"
    r"non[-\s]?compliant|out\s+of\s+compliance|"
    r"trigger(?:s|ed)?\s+(?:an?\s+)?(?:critical|high|amber|red)|"
    r"escalat(?:e|ed|ion))\b",
    re.IGNORECASE,
)

# Phrases that bind a number to a "this is the CURRENT value" claim, vs.
# the threshold / a quoted definition / a date / a citation index.
_VALUE_NEAR_NUMBER = re.compile(
    r"(?:\b(?:current(?:ly)?|now|stands?\s+at|reached|reports?|measured\s+at|"
    r"value\s+of|ratio\s+of|level\s+of|at\s+a\s+value\s+of|is\s+at)\b\s*[:\-]?\s*\d|"
    r"\d\s*(?:%|bps|x)?\s+(?:vs|against|over|above|under|below|exceeds?|breach(?:es)?)\s)",
    re.IGNORECASE,
)


def _has_real_breach_claim(text: str, keyword_hits: list[re.Match[str]]) -> bool:
    """A rule should only fire if the agent's response actually CLAIMS a breach
    AND has a current-value-shaped statement, not just mentions a regulation."""
    if not _BREACH_LANGUAGE.search(text):
        return False
    if not _VALUE_NEAR_NUMBER.search(text):
        return False
    return True


async def escalation_check(state: dict, *, rules_path: str) -> dict:
    """Check agent response against escalation rules.

    Returns {"escalation_triggered": bool, "escalation_detail": str | None}.

    The agent's response must (a) mention the rule's keyword AND (b) contain
    real breach-language (e.g. "exceeds", "fell below", "non-compliant") AND
    (c) include a current-value phrase (e.g. "stands at 12.5", "currently 95%")
    — otherwise we treat the response as descriptive (explaining what LCR is,
    quoting a regulation, etc.) rather than reporting an actual breach.
    """
    agent_response = state.get("agent_response", "")
    if not agent_response.strip():
        return {"escalation_triggered": False, "escalation_detail": None}

    rules = _load_rules(rules_path)
    text_lower = agent_response.lower()

    for rule in rules:
        rule_type = rule.get("type", "")
        threshold = rule.get("threshold")
        condition = rule.get("condition", ">")
        description = rule.get("description", rule_type)

        if threshold is None:
            continue

        # Rule keyword present?
        keywords = rule_type.replace("_", " ").split()
        keyword_hits = [
            m for kw in keywords for m in re.finditer(re.escape(kw.lower()), text_lower)
        ]
        if not keyword_hits:
            continue

        # New guard: only proceed if the response is making a real breach claim.
        if not _has_real_breach_claim(agent_response, keyword_hits):
            continue

        # Extract numbers within 80 chars of a keyword hit (was 200 — tightened).
        numbers: list[float] = []
        for kw_hit in keyword_hits:
            start = max(0, kw_hit.start() - 80)
            end = min(len(agent_response), kw_hit.end() + 80)
            for n in _NUMBER_RE.finditer(agent_response[start:end]):
                try:
                    numbers.append(float(n.group()))
                except ValueError:
                    pass

        for num in numbers:
            # Skip the threshold itself reappearing — agent often quotes it
            # right next to the keyword ("covenant ratio limit is 4.0").
            if abs(num - threshold) < 1e-6:
                continue
            ops = {">": num > threshold, "<": num < threshold,
                   ">=": num >= threshold, "<=": num <= threshold}
            triggered = ops.get(condition, False)
            if triggered:
                detail = f"{description}: value {num} {condition} threshold {threshold}"
                logger.warning(
                    "escalation_triggered",
                    rule_type=rule_type, value=num, threshold=threshold,
                )
                return {"escalation_triggered": True, "escalation_detail": detail}

    return {"escalation_triggered": False, "escalation_detail": None}
