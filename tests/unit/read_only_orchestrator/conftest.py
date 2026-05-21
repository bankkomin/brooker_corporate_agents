"""Stub heavy service dependencies so the read-only-orchestrator pure-function
unit tests (_pick_specialist, _is_capability_query, etc.) can import pipeline.py
without qdrant_client / langchain_openai installed in the test environment."""
import sys
from unittest.mock import MagicMock

for _mod in ("qdrant_client", "langchain_openai"):
    sys.modules.setdefault(_mod, MagicMock())
