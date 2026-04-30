"""Prometheus metrics for all services."""
from prometheus_client import Counter, Histogram, Gauge, Info

# Query metrics
QUERY_COUNTER = Counter(
    "agent_queries_total",
    "Total queries received",
    ["dept_id", "agent_id", "intent"]
)

QUERY_LATENCY = Histogram(
    "agent_query_duration_seconds",
    "Query processing time",
    ["dept_id", "agent_id"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

# RAG metrics
RAG_HITS = Histogram(
    "rag_retrieval_hits",
    "Number of chunks retrieved per query",
    ["dept_id", "collection"],
    buckets=[0, 1, 2, 3, 5, 8, 10, 15, 20]
)

RAG_TOP_SIMILARITY = Histogram(
    "rag_top_similarity_score",
    "Top chunk similarity score",
    ["dept_id"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Proposal metrics
PROPOSALS_CREATED = Counter(
    "staging_proposals_total",
    "Total staging proposals created",
    ["dept_id", "agent_id"]
)

PROPOSALS_DECIDED = Counter(
    "approval_decisions_total",
    "Approval decisions by action",
    ["dept_id", "action"]  # approved, edited, rejected
)

# Confidence metrics
CONFIDENCE_SCORES = Histogram(
    "agent_confidence_score",
    "Confidence score distribution",
    ["dept_id", "label"],  # High, Medium, Low
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Citation grounding
CITATION_ACCURACY = Histogram(
    "citation_grounding_accuracy",
    "Citation verification accuracy per response",
    ["dept_id"],
    buckets=[0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0]
)

# Knowledge gaps
KNOWLEDGE_GAPS = Counter(
    "knowledge_gaps_total",
    "Knowledge gaps detected",
    ["dept_id", "source"]  # retrieve, self_report
)

# Service health
SERVICE_UP = Gauge(
    "service_up",
    "Service health status",
    ["service_name"]
)

LLM_LATENCY = Histogram(
    "llm_call_duration_seconds",
    "LLM inference time",
    ["model", "call_type"],  # reasoning, validation, reflection
    buckets=[1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0]
)

ACTIVE_CONNECTIONS = Gauge(
    "db_active_connections",
    "Active database connections",
    ["pool_name"]
)
