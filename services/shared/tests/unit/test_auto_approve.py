"""Tests for auto_approve module."""
import pytest

from services.shared.auto_approve import (
    AutoApproveRule,
    AutoApproveDecision,
    evaluate_auto_approve,
)


# --- Helpers ---

class FakeDBConn:
    """Fake database connection for testing."""

    def __init__(self, row=None):
        self._row = row

    async def fetchrow(self, query, *args):
        return self._row


def _make_rule(**overrides) -> AutoApproveRule:
    defaults = {
        "dept_id": "cac",
        "cell_pattern": r"LCR_\d+",
        "min_historical_approval_rate": 0.95,
        "min_sample_size": 30,
        "min_confidence": 0.90,
        "enabled": True,
    }
    defaults.update(overrides)
    return AutoApproveRule(**defaults)


def _make_proposal(**overrides) -> dict:
    defaults = {
        "id": "prop-001",
        "dept_id": "cac",
        "cell": "LCR_42",
        "confidence": 0.95,
    }
    defaults.update(overrides)
    return defaults


# --- Tests ---

class TestNoMatchingRule:
    @pytest.mark.asyncio
    async def test_no_rules(self):
        decision = await evaluate_auto_approve(_make_proposal(), [], None)
        assert decision.auto_approved is False
        assert "No matching auto-approve rule" in decision.reason

    @pytest.mark.asyncio
    async def test_wrong_dept(self):
        rule = _make_rule(dept_id="finance")
        decision = await evaluate_auto_approve(_make_proposal(), [rule], None)
        assert decision.auto_approved is False
        assert "No matching auto-approve rule" in decision.reason

    @pytest.mark.asyncio
    async def test_disabled_rule(self):
        rule = _make_rule(enabled=False)
        decision = await evaluate_auto_approve(_make_proposal(), [rule], None)
        assert decision.auto_approved is False

    @pytest.mark.asyncio
    async def test_cell_pattern_no_match(self):
        rule = _make_rule(cell_pattern=r"NSFR_\d+")
        decision = await evaluate_auto_approve(_make_proposal(), [rule], None)
        assert decision.auto_approved is False


class TestConfidenceCheck:
    @pytest.mark.asyncio
    async def test_confidence_below_threshold(self):
        rule = _make_rule(min_confidence=0.95)
        proposal = _make_proposal(confidence=0.80)
        decision = await evaluate_auto_approve(proposal, [rule], None)
        assert decision.auto_approved is False
        assert "Confidence 0.80 below threshold" in decision.reason

    @pytest.mark.asyncio
    async def test_confidence_exactly_at_threshold(self):
        """Confidence equal to threshold should pass the confidence check.

        It will still fail due to no DB connection (insufficient historical data).
        """
        rule = _make_rule(min_confidence=0.90)
        proposal = _make_proposal(confidence=0.90)
        decision = await evaluate_auto_approve(proposal, [rule], None)
        # Passes confidence but fails on historical data (no db)
        assert decision.auto_approved is False
        assert "Insufficient historical data" in decision.reason


class TestHistoricalDataCheck:
    @pytest.mark.asyncio
    async def test_no_db_connection(self):
        rule = _make_rule()
        proposal = _make_proposal()
        decision = await evaluate_auto_approve(proposal, [rule], None)
        assert decision.auto_approved is False
        assert "Insufficient historical data" in decision.reason

    @pytest.mark.asyncio
    async def test_insufficient_sample_size(self):
        db = FakeDBConn(row={"sample_size": 10, "rate": 0.98})
        rule = _make_rule(min_sample_size=30)
        proposal = _make_proposal()
        decision = await evaluate_auto_approve(proposal, [rule], db)
        assert decision.auto_approved is False
        assert "Insufficient historical data" in decision.reason
        assert "10 samples" in decision.reason

    @pytest.mark.asyncio
    async def test_low_historical_rate(self):
        db = FakeDBConn(row={"sample_size": 50, "rate": 0.80})
        rule = _make_rule(min_historical_approval_rate=0.95)
        proposal = _make_proposal()
        decision = await evaluate_auto_approve(proposal, [rule], db)
        assert decision.auto_approved is False
        assert "Historical approval rate 0.80 below threshold" in decision.reason


class TestAutoApproveSuccess:
    @pytest.mark.asyncio
    async def test_all_checks_pass(self):
        db = FakeDBConn(row={"sample_size": 50, "rate": 0.97})
        rule = _make_rule(
            min_confidence=0.90,
            min_sample_size=30,
            min_historical_approval_rate=0.95,
        )
        proposal = _make_proposal(confidence=0.95)
        decision = await evaluate_auto_approve(proposal, [rule], db)
        assert decision.auto_approved is True
        assert "Passed all checks" in decision.reason
        assert decision.historical_rate == 0.97
        assert decision.confidence == 0.95
        assert decision.rule_matched == r"LCR_\d+"

    @pytest.mark.asyncio
    async def test_decision_fields(self):
        db = FakeDBConn(row={"sample_size": 100, "rate": 0.99})
        rule = _make_rule()
        proposal = _make_proposal(id="prop-xyz", dept_id="cac", cell="LCR_99")
        decision = await evaluate_auto_approve(proposal, [rule], db)
        assert decision.proposal_id == "prop-xyz"
        assert decision.dept_id == "cac"
        assert decision.cell == "LCR_99"
        assert isinstance(decision, AutoApproveDecision)
