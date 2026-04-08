---
description: Run tests for a specific service
---
Run pytest for the service specified in $ARGUMENTS.

If $ARGUMENTS is a service name (e.g., "slack-bot", "rag-ingestion"):
  Run: `pytest tests/unit/test_{service_module}*.py tests/integration/test_{service_module}*.py -v --tb=short`

If $ARGUMENTS is "all":
  Run: `pytest tests/ -v --tb=short`

If $ARGUMENTS is "unit":
  Run: `pytest tests/unit/ -v --tb=short`

If $ARGUMENTS is "integration":
  Run: `pytest tests/integration/ -v --tb=short`

Report: total tests, passed, failed, coverage summary.
