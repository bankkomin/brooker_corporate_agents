"""Simplified read-only query pipeline: embed → search → format → synthesise → log."""
import json
import logging
import os
import re
import time
from pathlib import Path

import httpx
from langchain_openai import ChatOpenAI
from qdrant_client import AsyncQdrantClient

from .config import settings
from .staging_writer import maybe_write_staging_proposal

try:
    from services.shared.citation_grounding import ground_citations, add_grounding_badges
except ImportError:
    ground_citations = None  # type: ignore[assignment]

_RAG_INGESTION_URL = os.getenv("RAG_INGESTION_URL", "http://rag-ingestion:3004").rstrip("/")

# Shown when an answer cites sources but none of them actually support its claims.
_ABSTENTION_ANSWER = (
    "I don't have reference material on this topic in my knowledge base yet. "
    "Please share a relevant document and I'll analyze it."
)

# Identity / capability / greeting questions. These describe the agent's own role
# from its (grounded) skill mandate — they need no document retrieval, so they
# bypass the grounding gate instead of abstaining.
_CAPABILITY_RE = re.compile(
    r"\b(what(?:'?s| is| are) your (?:task|tasks|role|mandate|job|purpose|"
    r"responsibilit\w+|capabilit\w+)|what (?:can|do) you (?:do|help)|"
    r"who are you|what are you|introduce yourself|how can you help|"
    r"what do you cover|what is your function)\b",
    re.IGNORECASE,
)
_GREETING_RE = re.compile(r"^\s*(hi|hello|hey|good (?:morning|afternoon|evening))[\s!.?]*$", re.IGNORECASE)


def _is_capability_query(q: str) -> bool:
    q = (q or "").strip()
    return bool(_CAPABILITY_RE.search(q) or _GREETING_RE.match(q))


async def _pick_specialist(query: str, dept_config: dict, llm) -> str | None:
    """Supervisor routing: choose the ONE backend sub-agent best suited to the
    query, from the department's agentTopology.specialists. Returns the cleaned
    specialist name (e.g. 'credit-risk'), 'general', or None if the dept has no
    specialists. One cheap LLM classification call (route-to-relevant)."""
    specialists = (dept_config.get("agentTopology") or {}).get("specialists") or []
    names = [s.replace("-agent", "") for s in specialists]
    if not names:
        return None
    sys_prompt = (
        f"You are the supervisor of the {dept_config.get('name', 'department')}. "
        f"Route the user's question to exactly ONE backend sub-specialist.\n"
        f"Choices: {', '.join(names)}, general.\n"
        "Reply with ONLY one name from that list (or 'general' if none clearly fits). "
        "No other words."
    )
    try:
        resp = await llm.ainvoke([
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": query},
        ])
        pick = resp.content.strip().lower().split()[0].strip(".,:;\"'")
        if pick in names:
            return pick
    except Exception as exc:  # noqa: BLE001
        log.warning("specialist_routing_failed dept=%s error=%s",
                    dept_config.get("name"), exc)
    return "general"

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
        # Cross-read raw docs AND compiled wiki knowledge of the other dept.
        collections += [f"{d}_docs" for d in cross_read]
        collections += [f"{d}_knowledge" for d in cross_read]

    # ── Capability / identity bypass ──────────────────────────────────────────
    # "What is your task?", "who are you?", greetings — answer from the dept's
    # own (grounded) skill mandate; no document retrieval needed, so don't gate.
    if _is_capability_query(query):
        dept_name = dept_config.get("name", dept_id)
        llm = ChatOpenAI(base_url=settings.LLM_BASE_URL, model=settings.LLM_MODEL,
                         api_key="not-needed", temperature=0.2)
        sys_prompt = (
            f"You are the AI agent for the {dept_name} department of Brooker Group. "
            f"Describe your role, mandate, and what you can help with, based ONLY on "
            f"your skill below. Be concise (2-4 sentences). Do not invent metrics or data.\n\n"
            f"Your skill:\n{skill_content or '(no skill loaded)'}"
        )
        try:
            resp = await llm.ainvoke([
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": query},
            ])
            answer = resp.content.strip()
        except Exception as exc:  # noqa: BLE001
            log.warning("capability_answer_failed dept=%s error=%s", dept_id, exc)
            answer = f"I'm the {dept_name} agent for Brooker Group. Ask me about this department's documents and I'll answer with citations."
        latency = int((time.monotonic() - start) * 1000)
        _log_daily(dept_id, user_id, query, answer, [], latency)
        return {"response": answer, "citations": [], "dept_id": dept_id,
                "chunks_retrieved": 0, "latency_ms": latency}
    # ─────────────────────────────────────────────────────────────────────────

    chunks = await _search_collections(query, collections)

    # ── Grounding gate ────────────────────────────────────────────────────────
    # If no chunk clears the minimum relevance threshold, the LLM has nothing
    # reliable to cite.  Return a fixed abstention response so it can never
    # fabricate confident-sounding answers backed by thin or empty context.
    _ABSTAIN_RESPONSE = (
        "I don't have reference material on this topic in my knowledge base yet. "
        "Please share a relevant document and I'll analyze it."
    )
    grounded_chunks = [c for c in chunks if c.get("score", 0.0) >= settings.RAG_MIN_RELEVANCE]
    if not grounded_chunks:
        latency = int((time.monotonic() - start) * 1000)
        log.info(
            "grounding_gate_triggered dept=%s chunks_total=%d threshold=%.2f latency_ms=%d",
            dept_id, len(chunks), settings.RAG_MIN_RELEVANCE, latency,
        )
        _log_daily(dept_id, user_id, query, _ABSTAIN_RESPONSE, [], latency)
        return {
            "response": _ABSTAIN_RESPONSE,
            "citations": [],
            "dept_id": dept_id,
            "chunks_retrieved": len(chunks),
            "latency_ms": latency,
        }
    # ─────────────────────────────────────────────────────────────────────────

    # Step 3: Format context (only grounded chunks pass through)
    context_parts = []
    sources = []
    for i, chunk in enumerate(grounded_chunks[:8]):
        ref = f"[{i+1}]"
        context_parts.append(f"{ref} {chunk.get('text', '')}")
        sources.append({"id": str(i+1), "text": chunk.get("text", ""), "source": chunk.get("source", "")})

    context_text = "\n\n".join(context_parts) if context_parts else "No relevant documents found."

    # Step 4: Synthesise answer
    dept_name = dept_config.get("name", dept_id)
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        api_key="not-needed",
        temperature=0.1,
    )

    # Supervisor routing: pick the ONE backend sub-agent for this query. The
    # main (dept) agent stays the Slack-facing supervisor; the chosen specialist
    # shapes the answer's focus. Only relevant sub-agent runs (route-to-relevant).
    specialist = await _pick_specialist(query, dept_config, llm)
    focus = ""
    if specialist and specialist != "general":
        focus = (
            f"\n\nYou are the supervisor of the {dept_name}. This query is being handled by "
            f"your **{specialist}** sub-agent (backend). Answer with that specialist's focus, "
            f"strictly from the department skill and the retrieved context below."
        )

    system = SYSTEM_PROMPT.format(
        dept_name=dept_name,
        skill_content=skill_content,
        memory_content=memory,
    ) + focus

    user_prompt = f"Context:\n{context_text}\n\nQuestion: {query}"
    response = await llm.ainvoke([
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ])
    answer = response.content.strip()

    # Hard backstop: an answer that cites sources but verifies NONE of them is
    # fabrication — the model invented claims and attached citations that don't
    # support them. The grounding gate above blocks the zero-source case; this
    # catches weakly-relevant chunks that slipped through and got hallucinated on.
    if ground_citations is not None:
        report = ground_citations(answer, sources)
        if report.total_citations > 0 and report.verified == 0:
            latency = int((time.monotonic() - start) * 1000)
            log.warning(
                "ungrounded_replaced dept=%s citations=%d query=%s",
                dept_id, report.total_citations, query[:80],
            )
            _log_daily(dept_id, user_id, query, _ABSTENTION_ANSWER, [], latency)
            return {
                "response": _ABSTENTION_ANSWER,
                "citations": [],
                "dept_id": dept_id,
                "chunks_retrieved": len(chunks),
                "latency_ms": latency,
            }
        answer = add_grounding_badges(answer, report)

    # Attribute the backend sub-agent that handled it (transparency).
    if specialist and specialist != "general":
        answer = f"{answer}\n\n_— handled by the {specialist} sub-agent_"

    latency = int((time.monotonic() - start) * 1000)

    # ── Staging proposal (write-tier departments only) ─────────────────────
    # Runs AFTER the grounded answer is finalised. Gate logic inside:
    #   • capabilityTier must be "write" (finance, cio, vcc — NOT ic/read_only)
    #   • top chunk score must be >= STAGING_CONFIDENCE_THRESHOLD (default 0.85)
    #   • answer must contain a concrete value-change sentence
    # On success writes JSON manifest exclusively to /data/staging/pending/.
    # /data/mirror/ is NEVER written; ic is "read_only" so also skipped.
    top_score = grounded_chunks[0].get("score", 0.0) if grounded_chunks else 0.0
    proposal_id = await maybe_write_staging_proposal(
        dept_id=dept_id,
        dept_config=dept_config,
        answer=answer,
        query=query,
        user_id=user_id,
        specialist=specialist,
        top_chunk_score=top_score,
    )
    # ─────────────────────────────────────────────────────────────────────────

    # Step 5: Log interaction
    proposal_label = proposal_id if proposal_id else "none"
    _log_daily(dept_id, user_id, query, answer, sources, latency, proposal_label)

    result: dict = {
        "response": answer,
        "citations": [s["source"] for s in sources],
        "dept_id": dept_id,
        "specialist": specialist,
        "chunks_retrieved": len(chunks),
        "latency_ms": latency,
    }
    if proposal_id:
        result["proposal_id"] = proposal_id
    return result


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


async def _embed_query(text: str) -> list[float]:
    """Embed via rag-ingestion's /embed endpoint."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{_RAG_INGESTION_URL}/embed", json={"text": text})
        r.raise_for_status()
        return r.json()["vector"]


async def _search_collections(query: str, collections: list[str]) -> list[dict]:
    """Search multiple Qdrant collections with a real query vector."""
    try:
        vector = await _embed_query(query)
    except Exception as e:
        log.warning("embed_query_failed", exc_info=e)
        return []

    try:
        client = AsyncQdrantClient(url=settings.QDRANT_URL)
        results = []
        for collection in collections:
            try:
                resp = await client.query_points(
                    collection_name=collection,
                    query=vector,
                    limit=3,
                    with_payload=True,
                )
                for hit in resp.points:
                    results.append({
                        "text": hit.payload.get("text", ""),
                        "source": hit.payload.get("source", collection),
                        "score": hit.score,
                    })
            except Exception as e:
                log.warning("qdrant_search_failed collection=%s err=%r", collection, e)

        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[:8]
    except Exception:
        log.exception("Qdrant search failed")
        return []


def _log_daily(
    dept_id: str,
    user_id: str,
    query: str,
    answer: str,
    sources: list,
    latency: int,
    proposal_label: str = "none",
) -> None:
    """Append to daily log file."""
    from datetime import datetime
    vault = Path(settings.VAULT_ROOT) / dept_id / "daily-logs"
    vault.mkdir(parents=True, exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    now = datetime.utcnow().strftime("%H:%M")

    entry = (
        f"\n## {now} · @{user_id} · proposal: {proposal_label}\n"
        f"**Q:** {query}\n**A:** {answer[:500]}\n"
        f"**Latency:** {latency}ms\n**Outcome:** n/a\n"
    )
    with (vault / f"{today}.md").open("a", encoding="utf-8") as f:
        f.write(entry)
