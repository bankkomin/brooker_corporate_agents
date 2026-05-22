"""Simplified read-only query pipeline: embed → search → format → synthesise → log."""
import logging
import time
from pathlib import Path

from langchain_openai import ChatOpenAI
from qdrant_client import AsyncQdrantClient

from .config import settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a corporate AI assistant for the {dept_name} department.
Answer questions using the provided context. Cite sources using [N] format.
Be precise, factual, and professional. If no relevant sources found, say so clearly.
Never speculate beyond what the sources state.

{skill_content}

{memory_content}"""


async def run_query(
    query: str,
    dept_id: str,
    dept_config: dict,
    user_id: str,
    db_pool,
) -> dict:
    """Execute the 5-step read-only pipeline."""
    start = time.monotonic()

    # Step 1: Load memory + skills
    memory = _load_memory(dept_id, dept_config)
    skill_content = _load_skills(dept_id)

    # Step 2: Search Qdrant collections
    collections = [f"{dept_id}_docs", f"{dept_id}_chat", f"{dept_id}_knowledge", "shared_policies"]
    cross_read = dept_config.get("crossReadAccess", [])
    if cross_read and "*" not in cross_read:
        collections += [f"{d}_docs" for d in cross_read]

    chunks = await _search_collections(query, collections)

    # Step 3: Format context
    context_parts = []
    sources = []
    for i, chunk in enumerate(chunks[:8]):
        ref = f"[{i+1}]"
        context_parts.append(f"{ref} {chunk.get('text', '')}")
        sources.append({"id": str(i+1), "text": chunk.get("text", ""), "source": chunk.get("source", "")})

    context_text = "\n\n".join(context_parts) if context_parts else "No relevant documents found."

    # Step 4: Synthesise answer
    dept_name = dept_config.get("name", dept_id)
    system = SYSTEM_PROMPT.format(
        dept_name=dept_name,
        skill_content=skill_content,
        memory_content=memory,
    )

    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        api_key="not-needed",
        temperature=0.1,
    )

    user_prompt = f"Context:\n{context_text}\n\nQuestion: {query}"
    response = await llm.ainvoke([
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ])
    answer = response.content.strip()

    latency = int((time.monotonic() - start) * 1000)

    # Step 5: Log interaction
    _log_daily(dept_id, user_id, query, answer, sources, latency)

    return {
        "response": answer,
        "citations": [s["source"] for s in sources],
        "dept_id": dept_id,
        "chunks_retrieved": len(chunks),
        "latency_ms": latency,
    }


def _load_memory(dept_id: str, dept_config: dict) -> str:
    """Load agent memory triad if available."""
    vault = Path(settings.VAULT_ROOT) / dept_id / "_memory"
    parts = []
    if vault.exists():
        for agent_dir in vault.iterdir():
            if not agent_dir.is_dir() or agent_dir.name == "history":
                continue
            for fname in ("soul.md", "memory.md"):
                f = agent_dir / fname
                if f.is_file():
                    content = f.read_text(encoding="utf-8").strip()
                    if content:
                        parts.append(content)
    return "\n---\n".join(parts) if parts else ""


def _load_skills(dept_id: str) -> str:
    """Load SKILL.md content for the department."""
    skills_dir = Path(settings.SKILLS_ROOT) / dept_id
    parts = []
    if skills_dir.exists():
        for f in skills_dir.glob("*.md"):
            content = f.read_text(encoding="utf-8").strip()
            if content and not content.startswith("---\ndeprecated:"):
                parts.append(f"### {f.stem}\n{content[:500]}")
    return "\n\n".join(parts[:4]) if parts else ""  # max 4 skills


async def _search_collections(query: str, collections: list[str]) -> list[dict]:
    """Search multiple Qdrant collections."""
    try:
        client = AsyncQdrantClient(url=settings.QDRANT_URL)
        results = []
        for collection in collections:
            try:
                hits = await client.query_points(
                    collection_name=collection,
                    query_text=query,
                    limit=3,
                )
                for hit in hits.points:
                    results.append({
                        "text": hit.payload.get("text", ""),
                        "source": hit.payload.get("source", collection),
                        "score": hit.score,
                    })
            except Exception:
                log.debug("Collection %s not available, skipping", collection)

        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[:8]
    except Exception:
        log.exception("Qdrant search failed")
        return []


def _log_daily(dept_id: str, user_id: str, query: str, answer: str, sources: list, latency: int):
    """Append to daily log file."""
    from datetime import datetime
    vault = Path(settings.VAULT_ROOT) / dept_id / "daily-logs"
    vault.mkdir(parents=True, exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    now = datetime.utcnow().strftime("%H:%M")

    entry = f"\n## {now} · @{user_id} · proposal: none\n**Q:** {query}\n**A:** {answer[:500]}\n**Latency:** {latency}ms\n**Outcome:** n/a\n"
    with (vault / f"{today}.md").open("a", encoding="utf-8") as f:
        f.write(entry)
