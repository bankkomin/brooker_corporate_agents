"""LLM client for the reflection engine.

Uses vLLM via OpenAI-compatible API (langchain-openai).
Degrades gracefully: returns empty update dicts on any LLM failure.
"""
import asyncio
import json
import os

import structlog
from langchain_openai import ChatOpenAI

from .config import settings

log = structlog.get_logger(__name__)

# The shared DGX Spark fails beyond a few concurrent sequences. The reflection
# engine runs a nightly batch over many agents, so cap concurrent LLM calls.
LLM_MAX_CONCURRENCY = int(os.getenv("LLM_MAX_CONCURRENCY", "4"))
_DGX_SEMAPHORE = asyncio.Semaphore(LLM_MAX_CONCURRENCY)

REFLECTION_PROMPT = """You are a reflection agent for the {dept_id} department's {agent_id} agent.
Analyze yesterday's interactions and approval decisions, then determine what should be updated
in the agent's persistent memory.

Yesterday's daily log entries:
{daily_log}

Approval decisions on staging proposals:
{decisions}

Knowledge gaps identified:
{gaps}

Current memory.md:
{current_memory}

Current user.md:
{current_user}

Output a JSON object with exactly these keys:
{{
  "memory_md_updates": [
    {{"section": "section_name", "content": "new content to add or replace"}}
  ],
  "user_md_updates": [
    {{"section": "section_name", "content": "new content to add or replace"}}
  ],
  "skill_proposals": [
    {{"skill_path": "skills/dept/skill.md", "trigger": "description of pattern", "evidence": {{"count": 5, "avg_signal": 0.3}}}}
  ]
}}

Rules:
- Only promote facts you are highly confident about (observed >= 3 times)
- memory_md_updates: lessons learned, recurring corrections, key decisions
- user_md_updates: per-user/committee facts (names, preferences, recurring concerns) — high confidence only
- skill_proposals: only if >= {min_pattern_count} same-shape corrections with avg signal_strength < {signal_threshold}
- Be conservative — fewer updates is better than noisy updates
- Return empty arrays if nothing warrants an update
"""

_EMPTY_RESPONSE: dict = {"memory_md_updates": [], "user_md_updates": [], "skill_proposals": []}


async def run_reflection_llm(
    dept_id: str,
    agent_id: str,
    daily_log: str,
    decisions: str,
    gaps: str,
    current_memory: str,
    current_user: str,
) -> dict:
    """Call LLM to produce reflection output.

    Returns empty update dict on LLM unavailability or parse failure.
    """
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key="not-needed",  # noqa: S106 — vLLM local, no real auth
        temperature=0.1,
    )

    prompt = REFLECTION_PROMPT.format(
        dept_id=dept_id,
        agent_id=agent_id,
        daily_log=daily_log,
        decisions=decisions,
        gaps=gaps,
        current_memory=current_memory,
        current_user=current_user,
        min_pattern_count=settings.MIN_PATTERN_COUNT,
        signal_threshold=settings.SIGNAL_THRESHOLD,
    )

    for attempt in range(3):
        try:
            async with _DGX_SEMAPHORE:
                response = await llm.ainvoke(prompt)
            content: str = response.content.strip()

            # Strip markdown code fences if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
            if all(k in result for k in ("memory_md_updates", "user_md_updates", "skill_proposals")):
                log.info(
                    "reflection_llm_ok",
                    dept=dept_id,
                    agent=agent_id,
                    attempt=attempt + 1,
                    memory_updates=len(result["memory_md_updates"]),
                    skill_proposals=len(result["skill_proposals"]),
                )
                return result

            log.warning("reflection_llm_missing_keys", attempt=attempt + 1, dept=dept_id, agent=agent_id)

        except json.JSONDecodeError:
            log.warning("reflection_llm_json_parse_error", attempt=attempt + 1, dept=dept_id, agent=agent_id)
        except Exception:
            log.exception("reflection_llm_error", attempt=attempt + 1, dept=dept_id, agent=agent_id)
            # LLM unavailable — return empty rather than crashing
            return _EMPTY_RESPONSE

        if attempt < 2:
            await asyncio.sleep(2**attempt)

    log.error("reflection_llm_exhausted_retries", dept=dept_id, agent=agent_id)
    return _EMPTY_RESPONSE
