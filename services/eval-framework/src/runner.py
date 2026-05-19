import time
from difflib import SequenceMatcher

import httpx

ORCHESTRATOR_PORTS = {"cac": 3001, "hr": 3002, "finance": 3010}


async def _create_run(db_pool, dept_id: str) -> int:
    """Insert a new eval run row and return its id."""
    row = await db_pool.fetchrow(
        """
        INSERT INTO eval_runs (dept_id, total, passed, failed, accuracy, avg_latency_ms, citation_accuracy)
        VALUES ($1, 0, 0, 0, 0, 0, 0)
        RETURNING id
        """,
        dept_id,
    )
    return row["id"]


async def _save_result(db_pool, result: dict) -> None:
    """Persist a single evaluation result."""
    await db_pool.execute(
        """
        INSERT INTO eval_results
            (dept_id, golden_id, question, actual_answer, answer_score,
             citation_correct, keywords_present, keywords_absent,
             latency_ms, passed, run_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """,
        result.get("dept_id", ""),
        result["golden_id"],
        result["question"],
        result.get("actual_answer", ""),
        result.get("answer_score", 0.0),
        result.get("citation_correct", False),
        result.get("keywords_present", False),
        result.get("keywords_absent", True),
        result.get("latency_ms", 0),
        result.get("passed", False),
        result["run_id"],
    )


async def _complete_run(
    db_pool,
    run_id: int,
    total: int,
    passed: int,
    accuracy: float,
    avg_latency: float,
    citation_accuracy: float,
) -> None:
    """Update the eval run with final summary stats."""
    await db_pool.execute(
        """
        UPDATE eval_runs
        SET total = $2,
            passed = $3,
            failed = $4,
            accuracy = $5,
            avg_latency_ms = $6,
            citation_accuracy = $7
        WHERE id = $1
        """,
        run_id,
        total,
        passed,
        total - passed,
        accuracy,
        avg_latency,
        citation_accuracy,
    )


async def run_eval(dept_id: str, golden_answers: list[dict], db_pool) -> dict:
    """Run all golden answers against the orchestrator and score results."""
    port = ORCHESTRATOR_PORTS.get(dept_id)
    if not port:
        return {"error": f"Unknown dept: {dept_id}"}

    # Create eval run
    run_id = await _create_run(db_pool, dept_id)
    results = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        for ga in golden_answers:
            start = time.monotonic()
            try:
                resp = await client.post(
                    f"http://localhost:{port}/query",
                    json={"query": ga["question"]},
                )
                resp.raise_for_status()
                data = resp.json()
                latency = int((time.monotonic() - start) * 1000)

                actual = data.get("response", "")
                citations = data.get("citations", [])

                # Score answer
                answer_score = SequenceMatcher(
                    None, ga["expected_answer"], actual
                ).ratio()

                # Check keywords
                keywords_present = (
                    all(
                        kw.lower() in actual.lower()
                        for kw in ga.get("acceptable_keywords", [])
                    )
                    if ga.get("acceptable_keywords")
                    else True
                )

                keywords_absent = (
                    not any(
                        kw.lower() in actual.lower()
                        for kw in ga.get("unacceptable_keywords", [])
                    )
                    if ga.get("unacceptable_keywords")
                    else True
                )

                # Check citations
                citation_correct = (
                    any(
                        any(exp in cit for cit in citations)
                        for exp in ga.get("expected_citations", [])
                    )
                    if ga.get("expected_citations")
                    else True
                )

                passed = (
                    answer_score >= 0.5 and keywords_present and keywords_absent
                )

                result = {
                    "dept_id": dept_id,
                    "golden_id": ga["id"],
                    "question": ga["question"],
                    "expected_answer": ga["expected_answer"],
                    "actual_answer": actual,
                    "answer_score": round(answer_score, 3),
                    "citation_correct": citation_correct,
                    "keywords_present": keywords_present,
                    "keywords_absent": keywords_absent,
                    "latency_ms": latency,
                    "passed": passed,
                    "run_id": run_id,
                }
                results.append(result)
                await _save_result(db_pool, result)

            except Exception as e:
                results.append(
                    {
                        "dept_id": dept_id,
                        "golden_id": ga["id"],
                        "question": ga["question"],
                        "error": str(e),
                        "passed": False,
                        "run_id": run_id,
                    }
                )

    # Compute summary
    total = len(results)
    passed_count = sum(1 for r in results if r.get("passed"))
    accuracy = passed_count / total if total > 0 else 0
    avg_latency = (
        sum(r.get("latency_ms", 0) for r in results) / total if total > 0 else 0
    )
    citation_acc = (
        sum(1 for r in results if r.get("citation_correct")) / total
        if total > 0
        else 0
    )

    await _complete_run(
        db_pool, run_id, total, passed_count, accuracy, avg_latency, citation_acc
    )

    return {
        "run_id": run_id,
        "dept_id": dept_id,
        "total": total,
        "passed": passed_count,
        "accuracy": round(accuracy, 3),
        "avg_latency_ms": round(avg_latency),
        "citation_accuracy": round(citation_acc, 3),
        "results": results,
    }
