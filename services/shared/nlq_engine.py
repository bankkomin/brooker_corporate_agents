"""Natural Language Query engine — converts questions to structured data queries."""
import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class NLQResult:
    original_query: str
    query_type: str  # metric_lookup, trend_analysis, comparison, filter
    sql_query: str | None  # generated SQL (for structured data)
    parameters: dict
    explanation: str


# Pattern matchers for common query types
PATTERNS = [
    {
        "pattern": r"(?:show|list|find)\s+(?:all\s+)?(?:funds?|departments?)\s+(?:where|with)\s+(.+)",
        "type": "filter",
        "handler": "_handle_filter",
    },
    {
        "pattern": r"(?:what|how)\s+(?:is|was|are)\s+(?:the\s+)?(.+?)(?:\s+(?:for|in|of)\s+(.+))?$",
        "type": "metric_lookup",
        "handler": "_handle_metric_lookup",
    },
    {
        "pattern": r"(?:compare|difference|vs)\s+(.+?)\s+(?:and|vs|versus|with)\s+(.+)",
        "type": "comparison",
        "handler": "_handle_comparison",
    },
    {
        "pattern": r"(?:trend|how has|history of)\s+(.+?)(?:\s+(?:over|in|for)\s+(?:the\s+)?(?:last\s+)?(\d+)\s*(days?|weeks?|months?|quarters?))?",
        "type": "trend_analysis",
        "handler": "_handle_trend",
    },
]

# Metric name mapping
METRIC_MAP = {
    "approval rate": ("approval_decisions", "COUNT(CASE WHEN action='approved' THEN 1 END)::float / COUNT(*)", "dept_id"),
    "accuracy": ("eval_runs", "accuracy", "dept_id"),
    "latency": ("eval_runs", "avg_latency_ms", "dept_id"),
    "proposals": ("staging_proposals", "COUNT(*)", "dept_id"),
    "knowledge gaps": ("agent_knowledge_gaps", "COUNT(*)", "dept_id"),
    "signal strength": ("agent_performance", "AVG(signal_strength)", "dept_id"),
}


def parse_nlq(query: str) -> NLQResult:
    """Parse a natural language query into a structured query."""
    query_clean = query.strip().rstrip("?.")

    for pattern_def in PATTERNS:
        match = re.search(pattern_def["pattern"], query_clean, re.IGNORECASE)
        if match:
            handler = globals().get(pattern_def["handler"])
            if handler:
                return handler(query, match)

    # Fallback: treat as a general text search
    return NLQResult(
        original_query=query,
        query_type="text_search",
        sql_query=None,
        parameters={"query": query},
        explanation=f"No structured pattern matched. Routing as free-text query.",
    )


def _handle_filter(query: str, match: re.Match) -> NLQResult:
    condition = match.group(1).strip()

    # Try to parse simple conditions
    parts = re.split(r"\s+(and|or)\s+", condition, flags=re.IGNORECASE)

    return NLQResult(
        original_query=query,
        query_type="filter",
        sql_query=None,  # would need LLM to generate safe SQL
        parameters={"conditions": parts},
        explanation=f"Filter query with conditions: {condition}",
    )


def _handle_metric_lookup(query: str, match: re.Match) -> NLQResult:
    metric_name = match.group(1).strip().lower()
    scope = match.group(2).strip() if match.group(2) else None

    metric_info = METRIC_MAP.get(metric_name)
    if metric_info:
        table, column, group_by = metric_info
        sql = f"SELECT {group_by}, {column} AS value FROM {table}"
        if scope:
            sql += f" WHERE {group_by} = '{scope}'"
        sql += f" GROUP BY {group_by} ORDER BY value DESC"

        return NLQResult(
            original_query=query,
            query_type="metric_lookup",
            sql_query=sql,
            parameters={"metric": metric_name, "scope": scope},
            explanation=f"Looking up {metric_name}" + (f" for {scope}" if scope else ""),
        )

    return NLQResult(
        original_query=query,
        query_type="metric_lookup",
        sql_query=None,
        parameters={"metric": metric_name, "scope": scope},
        explanation=f"Metric '{metric_name}' not in known metrics. Routing to RAG.",
    )


def _handle_comparison(query: str, match: re.Match) -> NLQResult:
    entity_a = match.group(1).strip()
    entity_b = match.group(2).strip()

    return NLQResult(
        original_query=query,
        query_type="comparison",
        sql_query=None,
        parameters={"entity_a": entity_a, "entity_b": entity_b},
        explanation=f"Comparing {entity_a} vs {entity_b}",
    )


def _handle_trend(query: str, match: re.Match) -> NLQResult:
    metric = match.group(1).strip()
    period_num = int(match.group(2)) if match.group(2) else 90
    period_unit = match.group(3) if match.group(3) else "days"

    days = period_num
    if "week" in period_unit:
        days = period_num * 7
    elif "month" in period_unit:
        days = period_num * 30
    elif "quarter" in period_unit:
        days = period_num * 90

    return NLQResult(
        original_query=query,
        query_type="trend_analysis",
        sql_query=None,
        parameters={"metric": metric, "days": days},
        explanation=f"Trend analysis for {metric} over {days} days",
    )
