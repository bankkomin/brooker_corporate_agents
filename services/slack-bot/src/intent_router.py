"""LLM-based intent classifier for the slack-bot router.

Fires one fast Qwen call to decide whether a user @mention is asking to
GENERATE an artefact (today: a pitch deck) or asking a normal QUESTION.

Returns a structured `Intent` so the dispatch table in `clients.py` stays
declarative as we add more actionable intents (staging proposal, escalation,
report run, etc.).
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Literal

import httpx
import structlog

logger = structlog.get_logger("slack-bot.intent_router")

IntentName = Literal["deck", "chat"]


@dataclass(frozen=True)
class Intent:
    name: IntentName
    confidence: float
    reason: str = ""


_SYSTEM_PROMPT = (
    "You classify a single Slack message into ONE of these intents:\n"
    "  deck  — the user is asking the assistant to CREATE / GENERATE / WRITE / "
    "DRAFT / BUILD a pitch deck, slide deck, presentation, slides, or pptx.\n"
    "  chat  — anything else: questions, lookups, explanations, conversation, "
    "small talk, even questions ABOUT decks (e.g. 'what is a pitch deck').\n"
    "Reply with ONLY a JSON object, no prose, no fences, no extra characters:\n"
    '{"intent": "deck" | "chat", "confidence": 0.0-1.0, "reason": "string"}\n'
    "Bias toward `chat` unless the request is unambiguously to PRODUCE a deck."
)

# Patterns we can short-circuit on without hitting the LLM at all.
# Saves the latency hit on the obvious cases (greetings, plain questions).
_DECK_VERB = re.compile(
    r"\b(generate|create|make|write|draft|build|compose|prepare|put together|"
    r"give me|produce)\b[^?]{0,80}\b(deck|slides?|presentation|pptx|pitch)\b",
    re.IGNORECASE,
)
# Message that STARTS with a deck noun ("deck about X", "slides on Y",
# "presentation for Z", "pitch deck comparing A vs B"). The trailing
# `\s+\S` requires actual content after the noun so a bare "deck" or
# "what is a deck" doesn't match.
_DECK_NOUN_LEAD = re.compile(
    r"^\s*(?:a\s+)?(?:pitch\s+)?(?:deck|slides?|presentation|pptx|slide\s+deck)"
    r"\s+(?:about|on|for|covering|comparing|featuring|with|that|to|of)\b",
    re.IGNORECASE,
)
_CHAT_SHORT_CIRCUIT = re.compile(
    r"^\s*(hi|hello|hey|sup|yo|gm|good (morning|afternoon|evening)|"
    r"what is|whats|what's|who is|whos|who's|how|why|when|where|tell me about|"
    r"explain|define|describe)\b",
    re.IGNORECASE,
)


class IntentRouter:
    """Async intent classifier. Stateless across calls."""

    def __init__(
        self,
        *,
        llm_url: str,
        llm_model: str,
        api_key: str = "",
        timeout: float = 5.0,
    ) -> None:
        self._url = llm_url.rstrip("/") + "/chat/completions"
        self._model = llm_model
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.AsyncClient(timeout=timeout, headers=headers)

    async def close(self) -> None:
        await self._http.aclose()

    async def classify(self, message: str) -> Intent:
        text = (message or "").strip()
        if not text:
            return Intent(name="chat", confidence=1.0, reason="empty")

        # Cheap regex fast-paths before paying for an LLM call.
        if _DECK_VERB.search(text):
            logger.info("intent.shortcircuit", intent="deck", path="regex_deck_verb")
            return Intent(name="deck", confidence=0.95, reason="regex:deck_verb")
        if _DECK_NOUN_LEAD.match(text):
            logger.info("intent.shortcircuit", intent="deck", path="regex_deck_noun_lead")
            return Intent(name="deck", confidence=0.95, reason="regex:deck_noun_lead")
        if _CHAT_SHORT_CIRCUIT.match(text):
            logger.info("intent.shortcircuit", intent="chat", path="regex_question")
            return Intent(name="chat", confidence=0.9, reason="regex:question_lead")

        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text[:600]},
            ],
            "max_tokens": 60,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }
        t0 = time.monotonic()
        try:
            r = await self._http.post(self._url, json=body)
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"] or "{}"
            parsed = _extract_json_object(raw) or {}
            name = parsed.get("intent")
            if name not in ("deck", "chat"):
                name = "chat"
            confidence = float(parsed.get("confidence", 0.5) or 0.5)
            reason = str(parsed.get("reason", ""))[:120]
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.info(
                "intent.classified",
                intent=name, confidence=round(confidence, 2),
                elapsed_ms=elapsed_ms, reason=reason,
            )
            return Intent(name=name, confidence=confidence, reason=reason)
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.warning(
                "intent.classify_failed", error=str(exc), elapsed_ms=elapsed_ms,
                fallback="chat",
            )
            return Intent(name="chat", confidence=0.0, reason=f"fallback:{type(exc).__name__}")


def _extract_json_object(text: str) -> dict | None:
    """Find the first balanced {...} block in `text` and parse it.

    Mirrors the parser deck-writer uses — Qwen sometimes wraps JSON in
    markdown fences or prepends stray characters.
    """
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.DOTALL)
    s = re.sub(r"\{\s*\[\s*\]\s*", "{", s)
    s = re.sub(r"\{\s*\[(\s*[\"\n])", r"{\1", s)
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[start : i + 1])
                except Exception:
                    return None
    return None


def make_default_router() -> IntentRouter:
    """Build a router from env vars (same vars cac-orchestrator uses)."""
    return IntentRouter(
        llm_url=os.getenv("VLLM_LARGE_URL", "http://nginx:8080/v1"),
        llm_model=os.getenv("VLLM_LARGE_MODEL", "qwen-large"),
        api_key=os.getenv("LLM_API_KEY", ""),
        timeout=float(os.getenv("INTENT_TIMEOUT_SECONDS", "5.0")),
    )
