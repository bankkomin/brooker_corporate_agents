"""LLM client using the Google GenAI SDK."""
from __future__ import annotations

import time

import structlog
from google import genai
from google.genai import types
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger("hr-orchestrator.llm")


class LLMClient:
    """Async client for Google Gemini via the google-genai SDK."""

    def __init__(
        self, base_url: str = "", model: str = "gemini-3.1-flash-lite-preview",
        api_key: str = "", timeout: float = 180.0,
    ) -> None:
        self._model = model
        self._client = genai.Client(api_key=api_key) if api_key else genai.Client()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
    )
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        **kwargs: object,
    ) -> str:
        """Send chat completion request and return the response text."""
        start = time.monotonic()

        # Convert OpenAI-style messages to Gemini contents format
        system_instruction = None
        contents: list[types.Content] = []

        for msg in messages:
            role = msg["role"]
            text = msg["content"]
            if role == "system":
                system_instruction = text
            else:
                # Gemini uses "user" and "model" (not "assistant")
                gemini_role = "model" if role == "assistant" else "user"
                contents.append(
                    types.Content(
                        role=gemini_role,
                        parts=[types.Part(text=text)],
                    )
                )

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
        )

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )

        elapsed_ms = (time.monotonic() - start) * 1000
        content = response.text or ""
        usage = response.usage_metadata
        total_tokens = (
            (usage.prompt_token_count or 0) + (usage.candidates_token_count or 0)
            if usage else None
        )

        logger.info(
            "llm_chat_complete",
            model=self._model,
            elapsed_ms=round(elapsed_ms, 1),
            tokens=total_tokens,
        )
        return content

    async def close(self) -> None:
        """No persistent connection to close with genai SDK."""
        pass
