# TODO — Testing & QA

Unit tests, integration tests, linting, coverage, and UAT checklist.

---

## P1 — High

### [ ] Run full unit test suite
- Command: `python -m pytest tests/unit/ -v`
- Expected: 86 test files, 500+ tests
- Fix any failures before proceeding to integration tests
- **Config:** `pyproject.toml` -> `[tool.pytest.ini_options]`

### [ ] Run ruff linter across all services
- Command: `ruff check .`
- Auto-fix available: `ruff check --fix .`
- **Config:** `pyproject.toml` -> `[tool.ruff]`

### [ ] Run mypy strict type checking
- Command: `mypy services/ --strict`
- Focus on business logic files; third-party stubs may need `# type: ignore`

### [ ] Verify test fixtures are complete
- **Directory:** `tests/fixtures/`
- Required: sample PDF, XLSX, DOCX, staging proposal JSON manifest, mock Slack event payloads
- Check each integration test file's imports to see what fixtures it expects

---

## P2 — Medium

### [ ] Run integration tests with Docker services
- Command: `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d && python -m pytest tests/integration/ -v`
- Requires: Postgres, Qdrant, MinIO running; MailHog for email tests
- Tests: infrastructure, rag_pipeline, staging_flow, sync_loop, e2e_golden_path, e2e_rejection, e2e_escalation
- **Note:** Some tests may need real vLLM or mocked LLM responses

### [ ] Measure test coverage
- Command: `python -m pytest tests/unit/ --cov=services --cov-report=html`
- Target: 80%+ on business logic (per PRD Section 14)
- Focus coverage gaps on: graph nodes, agent logic, staging writer, email sender

### [ ] Execute Stage 10 UAT checklist
- Full checklist in `docs/Implementation.md` under Stage 10
- 23 items covering real-world workflow validation
- **Prerequisites:** All P0 and P1 items from other todo files completed

---

## P3 — Low

### [ ] Set up CI pipeline
- Not currently configured
- Recommended: ruff check -> mypy -> pytest unit -> docker compose build
- Can defer until after UAT

### [ ] Load testing for vLLM endpoints
- Verify vLLM handles concurrent requests from multiple services
- cac-orchestrator: 3 LLM calls per query; wiki-compiler: 1 per event; rag-ingestion: N per document
- All hit same vLLM instance — test with realistic concurrent load
- **Tool:** `locust` or `hey` against `http://localhost:8000/v1/chat/completions`

---
*Last updated: 2026-04-10*
