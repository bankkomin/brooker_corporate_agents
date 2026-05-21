"""Calibrate confidence node — computes calibrated score ONCE before staging gate.

This node runs after excel_navigator and before the staging conditional so that
both staging_writer (the gate decision) and synthesise (the displayed label) use
the identical numeric value.  Audit bug #3 fix.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger("cac-orchestrator.calibrate")

try:
    from services.shared.calibrated_confidence import compute_confidence
except ImportError:
    compute_confidence = None  # type: ignore[assignment]


async def calibrate_confidence(state: dict) -> dict:
    """Compute calibrated confidence and store it as ``calibrated_confidence_score``.

    Falls back to the agent's raw ``confidence_score`` when the shared library is
    unavailable so the node is always safe to wire in.

    Returns:
        {"calibrated_confidence_score": float}
    """
    raw_score: float = state.get("confidence_score", 0.0)

    if compute_confidence is None:
        logger.debug(
            "calibrate_confidence_skipped",
            reason="shared_library_unavailable",
            fallback=raw_score,
        )
        return {"calibrated_confidence_score": raw_score}

    # Normalise sources into the shape compute_confidence expects.
    raw_sources: list[dict] = state.get("sources", []) or []
    chunks: list[dict] = []
    top_sim: float = 0.0
    for i, s in enumerate(raw_sources, start=1):
        text = s.get("text") or s.get("excerpt") or ""
        chunks.append({
            "id": str(i),
            "text": text,
            "source": s.get("filename") or s.get("type") or f"src{i}",
        })
        score = float(s.get("relevance_score") or s.get("score") or 0.0)
        if score > top_sim:
            top_sim = score

    # At this point in the graph the final synthesised answer does not exist yet.
    # Use the agent's analysis text as the best available proxy for verbatim-score
    # computation (whether the proposed value appears in a retrieved chunk).
    answer_proxy: str = state.get("agent_response", "")
    proposed_value: str | None = state.get("proposed_value")

    conf = compute_confidence(
        retrieved_chunks=chunks,
        top_similarity=top_sim,
        answer_text=answer_proxy,
        proposed_value=proposed_value,
    )

    logger.info(
        "confidence_calibrated",
        composite=conf.composite,
        label=conf.label,
        raw_agent_score=raw_score,
    )
    return {"calibrated_confidence_score": conf.composite}
