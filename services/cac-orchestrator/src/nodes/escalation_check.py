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


def _extract_numbers(text: str) -> list[float]:
    """Extract all decimal numbers from text."""
    return [float(m) for m in re.findall(r'\b\d+\.?\d*\b', text)]


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

        # Check if the rule type keywords appear in the response
        keywords = rule_type.replace("_", " ").split()
        if not any(kw.lower() in agent_response.lower() for kw in keywords):
            continue

        # Extract numbers and check against threshold
        numbers = _extract_numbers(agent_response)
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
