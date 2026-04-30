import asyncio
import json
import logging

from langchain_openai import ChatOpenAI

from .config import settings

log = logging.getLogger(__name__)

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
    {{"skill_path": "skills/dept/skill.md", "trigger": "description of pattern", "evidence": {{"count": N, "avg_signal": 0.X}}}}
  ]
}}

Rules:
- Only promote facts you are highly confident about
- memory_md_updates: lessons learned, recurring corrections, key decisions
- user_md_updates: per-user/committee facts (names, preferences, recurring concerns) — high confidence only
- skill_proposals: only if >= 5 same-shape corrections with avg signal_strength < 0.5
- Be conservative — fewer updates is better than noisy updates
- Return empty arrays if nothing warrants an update
"""


async def run_reflection_llm(
    dept_id: str,
    agent_id: str,
    daily_log: str,
    decisions: str,
    gaps: str,
    current_memory: str,
    current_user: str,
) -> dict:
    """Call LLM to produce reflection output."""
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        api_key="not-needed",
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
    )

    for attempt in range(3):
        response = await llm.ainvoke(prompt)
        content = response.content.strip()
        # Extract JSON from markdown code block if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            result = json.loads(content)
            if all(k in result for k in ("memory_md_updates", "user_md_updates", "skill_proposals")):
                return result
            log.warning("Attempt %d: missing keys in LLM response", attempt + 1)
        except json.JSONDecodeError:
            log.warning("Attempt %d: failed to parse LLM JSON response", attempt + 1)

        if attempt < 2:
            await asyncio.sleep(2 ** attempt)

    return {"memory_md_updates": [], "user_md_updates": [], "skill_proposals": []}
