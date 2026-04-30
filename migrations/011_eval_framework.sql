CREATE TABLE IF NOT EXISTS eval_golden_answers (
    id TEXT PRIMARY KEY,
    dept_id TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('lookup', 'analytical', 'edge_case')),
    question TEXT NOT NULL,
    expected_answer TEXT NOT NULL,
    expected_citations JSONB DEFAULT '[]',
    acceptable_keywords JSONB DEFAULT '[]',
    unacceptable_keywords JSONB DEFAULT '[]',
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS eval_results (
    id BIGSERIAL PRIMARY KEY,
    dept_id TEXT NOT NULL,
    golden_id TEXT REFERENCES eval_golden_answers(id),
    question TEXT NOT NULL,
    actual_answer TEXT,
    answer_score FLOAT,
    citation_correct BOOLEAN,
    keywords_present BOOLEAN,
    keywords_absent BOOLEAN,
    latency_ms INT,
    passed BOOLEAN,
    run_id INT NOT NULL,
    evaluated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id BIGSERIAL PRIMARY KEY,
    dept_id TEXT NOT NULL,
    total INT NOT NULL,
    passed INT NOT NULL,
    failed INT NOT NULL,
    accuracy FLOAT,
    avg_latency_ms FLOAT,
    citation_accuracy FLOAT,
    run_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_eval_runs_dept ON eval_runs(dept_id, run_at DESC);
