import json
import logging
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, HTTPException

from .config import settings
from .golden_loader import load_golden_answers
from .models import GoldenAnswer
from .runner import run_eval
from .scheduler import start_scheduler

logger = logging.getLogger(__name__)

db_pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    db_pool = await asyncpg.create_pool(dsn=settings.POSTGRES_DSN, min_size=2, max_size=10)
    scheduler = start_scheduler(db_pool)
    logger.info("Eval framework started on port %s", settings.PORT)
    yield
    scheduler.shutdown(wait=False)
    await db_pool.close()


app = FastAPI(
    title="Eval Framework",
    description="Automated evaluation for corporate AI agents",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "eval-framework"}


@app.post("/eval/run/{dept_id}")
async def run_evaluation(dept_id: str):
    """Run evaluation for a department using its golden answer dataset."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    golden = load_golden_answers(dept_id)
    if not golden:
        raise HTTPException(
            status_code=404,
            detail=f"No golden answers found for department: {dept_id}",
        )

    result = await run_eval(dept_id, golden, db_pool)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@app.get("/eval/results/{dept_id}")
async def get_results(dept_id: str, run_id: int | None = None):
    """Get evaluation results for a department, optionally for a specific run."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    if run_id:
        rows = await db_pool.fetch(
            """
            SELECT * FROM eval_results
            WHERE dept_id = $1 AND run_id = $2
            ORDER BY evaluated_at
            """,
            dept_id,
            run_id,
        )
    else:
        # Get results from the latest run
        latest = await db_pool.fetchrow(
            """
            SELECT id FROM eval_runs
            WHERE dept_id = $1
            ORDER BY run_at DESC
            LIMIT 1
            """,
            dept_id,
        )
        if not latest:
            raise HTTPException(
                status_code=404, detail=f"No eval runs found for {dept_id}"
            )
        rows = await db_pool.fetch(
            """
            SELECT * FROM eval_results
            WHERE dept_id = $1 AND run_id = $2
            ORDER BY evaluated_at
            """,
            dept_id,
            latest["id"],
        )

    return {"dept_id": dept_id, "results": [dict(r) for r in rows]}


@app.get("/eval/trends/{dept_id}")
async def get_trends(dept_id: str, limit: int = 30):
    """Get accuracy trend over time for a department."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    rows = await db_pool.fetch(
        """
        SELECT id, dept_id, total, passed, failed, accuracy,
               avg_latency_ms, citation_accuracy, run_at
        FROM eval_runs
        WHERE dept_id = $1
        ORDER BY run_at DESC
        LIMIT $2
        """,
        dept_id,
        limit,
    )

    return {
        "dept_id": dept_id,
        "runs": [dict(r) for r in rows],
        "count": len(rows),
    }


@app.post("/eval/golden/{dept_id}")
async def add_golden_answer(dept_id: str, ga: GoldenAnswer):
    """Add a golden answer to the database."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    ga.dept_id = dept_id

    await db_pool.execute(
        """
        INSERT INTO eval_golden_answers
            (id, dept_id, category, question, expected_answer,
             expected_citations, acceptable_keywords, unacceptable_keywords,
             created_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (id) DO UPDATE SET
            question = EXCLUDED.question,
            expected_answer = EXCLUDED.expected_answer,
            expected_citations = EXCLUDED.expected_citations,
            acceptable_keywords = EXCLUDED.acceptable_keywords,
            unacceptable_keywords = EXCLUDED.unacceptable_keywords
        """,
        ga.id,
        dept_id,
        ga.category,
        ga.question,
        ga.expected_answer,
        json.dumps(ga.expected_citations),
        json.dumps(ga.acceptable_keywords),
        json.dumps(ga.unacceptable_keywords),
        ga.created_by,
    )

    return {"status": "ok", "id": ga.id, "dept_id": dept_id}
