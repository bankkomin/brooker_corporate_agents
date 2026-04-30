from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GoldenAnswer(BaseModel):
    id: str  # ga_cac_001
    dept_id: str
    category: Literal["lookup", "analytical", "edge_case"]
    question: str
    expected_answer: str
    expected_citations: list[str] = []  # expected source documents
    acceptable_keywords: list[str] = []  # must appear in answer
    unacceptable_keywords: list[str] = []  # must NOT appear
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EvalResult(BaseModel):
    id: int
    dept_id: str
    golden_id: str
    question: str
    expected_answer: str
    actual_answer: str
    answer_score: float  # 0-1 semantic similarity
    citation_correct: bool
    keywords_present: bool
    keywords_absent: bool  # true = no bad keywords found
    latency_ms: int
    passed: bool
    run_id: int
    evaluated_at: datetime


class EvalRun(BaseModel):
    id: int
    dept_id: str
    total: int
    passed: int
    failed: int
    accuracy: float  # passed/total
    avg_latency_ms: float
    citation_accuracy: float
    run_at: datetime
