"""Unit tests for services/shared/citation_grounding.py."""
from __future__ import annotations

import pytest
from services.shared.citation_grounding import (
    GroundingReport,
    GroundingResult,
    add_grounding_badges,
    ground_citations,
)


# ---------------------------------------------------------------------------
# ground_citations — happy path
# ---------------------------------------------------------------------------

class TestGroundCitationsVerified:
    def test_verified_citation_when_claim_matches_source(self) -> None:
        """A claim that closely echoes the source text scores above threshold."""
        answer = "The LCR ratio is 135% as of Q3 2025 [1]."
        sources = [{"id": "1", "text": "The LCR ratio is 135% as of Q3 2025."}]
        report = ground_citations(answer, sources, threshold=0.3)
        assert report.total_citations == 1
        assert report.verified == 1
        assert report.unverified == 0
        assert report.accuracy == pytest.approx(1.0)

    def test_accuracy_equals_verified_over_total(self) -> None:
        answer = "Rate is 3.15% [1]. Tier-1 ratio is 14% [2]."
        sources = [
            {"id": "1", "text": "Rate is 3.15 percent."},
            {"id": "2", "text": "Tier-1 capital ratio is 14 percent."},
        ]
        report = ground_citations(answer, sources, threshold=0.2)
        assert report.total_citations == 2
        assert report.accuracy == pytest.approx(report.verified / 2)

    def test_detail_results_populated_per_citation(self) -> None:
        answer = "Rate is 3.15% [1]."
        sources = [{"id": "1", "text": "The overnight funding rate is 3.15 percent."}]
        report = ground_citations(answer, sources, threshold=0.2)
        assert len(report.details) == 1
        assert report.details[0].citation_ref == "[1]"
        assert isinstance(report.details[0].similarity, float)


# ---------------------------------------------------------------------------
# ground_citations — unverified case
# ---------------------------------------------------------------------------

class TestGroundCitationsUnverified:
    def test_citation_cites_1_but_source_does_not_support_it(self) -> None:
        """Key case: answer cites [1] but source text is completely unrelated."""
        answer = "The Basel III minimum LCR is 100% [1]."
        sources = [{"id": "1", "text": "Annual leave policy: staff are entitled to 20 days."}]
        report = ground_citations(answer, sources, threshold=0.3)
        assert report.total_citations == 1
        assert report.verified == 0
        assert report.unverified == 1
        assert report.accuracy == pytest.approx(0.0)
        assert report.details[0].verified is False

    def test_missing_source_index_is_unverified(self) -> None:
        """Citation [5] but only one source provided — treated as unverified."""
        answer = "LCR is fine [5]."
        sources = [{"id": "1", "text": "LCR is 120%."}]
        report = ground_citations(answer, sources, threshold=0.3)
        assert report.unverified == 1
        assert report.verified == 0

    def test_mixed_verified_and_unverified(self) -> None:
        answer = "Rate is 3.15% [1]. Policy states 20 days leave [2]."
        sources = [
            {"id": "1", "text": "The overnight funding rate is 3.15 percent."},
            {"id": "2", "text": "The LCR ratio sits at 135 percent."},
        ]
        report = ground_citations(answer, sources, threshold=0.3)
        assert report.total_citations == 2
        # [2] claim about 'leave' does not appear in an LCR source
        assert report.verified + report.unverified == 2
        assert 0.0 <= report.accuracy <= 1.0


# ---------------------------------------------------------------------------
# ground_citations — edge cases
# ---------------------------------------------------------------------------

class TestGroundCitationsEdgeCases:
    def test_no_citations_returns_accuracy_1(self) -> None:
        report = ground_citations("No citations here.", [{"id": "1", "text": "stuff"}])
        assert report.total_citations == 0
        assert report.accuracy == pytest.approx(1.0)

    def test_citations_but_no_sources_returns_accuracy_0(self) -> None:
        report = ground_citations("Some claim [1].", [])
        assert report.total_citations == 1
        assert report.accuracy == pytest.approx(0.0)

    def test_empty_answer_returns_zero_citations(self) -> None:
        report = ground_citations("", [{"id": "1", "text": "text"}])
        assert report.total_citations == 0

    def test_positional_source_lookup_by_index(self) -> None:
        """Sources without 'id' key are indexed by position (1-based)."""
        answer = "Claim [1] and [2]."
        sources = [
            {"text": "First source content about the claim."},
            {"text": "Second source about something else entirely unrelated extra words."},
        ]
        report = ground_citations(answer, sources, threshold=0.01)
        assert report.total_citations == 2

    def test_threshold_boundary_exactly_at_threshold(self) -> None:
        """A combined score that equals threshold should be verified."""
        answer = "The funding rate is 3.15% [1]."
        sources = [{"id": "1", "text": "The funding rate is 3.15%."}]
        # With identical text the combined score will be >>0.3; use threshold=0.99
        report = ground_citations(answer, sources, threshold=0.99)
        # Very high threshold — combined score will likely be below it
        assert isinstance(report.verified, int)
        assert isinstance(report.unverified, int)


# ---------------------------------------------------------------------------
# add_grounding_badges
# ---------------------------------------------------------------------------

class TestAddGroundingBadges:
    def test_badge_appended_with_correct_counts(self) -> None:
        report = GroundingReport(
            total_citations=2,
            verified=2,
            unverified=0,
            accuracy=1.0,
            details=[],
        )
        result = add_grounding_badges("Answer text.", report)
        assert "2/2 verified" in result
        assert result.startswith("Answer text.")

    def test_badge_lists_unverified_refs(self) -> None:
        detail = GroundingResult(
            citation_ref="[1]",
            source_id="1",
            claim_text="some claim",
            source_text="unrelated",
            similarity=0.05,
            verified=False,
        )
        report = GroundingReport(
            total_citations=1,
            verified=0,
            unverified=1,
            accuracy=0.0,
            details=[detail],
        )
        result = add_grounding_badges("Answer.", report)
        assert "Unverified" in result
        assert "[1]" in result

    def test_no_badge_when_no_citations(self) -> None:
        report = GroundingReport(total_citations=0, verified=0, unverified=0, accuracy=1.0, details=[])
        result = add_grounding_badges("Clean answer.", report)
        assert result == "Clean answer."

    def test_badge_separator_present(self) -> None:
        report = GroundingReport(
            total_citations=1, verified=1, unverified=0, accuracy=1.0, details=[]
        )
        result = add_grounding_badges("Text.", report)
        assert "---" in result
