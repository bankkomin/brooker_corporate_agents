"""Escalation check node for HR -- checks against HR-specific escalation rules."""
from __future__ import annotations

import json
import re

import structlog

logger = structlog.get_logger("hr-orchestrator.escalation")


def _load_rules(rules_path: str) -> list[dict]:
    """Load escalation rules from JSON config file."""
    try:
        with open(rules_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("triggers", [])
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("escalation_rules_load_failed", path=rules_path, error=str(exc))
        return []


_NUMBER_RE = re.compile(r'\b\d+\.?\d*\b')
_PROXIMITY_WINDOW = 200


def _extract_numbers_near_keywords(text: str, keywords: list[str]) -> list[float]:
    """Extract numbers that appear within PROXIMITY_WINDOW chars of a keyword."""
    text_lower = text.lower()
    results: list[float] = []
    for match in _NUMBER_RE.finditer(text):
        start = match.start()
        window_start = max(0, start - _PROXIMITY_WINDOW)
        window_end = min(len(text), start + len(match.group()) + _PROXIMITY_WINDOW)
        surrounding = text_lower[window_start:window_end]
        if any(kw.lower() in surrounding for kw in keywords):
            results.append(float(match.group()))
    return results


async def escalation_check(state: dict, *, rules_path: str) -> dict:
    """Check agent response against escalation rules.

    Returns {"escalation_triggered": bool, "escalation_detail": str | None}.
    """
    agent_response = state.get("agent_response", "")
    rules = _load_rules(rules_path)

    for rule in rules:
        rule_type = rule.get("type", "")
        threshold = rule.get("threshold")
        condition = rule.get("condition", ">")
        description = rule.get("description", rule_type)

        if threshold is None:
            continue

        keywords = rule_type.replace("_", " ").split()
        if not any(kw.lower() in agent_response.lower() for kw in keywords):
            continue

        numbers = _extract_numbers_near_keywords(agent_response, keywords)
        for num in numbers:
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
