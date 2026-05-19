"""Post-generation citation grounding — verify LLM citations match actual sources."""
import logging
import re
from difflib import SequenceMatcher
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

@dataclass
class GroundingResult:
    citation_ref: str  # e.g., "[1]"
    source_id: str
    claim_text: str  # the text around the citation
    source_text: str  # the actual source chunk
    similarity: float  # how well the claim matches the source
    verified: bool  # similarity > threshold

@dataclass
class GroundingReport:
    total_citations: int = 0
    verified: int = 0
    unverified: int = 0
    accuracy: float = 0.0
    details: list[GroundingResult] = field(default_factory=list)


def ground_citations(
    answer: str,
    sources: list[dict],  # [{"id": "1", "text": "...", "source": "..."}]
    threshold: float = 0.3,
) -> GroundingReport:
    """Verify that each [N] citation in the answer is supported by the corresponding source.

    Args:
        answer: The LLM-generated answer with [N] citations
        sources: List of source chunks, indexed by position
        threshold: Minimum similarity for a citation to be "verified"

    Returns:
        GroundingReport with per-citation verification results
    """
    report = GroundingReport()

    # Find all citations in the answer
    citation_pattern = re.compile(r'\[(\d+)\]')
    matches = list(citation_pattern.finditer(answer))
    report.total_citations = len(matches)

    if not matches or not sources:
        report.accuracy = 1.0 if not matches else 0.0
        return report

    # Build source index
    source_map = {}
    for i, src in enumerate(sources):
        source_map[str(i + 1)] = src.get("text", "")
        if "id" in src:
            source_map[src["id"]] = src.get("text", "")

    for i, match in enumerate(matches):
        ref_num = match.group(1)
        source_text = source_map.get(ref_num, "")

        if not source_text:
            report.details.append(GroundingResult(
                citation_ref=f"[{ref_num}]",
                source_id=ref_num,
                claim_text="",
                source_text="(source not found)",
                similarity=0.0,
                verified=False,
            ))
            report.unverified += 1
            continue

        # Extract the claim — text between the previous citation (or sentence start)
        # and the current citation marker, to avoid spilling into adjacent claims.
        pos = match.start()
        # Left boundary: end of previous citation, or start of sentence ('. ' boundary)
        if i > 0:
            prev_end = matches[i - 1].end()
            # Also check for a '. ' sentence boundary between prev citation and here
            sent_boundary = answer.rfind('. ', prev_end, pos)
            start = (sent_boundary + 2) if sent_boundary != -1 else prev_end
        else:
            boundary_before = answer.rfind('. ', 0, pos)
            start = (boundary_before + 2) if boundary_before != -1 else 0
        # Right boundary: include up to and including the citation marker
        end = match.end()
        claim = answer[start:end].strip()
        # Remove citation markers from claim for comparison
        claim_clean = citation_pattern.sub('', claim).strip()

        # Compare claim against source
        similarity = SequenceMatcher(None, claim_clean.lower(), source_text.lower()).ratio()

        # Also check if key phrases from the claim appear in the source
        claim_words = set(claim_clean.lower().split())
        source_words = set(source_text.lower().split())
        word_overlap = len(claim_words & source_words) / max(len(claim_words), 1)

        # Combined score
        combined = (similarity + word_overlap) / 2
        verified = combined >= threshold

        result = GroundingResult(
            citation_ref=f"[{ref_num}]",
            source_id=ref_num,
            claim_text=claim_clean[:200],
            source_text=source_text[:200],
            similarity=round(combined, 3),
            verified=verified,
        )
        report.details.append(result)

        if verified:
            report.verified += 1
        else:
            report.unverified += 1
            log.warning(
                "Citation [%s] unverified (similarity=%.2f): claim='%s' source='%s'",
                ref_num, combined, claim_clean[:80], source_text[:80]
            )

    report.accuracy = report.verified / report.total_citations if report.total_citations > 0 else 1.0
    return report


def add_grounding_badges(answer: str, report: GroundingReport) -> str:
    """Append grounding status to the answer for transparency."""
    if report.total_citations == 0:
        return answer

    badge = f"\n\n---\n_Citation verification: {report.verified}/{report.total_citations} verified"
    if report.unverified > 0:
        unverified_refs = [d.citation_ref for d in report.details if not d.verified]
        badge += f" | Unverified: {', '.join(unverified_refs)}"
    badge += "_"
    return answer + badge
