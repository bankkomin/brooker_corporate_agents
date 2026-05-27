"""LLM client for the OpenAI-compatible vLLM/Qwen endpoint.

Mirrors the request shape used in D:\\DGX_Test\\atlas_dispatcher.py:
POST {base_url}/chat/completions with {model, messages, max_tokens,
temperature, ...} and returns choices[0].message.content.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger("hr-orchestrator.llm")

# The DGX runs a single Qwen Spark that fails beyond a few concurrent sequences.
# Cap concurrent calls per process; extra calls await a free slot (no reject).
# Shared across every LLMClient instance in this process.
LLM_MAX_CONCURRENCY = int(os.getenv("LLM_MAX_CONCURRENCY", "4"))
_DGX_SEMAPHORE = asyncio.Semaphore(LLM_MAX_CONCURRENCY)

_PASSTHROUGH_KEYS = (
    "top_p",
    "top_k",
    "stop",
    "tools",
    "tool_choice",
    "chat_template_kwargs",
    "response_format",
    "seed",
    "preserve_thinking",
)


class LLMClient:
    """Async client for the Qwen vLLM server (OpenAI-compatible)."""

    def __init__(
        self,
        base_url: str = "http://nginx:8080/v1",
        model: str = "qwen-large",
        api_key: str = "",
        timeout: float = 180.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.AsyncClient(timeout=timeout, headers=headers)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError)
        ),
        reraise=True,
    )
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """Send chat completion request and return the assistant text."""
        start = time.monotonic()

        body: dict[str, Any] = {
            "model": kwargs.get("model", self._model),
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        for k in _PASSTHROUGH_KEYS:
            if k in kwargs:
                body[k] = kwargs[k]

        async with _DGX_SEMAPHORE:
            resp = await self._http.post(f"{self._base_url}/chat/completions", json=body)
            resp.raise_for_status()
            data = resp.json()

        message = data["choices"][0]["message"]
        content = message.get("content") or ""

        elapsed_ms = (time.monotonic() - start) * 1000
        usage = data.get("usage") or {}
        logger.info(
            "llm_chat_complete",
            model=body["model"],
            elapsed_ms=round(elapsed_ms, 1),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
        return content

    async def close(self) -> None:
        await self._http.aclose()
