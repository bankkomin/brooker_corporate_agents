"""Calibrated confidence scoring based on retrieval heuristics, not LLM self-report."""
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class ConfidenceBreakdown:
    retrieval_score: float  # based on number and quality of retrieved chunks
    verbatim_score: float  # does the answer value appear verbatim in sources?
    citation_score: float  # from grounding report
    history_score: float  # based on similar past proposals' approval rates
    composite: float  # weighted combination
    label: str  # "High", "Medium", "Low"
    explanation: str  # human-readable explanation


def compute_confidence(
    retrieved_chunks: list[dict],
    top_similarity: float,
    answer_text: str,
    proposed_value: str | None = None,
    citation_accuracy: float = 1.0,
    historical_approval_rate: float | None = None,
) -> ConfidenceBreakdown:
    """Compute calibrated confidence from measurable signals.

    Args:
        retrieved_chunks: List of retrieved Qdrant results
        top_similarity: Highest similarity score from retrieval
        answer_text: The generated answer
        proposed_value: If a staging proposal, the proposed value string
        citation_accuracy: From grounding report (0-1)
        historical_approval_rate: Past approval rate for similar proposals (0-1)
    """
    # 1. Retrieval score: how many relevant chunks did we find?
    num_chunks = len(retrieved_chunks)
    if num_chunks >= 5:
        retrieval_score = 0.9
    elif num_chunks >= 3:
        retrieval_score = 0.7
    elif num_chunks >= 1:
        retrieval_score = 0.4
    else:
        retrieval_score = 0.1

    # Boost/penalize by top similarity
    if top_similarity >= 0.85:
        retrieval_score = min(1.0, retrieval_score + 0.1)
    elif top_similarity < 0.5:
        retrieval_score = max(0.0, retrieval_score - 0.2)

    # 2. Verbatim score: does the proposed value appear exactly in a source?
    verbatim_score = 0.5  # default
    if proposed_value:
        for chunk in retrieved_chunks:
            chunk_text = chunk.get("text", "")
            if proposed_value in chunk_text:
                verbatim_score = 1.0
                break
            # Partial match — value appears with different formatting
            clean_value = proposed_value.replace("%", "").replace(",", "").strip()
            if clean_value and clean_value in chunk_text:
                verbatim_score = 0.8
                break
        else:
            verbatim_score = 0.2  # value not found in any source

    # 3. Citation score: from grounding
    citation_score = citation_accuracy

    # 4. History score: how often are similar proposals approved?
    if historical_approval_rate is not None:
        history_score = historical_approval_rate
    else:
        history_score = 0.5  # unknown

    # Weighted composite
    weights = {
        "retrieval": 0.30,
        "verbatim": 0.30,
        "citation": 0.20,
        "history": 0.20,
    }

    composite = (
        weights["retrieval"] * retrieval_score
        + weights["verbatim"] * verbatim_score
        + weights["citation"] * citation_score
        + weights["history"] * history_score
    )

    # Label
    if composite >= 0.75:
        label = "High"
    elif composite >= 0.50:
        label = "Medium"
    else:
        label = "Low"

    # Human-readable explanation
    parts = []
    parts.append(f"Based on {num_chunks} matching documents (top similarity: {top_similarity:.0%})")
    if proposed_value:
        if verbatim_score >= 0.8:
            parts.append(f"Value '{proposed_value}' found in source documents")
        else:
            parts.append(f"Value '{proposed_value}' NOT found verbatim in sources")
    if citation_accuracy < 0.8:
        parts.append(f"Citation verification: {citation_accuracy:.0%}")
    if historical_approval_rate is not None:
        parts.append(f"Historical approval rate for similar proposals: {historical_approval_rate:.0%}")

    explanation = ". ".join(parts) + "."

    return ConfidenceBreakdown(
        retrieval_score=round(retrieval_score, 3),
        verbatim_score=round(verbatim_score, 3),
        citation_score=round(citation_score, 3),
        history_score=round(history_score, 3),
        composite=round(composite, 3),
        label=label,
        explanation=explanation,
    )
