"""Unit tests for services/read-only-orchestrator/src/pipeline.py."""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Stub out heavy deps that are not installed in the unit-test venv.
# Must happen BEFORE the pipeline module is imported.
# ---------------------------------------------------------------------------

def _stub_deps() -> None:
    """Inject lightweight stubs for langchain_openai and pydantic_settings."""
    if "langchain_openai" not in sys.modules:
        lo = types.ModuleType("langchain_openai")
        lo.ChatOpenAI = MagicMock  # type: ignore[attr-defined]
        sys.modules["langchain_openai"] = lo

    if "pydantic_settings" not in sys.modules:
        ps = types.ModuleType("pydantic_settings")

        class _BaseSettings:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
            class model_config:  # noqa: N801
                pass

        ps.BaseSettings = _BaseSettings  # type: ignore[attr-defined]
        sys.modules["pydantic_settings"] = ps


_stub_deps()


# ---------------------------------------------------------------------------
# Import helper — read-only-orchestrator is hyphenated and not in conftest.py.
# ---------------------------------------------------------------------------

def _ensure_ro_importable() -> None:
    """Register services.read_only_orchestrator.src as an importable package."""
    repo = Path(__file__).resolve().parents[3]
    svc = repo / "services" / "read-only-orchestrator"
    src = svc / "src"

    ro_mod = "services.read_only_orchestrator"
    ro_src_mod = "services.read_only_orchestrator.src"

    if ro_mod not in sys.modules:
        m = types.ModuleType(ro_mod)
        m.__path__ = [str(svc)]  # type: ignore[attr-defined]
        m.__package__ = ro_mod
        sys.modules[ro_mod] = m

    if ro_src_mod not in sys.modules:
        m2 = types.ModuleType(ro_src_mod)
        m2.__path__ = [str(src)]  # type: ignore[attr-defined]
        m2.__package__ = ro_src_mod
        sys.modules[ro_src_mod] = m2

    # Also register the config sub-module (pipeline imports .config)
    cfg_mod = "services.read_only_orchestrator.src.config"
    if cfg_mod not in sys.modules:
        spec = importlib.util.spec_from_file_location(cfg_mod, src / "config.py")
        if spec and spec.loader:
            cfg = importlib.util.module_from_spec(spec)
            sys.modules[cfg_mod] = cfg
            spec.loader.exec_module(cfg)


_ensure_ro_importable()


def _import_pipeline():
    """Import the pipeline module (cached after first call)."""
    mod_name = "services.read_only_orchestrator.src.pipeline"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    repo = Path(__file__).resolve().parents[3]
    pipeline_path = repo / "services" / "read-only-orchestrator" / "src" / "pipeline.py"
    spec = importlib.util.spec_from_file_location(mod_name, pipeline_path)
    assert spec and spec.loader, f"Cannot locate pipeline at {pipeline_path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# _is_capability_query
# ---------------------------------------------------------------------------

class TestIsCapabilityQuery:
    def _fn(self, q: str) -> bool:
        return _import_pipeline()._is_capability_query(q)

    def test_what_is_your_task_returns_true(self) -> None:
        assert self._fn("what is your task?") is True

    def test_what_are_your_capabilities_returns_true(self) -> None:
        assert self._fn("what are your capabilities") is True

    def test_who_are_you_returns_true(self) -> None:
        assert self._fn("who are you?") is True

    def test_what_can_you_do_returns_true(self) -> None:
        assert self._fn("what can you do") is True

    def test_introduce_yourself_returns_true(self) -> None:
        assert self._fn("introduce yourself") is True

    def test_hello_greeting_returns_true(self) -> None:
        assert self._fn("hello") is True

    def test_hey_returns_true(self) -> None:
        assert self._fn("hey!") is True

    def test_good_morning_greeting_returns_true(self) -> None:
        assert self._fn("good morning") is True

    def test_substantive_lcr_question_returns_false(self) -> None:
        assert self._fn("What is the current LCR ratio in the ALCO tracker?") is False

    def test_rwa_question_returns_false(self) -> None:
        assert self._fn("What was the RWA for Q3 2025?") is False

    def test_empty_string_returns_false(self) -> None:
        assert self._fn("") is False


# ---------------------------------------------------------------------------
# _pick_specialist
# ---------------------------------------------------------------------------

class TestPickSpecialist:
    @pytest.mark.asyncio
    async def test_returns_matched_specialist_name(self) -> None:
        pipeline = _import_pipeline()

        fake_resp = MagicMock()
        fake_resp.content = "credit-risk"
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=fake_resp)

        dept_config = {
            "name": "Risk",
            "agentTopology": {"specialists": ["credit-risk-agent", "market-risk-agent"]},
        }
        result = await pipeline._pick_specialist(
            "Tell me about credit exposure", dept_config, fake_llm
        )
        assert result == "credit-risk"

    @pytest.mark.asyncio
    async def test_returns_general_on_garbage_llm_output(self) -> None:
        pipeline = _import_pipeline()

        fake_resp = MagicMock()
        fake_resp.content = "xyzzy_not_a_real_specialist"
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=fake_resp)

        dept_config = {
            "name": "Risk",
            "agentTopology": {"specialists": ["credit-risk-agent"]},
        }
        result = await pipeline._pick_specialist("random question", dept_config, fake_llm)
        assert result == "general"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_specialists(self) -> None:
        pipeline = _import_pipeline()

        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock()

        dept_config = {"name": "HR", "agentTopology": {}}
        result = await pipeline._pick_specialist("any question", dept_config, fake_llm)
        assert result is None
        fake_llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_agent_topology(self) -> None:
        pipeline = _import_pipeline()

        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock()

        dept_config = {"name": "Legal"}
        result = await pipeline._pick_specialist("any question", dept_config, fake_llm)
        assert result is None
        fake_llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_general_on_llm_exception(self) -> None:
        pipeline = _import_pipeline()

        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(side_effect=RuntimeError("network error"))

        dept_config = {
            "name": "Risk",
            "agentTopology": {"specialists": ["credit-risk-agent"]},
        }
        result = await pipeline._pick_specialist("something", dept_config, fake_llm)
        assert result == "general"

    @pytest.mark.asyncio
    async def test_strip_agent_suffix_before_matching(self) -> None:
        """LLM returns 'market-risk' (no '-agent' suffix) — still matches."""
        pipeline = _import_pipeline()

        fake_resp = MagicMock()
        fake_resp.content = "market-risk"
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=fake_resp)

        dept_config = {
            "name": "Risk",
            "agentTopology": {"specialists": ["market-risk-agent"]},
        }
        result = await pipeline._pick_specialist("market volatility", dept_config, fake_llm)
        assert result == "market-risk"
