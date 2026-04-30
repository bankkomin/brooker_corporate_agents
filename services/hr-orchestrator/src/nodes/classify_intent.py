"""Intent classification node for HR queries."""
from __future__ import annotations

import json

import structlog

from ..tools.llm_client import LLMClient

logger = structlog.get_logger("hr-orchestrator.classify")

HR_INTENT_CATEGORIES = ["recruitment", "compensation", "compliance", "general"]

SYSTEM_PROMPT = (
    "You are an intent classifier for a Human Resources AI system.\n"
    "Classify the following query into exactly one of these categories: "
    "recruitment, compensation, compliance, general.\n"
    "- recruitment: hiring, talent acquisition, job postings, interviews, onboarding\n"
    "- compensation: salaries, benefits, bonuses, pay bands, market benchmarking\n"
    "- compliance: labor law, HR policy adherence, termination procedures, audits\n"
    "- general: anything else HR-related\n"
    'Respond with JSON only: {"intent": "<category>", "confidence": <0.0-1.0>}\n'
    "Do not include any other text."
)


async def classify_intent(state: dict, *, llm_client: LLMClient) -> dict:
    """Classify user query intent. Returns {"intent": str, "intent_confidence": float}."""
    query = state.get("query", "")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]
    raw_text = ""
    try:
        raw_text = await llm_client.chat(
            messages, temperature=0.0, max_tokens=100, seed=42
        )
        parsed = json.loads(raw_text)
        intent = parsed.get("intent", "general")
        confidence = float(parsed.get("confidence", 0.5))
        if intent not in HR_INTENT_CATEGORIES:
            intent = "general"
        confidence = max(0.0, min(1.0, confidence))
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("classify_intent_parse_error", error=str(exc), raw=raw_text)
        intent = "general"
        confidence = 0.5

    logger.info("intent_classified", intent=intent, confidence=confidence)
    return {"intent": intent, "intent_confidence": confidence}
