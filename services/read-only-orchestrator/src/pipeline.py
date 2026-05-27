"""Simplified read-only query pipeline: embed → search → format → synthesise → log."""
import asyncio
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

# The shared DGX Spark fails beyond a few concurrent sequences. Cap concurrent
# LLM calls per process; extra calls await a free slot (clean queue, no reject).
LLM_MAX_CONCURRENCY = int(os.getenv("LLM_MAX_CONCURRENCY", "4"))
_DGX_SEMAPHORE = asyncio.Semaphore(LLM_MAX_CONCURRENCY)


async def _ainvoke_capped(llm, messages):
    """llm.ainvoke under the DGX concurrency cap."""
    async with _DGX_SEMAPHORE:
        return await llm.ainvoke(messages)

# Fallback when no contextual builder is available.
_ABSTENTION_ANSWER = (
    "I don't have reference material on this topic in my knowledge base yet. "
    "Please share a relevant document and I'll analyze it."
)

# What each dept agent is actually grounded in — used in abstain messages so the
# user knows which records the agent owns, instead of a generic "no reference".
_DEPT_SOURCE_LABEL = {
    "finance": "BICL audited financial statements + corporate records",
    "ib":      "investment-banking transaction documents + deal pipeline",
    "ic":      "investment committee minutes, decisions, valuation reports",
    "cio":     "CIO investment-cluster materials (NAV, custodian, on-chain)",
    "vcc":     "VCC fund offering documents + service-provider contracts",
    "ceo":     "CEO strategy, Board resolutions, North Star OKRs",
    "comms":   "communications knowledge base",
    "risk":    "risk policies + limits + escalation rules",
    "legal":   "external-counsel opinions + signed instruments",
    "hr":      "HR policy + self-assessment + role records",
    "it":      "infrastructure, security, devops runbooks",
}

_URL_RE = re.compile(r"https?://\S+")
_SHAREPOINT_RE = re.compile(r"sharepoint\.com|1drv\.ms|onedrive", re.I)


def _abstain(query: str, dept_id: str, dept_config: dict) -> str:
    """Context-aware abstain.

    The generic "please share a relevant document" message contradicts the user
    when they JUST shared one (and ignores channel context entirely). This:
      - names what THIS dept's agent is actually grounded in,
      - acknowledges any link in the query instead of telling them to share one,
      - routes SharePoint/OneDrive xlsx links to #cac-committee where the CAC
        report pipeline can actually open them.
    """
    dept_name = (dept_config or {}).get("name") or dept_id.upper()
    source = _DEPT_SOURCE_LABEL.get(dept_id, f"{dept_name} ingested records")
    q = query or ""
    has_url = bool(_URL_RE.search(q))
    is_share = bool(_SHAREPOINT_RE.search(q))

    base = (f"I don't have an answer for that in the {dept_name} agent's ingested "
            f"records ({source}).")
    if is_share:
        return (f"{base} I can see the SharePoint/OneDrive link you shared, but my "
                f"chat path can't open external files — only the CAC report pipeline "
                f"reads them. If that's the CAC Monthly Data Pack, post in "
                f"#cac-committee with \"produce CAC report from this link\" and "
                f"you'll get the .docx with the figures.")
    if has_url:
        return (f"{base} The link in your message isn't a source I can fetch from "
                f"this channel — upload the file directly here and I'll ingest it.")
    return (f"{base} Share the relevant document (PDF / Word / Excel) directly in "
            f"this channel and I'll ingest and analyse it.")

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
    specialists.

    Uses direct httpx (not LangChain) for the routing call because LangChain's
    ChatOpenAI.ainvoke() occasionally returns only-whitespace content for short
    classification tasks with this model, while the raw API returns the correct
    single-token answer. Retries once on whitespace response before falling back.
    """
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
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": query},
    ]
    for attempt in range(2):
        try:
            async with _DGX_SEMAPHORE:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.post(
                        f"{settings.LLM_BASE_URL}/chat/completions",
                        json={
                            "model": settings.LLM_MODEL,
                            "messages": messages,
                            "max_tokens": 10,
                            "temperature": 0.0,
                        },
                    )
                    r.raise_for_status()
                    data = r.json()
            content = (data["choices"][0]["message"].get("content") or "").strip().lower()
            tokens = content.split()
            if tokens:
                pick = tokens[0].strip(".,:;\"'")
                if pick in names:
                    return pick
                # LLM returned a word but it's not in the list — still usable as "general"
                log.debug(
                    "specialist_routing_unknown dept=%s pick=%s names=%s",
                    dept_config.get("name"), pick, names,
                )
                return "general"
            # Whitespace-only response — retry once
            log.warning(
                "specialist_routing_empty dept=%s attempt=%d — LLM returned whitespace",
                dept_config.get("name"), attempt + 1,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("specialist_routing_failed dept=%s error=%s",
                        dept_config.get("name"), exc)
            break
    # Both LLM routing attempts returned whitespace. Fall back to keyword matching
    # against the specialist names so we still give a focused context hint rather
    # than the generic 'general' which can trigger synthesis prompt confusion.
    query_lower = query.lower()
    for name in names:
        if name in query_lower or any(tok in query_lower for tok in name.split("-")):
            log.debug("specialist_routing_keyword_fallback dept=%s pick=%s",
                      dept_config.get("name"), name)
            return name
    return "general"

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a corporate AI assistant for the {dept_name} department.
Answer questions using the provided context. Cite sources using [N] format.
Be precise, factual, and professional. If no relevant sources found, say so clearly.
Never speculate beyond what the sources state.

ANSWERING RULES (these reduce hallucination):
1. Quote KEY facts (numbers, names, dates) verbatim from the source chunks —
   do not paraphrase numbers; do not synthesise a number from multiple chunks.
2. If a chunk has a "Quick-answer aliases" section with a Q&A that matches the
   user's question, PREFER it — that's the canonical phrasing of the answer.
3. Match the SPECIFIC metric named in the question (e.g. "AUM target" ≠
   "recurring income target"; "FoF Management Fee" ≠ "TSA residual fee";
   "PN.35 principal" ≠ "PN.36 principal").

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
            resp = await _ainvoke_capped(llm, [
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

    # ── Pre-RAG SharePoint guard ──────────────────────────────────────────────
    # A SharePoint/OneDrive link in the query means the user shared an external
    # file. The chat path CAN'T open it (only the cac-report pipeline calls MS
    # Graph), so RAG'ing anyway risks a confidently-cited but irrelevant answer
    # — e.g. a textbook D/E definition when the user asked about the value IN the
    # link. Short-circuit straight to the link-aware abstain so we never pretend
    # to have read the file.
    if _SHAREPOINT_RE.search(query or ""):
        latency = int((time.monotonic() - start) * 1000)
        answer_sp = _abstain(query, dept_id, dept_config)
        log.info(
            "sharepoint_link_short_circuit dept=%s latency_ms=%d",
            dept_id, latency,
        )
        _log_daily(dept_id, user_id, query, answer_sp, [], latency)
        return {
            "response": answer_sp,
            "citations": [],
            "dept_id": dept_id,
            "chunks_retrieved": 0,
            "latency_ms": latency,
        }

    chunks = await _search_collections(query, collections)

    # ── Grounding gate ────────────────────────────────────────────────────────
    # If no chunk clears the minimum relevance threshold, the LLM has nothing
    # reliable to cite.  Return a fixed abstention response so it can never
    # fabricate confident-sounding answers backed by thin or empty context.
    grounded_chunks = [c for c in chunks if c.get("score", 0.0) >= settings.RAG_MIN_RELEVANCE]
    if not grounded_chunks:
        latency = int((time.monotonic() - start) * 1000)
        log.info(
            "grounding_gate_triggered dept=%s chunks_total=%d threshold=%.2f latency_ms=%d",
            dept_id, len(chunks), settings.RAG_MIN_RELEVANCE, latency,
        )
        answer = _abstain(query, dept_id, dept_config)
        _log_daily(dept_id, user_id, query, answer, [], latency)
        return {
            "response": answer,
            "citations": [],
            "dept_id": dept_id,
            "chunks_retrieved": len(chunks),
            "latency_ms": latency,
        }
    # ─────────────────────────────────────────────────────────────────────────

    # Step 2.5: Cross-encoder rerank — re-score grounded chunks against the
    # query and take top-8. Round-robin merge guarantees dept-specific chunks
    # reach the candidate pool; the cross-encoder then ranks the *right* chunk
    # first regardless of where the original embedding placed it. Big stability
    # win on the previously-flaky factual tests.
    grounded_chunks = await _rerank_chunks(query, grounded_chunks, top_k=8)

    # Step 3: Format context (top-K reranked chunks pass through)
    # _chat collection chunks are raw daily-log entries: previous Q&A pairs with
    # nested [N] citations, attribution stubs, and latency/metadata lines.
    # The Q&A structure confuses the synthesis LLM — it treats the context as a
    # partially-completed conversation and outputs only a citation ref ("Answer",
    # "[1]", "[1][2][3]") instead of a full answer. Exclude them from synthesis
    # context entirely; the _knowledge and _docs collections carry the grounded
    # facts and are free of this structural noise.
    context_parts = []
    sources = []
    for i, chunk in enumerate(grounded_chunks):
        col = chunk.get("_col", "")
        if col.endswith("_chat"):
            # Skip chat-log chunks: raw Q&A conversation noise confuses synthesis
            log.debug(
                "context_skip_chat col=%s score=%.3f",
                col, chunk.get("score", 0.0),
            )
            continue
        src_num = len(context_parts) + 1
        clean_text = chunk.get("text", "")
        # Format: "Source [N]:\n<text>" — placing [N] AFTER "Source" avoids the model
        # treating "[N]" as a completion template to copy (which produces bare "[1]" answers
        # when the context chunk starts with a Q&A fragment). The source label is still
        # present so the model can cite with [N] inline.
        context_parts.append(f"Source [{src_num}]:\n{clean_text}")
        sources.append({"id": str(src_num), "text": clean_text, "source": chunk.get("source", "")})

    context_text = "\n\n".join(context_parts) if context_parts else "No relevant documents found."

    # Step 4: Synthesise answer
    dept_name = dept_config.get("name", dept_id)
    # Build a temp llm handle for _pick_specialist (routing needs it, though
    # the routing call itself now uses httpx internally).
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        api_key="not-needed",
        temperature=0.0,
    )

    # Supervisor routing: pick the ONE backend sub-agent for this query. The
    # main (dept) agent stays the Slack-facing supervisor; the chosen specialist
    # shapes the answer's focus. Only relevant sub-agent runs (route-to-relevant).
    specialist = await _pick_specialist(query, dept_config, llm)
    # Always append a synthesis directive so the LLM has an explicit instruction
    # at the end of the system prompt regardless of whether routing succeeded.
    # Without this, the system prompt can end with the memory markdown (e.g.
    # "## Known Gaps\n(none yet)") and the model produces only whitespace/1 token.
    if specialist and specialist != "general":
        focus = (
            f"\n\nYou are the supervisor of the {dept_name}. This query is being handled by "
            f"your **{specialist}** sub-agent (backend). Answer with that specialist's focus, "
            f"strictly from the department skill and the retrieved context below."
        )
    else:
        focus = (
            f"\n\nYou are the AI agent for the {dept_name}. Answer the user's question "
            f"strictly from the department skill and the retrieved context below. "
            f"Cite each fact with [N]. Write a complete sentence."
        )

    system = SYSTEM_PROMPT.format(
        dept_name=dept_name,
        skill_content=skill_content,
        memory_content=memory,
    ) + focus

    user_prompt = f"Context:\n{context_text}\n\nQuestion: {query}"

    # Use direct httpx for the synthesis call — LangChain's ChatOpenAI.ainvoke()
    # intermittently returns all-whitespace content on this vLLM endpoint (the
    # raw API always returns the correct completion). Bypassing LangChain here
    # eliminates the ~40% whitespace-response failure rate for synthesis.
    answer = ""
    _synthesis_raw_data: dict = {}
    _MIN_ANSWER_LEN = 10
    # Retry MUST break determinism — at temperature 0.0 a whitespace response
    # is repeatable, so attempt 2 with the same prompt returns the same garbage.
    # Bump temperature + nudge the prompt on retry to actually try something
    # different. Observed Qwen pathology: "what are our BTC holdings per the
    # coin book?" → 1024 newlines, finish=length. The retry must vary.
    _attempt_user_prompts = [
        user_prompt,
        user_prompt + (
            "\n\nIMPORTANT: Respond with a clear, complete sentence using the "
            "facts above. Do not output blank lines. Begin your answer with the "
            "answer itself, not a preamble."
        ),
    ]
    _attempt_temperatures = [0.0, 0.4]
    for _synthesis_attempt in range(2):
        try:
            async with _DGX_SEMAPHORE:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    r = await client.post(
                        f"{settings.LLM_BASE_URL}/chat/completions",
                        json={
                            "model": settings.LLM_MODEL,
                            "messages": [
                                {"role": "system", "content": system},
                                {"role": "user", "content": _attempt_user_prompts[_synthesis_attempt]},
                            ],
                            "max_tokens": 1024,
                            "temperature": _attempt_temperatures[_synthesis_attempt],
                        },
                    )
                    r.raise_for_status()
                    _synthesis_raw_data = r.json()
            choice = _synthesis_raw_data["choices"][0]
            answer = (choice["message"].get("content") or "").strip()
            _usage = _synthesis_raw_data.get("usage", {})
            log.debug(
                "synthesis_raw dept=%s attempt=%d finish=%s prompt_tok=%s comp_tok=%s answer_len=%d",
                dept_id, _synthesis_attempt + 1,
                choice.get("finish_reason"),
                _usage.get("prompt_tokens"),
                _usage.get("completion_tokens"),
                len(answer),
            )
            if len(answer) >= _MIN_ANSWER_LEN:
                break  # good answer — exit retry loop
            # Whitespace / too-short answer — retry once
            log.warning(
                "synthesis_short_attempt dept=%s attempt=%d answer_len=%d finish=%s comp_tok=%s raw=%r",
                dept_id, _synthesis_attempt + 1, len(answer),
                choice.get("finish_reason"),
                _usage.get("completion_tokens"),
                (choice["message"].get("content") or "")[:50],
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("synthesis_llm_failed dept=%s attempt=%d error=%s",
                        dept_id, _synthesis_attempt + 1, exc)
            break

    # Guard: if both synthesis attempts returned empty/degenerate content, replace
    # with a clean abstain. Must run BEFORE grounding badges are appended.
    if len(answer) < _MIN_ANSWER_LEN:
        _diag_choice = (_synthesis_raw_data.get("choices") or [{}])[0]
        _diag_usage = _synthesis_raw_data.get("usage", {})
        log.warning(
            "synthesis_empty dept=%s specialist=%s answer_len=%d "
            "finish=%s prompt_tok=%s comp_tok=%s raw=%r query=%s",
            dept_id, specialist, len(answer),
            _diag_choice.get("finish_reason"),
            _diag_usage.get("prompt_tokens"),
            _diag_usage.get("completion_tokens"),
            ((_diag_choice.get("message") or {}).get("content") or "")[:50],
            query[:80],
        )
        latency = int((time.monotonic() - start) * 1000)
        answer_abs = _abstain(query, dept_id, dept_config)
        _log_daily(dept_id, user_id, query, answer_abs, [], latency)
        return {
            "response": answer_abs,
            "citations": [],
            "dept_id": dept_id,
            "specialist": specialist,
            "chunks_retrieved": len(chunks),
            "latency_ms": latency,
        }

    # Hard backstop: an answer that cites sources but verifies NONE of them is
    # fabrication — the model invented claims and attached citations that don't
    # support them. The grounding gate above blocks the zero-source case; this
    # catches weakly-relevant chunks that slipped through and got hallucinated on.
    # Only run the post-LLM hallucination backstop when there ARE sources to
    # verify against. Capability / conversational answers pass through with no
    # sources; the LLM may emit decorative [N] markers, but with nothing to
    # verify they'd all read "unverified" and a legitimate answer would be
    # wrongly replaced by an abstain. See cac-orchestrator/synthesise.py.
    if ground_citations is not None and sources:
        report = ground_citations(answer, sources)
        # Only replace with abstain if there are citations with non-empty claim
        # text that all failed verification.  Citations at position-0 (e.g.
        # "[1] 164.6554 BTC") produce empty claim_text because there's no
        # preceding sentence — that's a structural artefact, not fabrication.
        # Firing on those would incorrectly replace a grounded answer.
        substantive_failures = [
            d for d in report.details if not d.verified and d.claim_text.strip()
        ]
        if report.total_citations > 0 and report.verified == 0 and substantive_failures:
            latency = int((time.monotonic() - start) * 1000)
            log.warning(
                "ungrounded_replaced dept=%s citations=%d query=%s",
                dept_id, report.total_citations, query[:80],
            )
            answer_abs = _abstain(query, dept_id, dept_config)
            _log_daily(dept_id, user_id, query, answer_abs, [], latency)
            return {
                "response": answer_abs,
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


_MEMORY_EMPTY_SECTION_RE = re.compile(
    # Remove any "## Heading\n(none ...)" block — these placeholder sections add
    # ~300+ chars of markdown structure that confuse the synthesis LLM into treating
    # the system prompt as a fill-in-the-blanks template (outputs "\n\n" then stops).
    r"^##[^\n]*\n\(none[^)]*\)\s*$",
    re.MULTILINE,
)
# Strip the "## How I work" section and everything after it — these are
# instruction-like lines that duplicate the system prompt rules and cause the
# model to treat the prompt as a meta-instructions doc and output "\n\n" (stop).
_MEMORY_HOW_I_WORK_RE = re.compile(
    r"\n##\s*How I work.*$",
    re.DOTALL,
)
_MEMORY_TRAILING_DASHES_RE = re.compile(r"\n---\s*$")

# Maximum chars to include from each memory file. soul.md can be ~1700+ chars;
# keeping only the mandate/capabilities section (first ~600) avoids the
# instruction-dense trailing sections that confuse synthesis.
_MEMORY_FILE_MAX_CHARS = 600


def _load_memory(dept_id: str, dept_config: dict) -> str:
    """Load agent memory triad if available.

    Only the mandate section of each file is kept (first _MEMORY_FILE_MAX_CHARS
    chars) after stripping placeholder sections and instruction-duplicate blocks.
    Long, instruction-dense memory content causes the synthesis LLM to treat the
    system prompt as a template document (outputs '\\n\\n' then stops) rather than
    answering the user's question.
    """
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
                        # Strip "How I work" block (duplicates system prompt rules)
                        content = _MEMORY_HOW_I_WORK_RE.sub("", content).strip()
                        # Strip empty placeholder sections
                        content = _MEMORY_EMPTY_SECTION_RE.sub("", content).strip()
                        content = _MEMORY_TRAILING_DASHES_RE.sub("", content).strip()
                        # Cap length — keep mandate section only
                        content = content[:_MEMORY_FILE_MAX_CHARS]
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


_RERANK_URL = os.getenv("EMBED_RERANK_URL", "http://host.docker.internal:8765/rerank")
_RERANK_ENABLED = os.getenv("RERANK_ENABLED", "true").lower() != "false"


async def _rerank_chunks(query: str, chunks: list[dict], top_k: int = 8) -> list[dict]:
    """Re-score chunks against query via the embed server's cross-encoder and
    return top-K in score-descending order.

    Why: cosine sim on standalone embeddings is noisy on borderline factual
    queries — the cross-encoder (ms-marco-MiniLM) gives much sharper relevance
    scores (positive for matches, very negative for non-matches), which sorts
    the right answer to the top of the LLM's context. Adds ~50-100ms latency.
    Disabled by setting RERANK_ENABLED=false in env (fail-safe fallback).
    """
    if not _RERANK_ENABLED or len(chunks) <= 1:
        return chunks[:top_k]
    try:
        docs = [(c.get("text") or "")[:1500] for c in chunks]
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(_RERANK_URL, json={"query": query, "documents": docs})
            r.raise_for_status()
            results = r.json().get("results", [])
        for item in results:
            i = item.get("index")
            if 0 <= i < len(chunks):
                chunks[i]["rerank_score"] = item.get("score", 0.0)
        chunks.sort(key=lambda c: c.get("rerank_score", -1e9), reverse=True)
        return chunks[:top_k]
    except Exception as e:
        log.warning("rerank_failed_using_original_order error=%r", e)
        return chunks[:top_k]


async def _search_collections(query: str, collections: list[str]) -> list[dict]:
    """Search multiple Qdrant collections, ROUND-ROBIN merging to guarantee each
    collection contributes to the final top-K.

    Why round-robin instead of global sort: `shared_policies` has ~811k chunks
    vs ~100-3000 in dept-specific collections; its top scores frequently dominate
    a global sort even when the dept-specific fact-chunk (e.g. "DBS Bank" in
    vcc_knowledge, "164.6554 BTC" in cio_knowledge) is well within that
    collection's top-K. Round-robin ensures the LLM sees dept-relevant context.

    Tunables: PER_COL is the candidate-pool size per collection (was 3, now 8 so
    that fact-chunks at ranks 4-8 within a collection survive); FINAL_K is the
    chunks passed to the LLM (was 8, now 16 to fit deeper round-robin without
    dropping any collection's contribution).
    """
    PER_COL = 8
    FINAL_K = 16

    try:
        vector = await _embed_query(query)
    except Exception as e:
        log.warning("embed_query_failed", exc_info=e)
        return []

    try:
        client = AsyncQdrantClient(url=settings.QDRANT_URL)
        chunks_by_col: dict[str, list[dict]] = {}
        for collection in collections:
            try:
                resp = await client.query_points(
                    collection_name=collection,
                    query=vector,
                    limit=PER_COL,
                    with_payload=True,
                )
                chunks_by_col[collection] = [
                    {
                        "text": hit.payload.get("text", ""),
                        "source": hit.payload.get("source", collection),
                        "score": hit.score,
                        "_col": collection,
                    }
                    for hit in resp.points
                ]
            except Exception as e:
                log.warning("qdrant_search_failed collection=%s err=%r", collection, e)
                chunks_by_col[collection] = []

        # Round-robin merge: rank-1 from each col, then rank-2 from each, etc.
        # Stops as soon as FINAL_K is reached. Order preserved so the LLM sees
        # higher-relevance chunks first.
        results: list[dict] = []
        for rank in range(PER_COL):
            for col in collections:
                if rank < len(chunks_by_col.get(col, [])):
                    results.append(chunks_by_col[col][rank])
                if len(results) >= FINAL_K:
                    return results
        return results
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
