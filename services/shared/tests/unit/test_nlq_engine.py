"""Tests for nlq_engine module."""

from services.shared.nlq_engine import NLQResult, parse_nlq


class TestMetricLookup:
    def test_known_metric(self):
        result = parse_nlq("What is the approval rate?")
        assert result.query_type == "metric_lookup"
        assert result.parameters["metric"] == "approval rate"
        assert result.sql_query is not None
        assert "approval_decisions" in result.sql_query

    def test_known_metric_with_scope(self):
        result = parse_nlq("What is the accuracy for cac?")
        assert result.query_type == "metric_lookup"
        assert result.parameters["metric"] == "accuracy"
        assert result.parameters["scope"] == "cac"
        assert "WHERE" in result.sql_query

    def test_unknown_metric(self):
        result = parse_nlq("What is the turnover rate?")
        assert result.query_type == "metric_lookup"
        assert result.sql_query is None
        assert "not in known metrics" in result.explanation

    def test_latency_metric(self):
        result = parse_nlq("What is the latency?")
        assert result.query_type == "metric_lookup"
        assert result.parameters["metric"] == "latency"
        assert "eval_runs" in result.sql_query


class TestTrendAnalysis:
    def test_trend_with_days(self):
        result = parse_nlq("trend of accuracy over the last 30 days")
        assert result.query_type == "trend_analysis"
        assert result.parameters["metric"] == "accuracy"
        assert result.parameters["days"] == 30

    def test_trend_with_weeks(self):
        result = parse_nlq("trend of latency over 4 weeks")
        assert result.query_type == "trend_analysis"
        assert result.parameters["days"] == 28

    def test_trend_with_months(self):
        result = parse_nlq("history of proposals over 3 months")
        assert result.query_type == "trend_analysis"
        assert result.parameters["days"] == 90

    def test_trend_with_quarters(self):
        result = parse_nlq("trend of signal strength over 2 quarters")
        assert result.query_type == "trend_analysis"
        assert result.parameters["days"] == 180

    def test_trend_default_period(self):
        result = parse_nlq("how has accuracy changed")
        assert result.query_type == "trend_analysis"
        assert result.parameters["days"] == 90  # default


class TestComparison:
    def test_compare_two_entities(self):
        result = parse_nlq("compare cac and finance")
        assert result.query_type == "comparison"
        assert result.parameters["entity_a"] == "cac"
        assert result.parameters["entity_b"] == "finance"

    def test_compare_with_vs(self):
        result = parse_nlq("compare fund A vs fund B")
        assert result.query_type == "comparison"
        assert result.parameters["entity_a"] == "fund A"
        assert result.parameters["entity_b"] == "fund B"

    def test_compare_with_versus(self):
        result = parse_nlq("compare Q1 versus Q2")
        assert result.query_type == "comparison"
        assert result.parameters["entity_a"] == "Q1"
        assert result.parameters["entity_b"] == "Q2"


class TestFilter:
    def test_simple_filter(self):
        result = parse_nlq("show all funds where NAV > 100")
        assert result.query_type == "filter"
        assert "conditions" in result.parameters

    def test_filter_with_and(self):
        result = parse_nlq("list departments where headcount > 10 and budget > 1M")
        assert result.query_type == "filter"
        conditions = result.parameters["conditions"]
        assert len(conditions) == 3  # two conditions + "and"

    def test_find_filter(self):
        result = parse_nlq("find funds with AUM above 500M")
        assert result.query_type == "filter"


class TestFallback:
    def test_unrecognized_query(self):
        result = parse_nlq("Tell me something interesting")
        assert result.query_type == "text_search"
        assert result.sql_query is None
        assert "No structured pattern matched" in result.explanation

    def test_random_text(self):
        result = parse_nlq("xyzzy plugh")
        assert result.query_type == "text_search"

    def test_result_is_nlq_result(self):
        result = parse_nlq("hello world")
        assert isinstance(result, NLQResult)
        assert result.original_query == "hello world"
