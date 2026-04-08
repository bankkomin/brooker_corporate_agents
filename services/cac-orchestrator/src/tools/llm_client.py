"""LLM client for vLLM chat completions."""
from __future__ import annotations

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger("cac-orchestrator.llm")


class LLMClient:
    """Async client for vLLM /v1/chat/completions endpoint."""

    def __init__(self, base_url: str, model: str, timeout: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.AsyncClient(timeout=timeout)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
    )
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Send chat completion request and return the response text."""
        import time

        start = time.monotonic()
        response = await self._client.post(
            f"{self._base_url}/chat/completions",
            json={
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        elapsed_ms = (time.monotonic() - start) * 1000
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        logger.info(
            "llm_chat_complete",
            model=self._model,
            elapsed_ms=round(elapsed_ms, 1),
            tokens=data.get("usage", {}).get("total_tokens"),
        )
        return content

    async def close(self) -> None:
        await self._client.aclose()
