import abc
import asyncio
import json
import logging
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Exception raised when an LLM provider fails."""
    pass


class BaseLLMService(abc.ABC):
    """Abstract Base Class for LLM Provider Strategy."""

    @abc.abstractmethod
    async def generate_response(
        self, messages: list[dict[str, str]]
    ) -> tuple[str, str, str]:
        """Generate full response given a list of messages."""
        pass

    @abc.abstractmethod
    async def generate_response_stream(
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens chunk by chunk."""
        pass

    @abc.abstractmethod
    async def generate_title(self, prompt: str) -> str:
        """Generate a concise title for a conversation based on the first message."""
        pass


class OpenRouterLLMService(BaseLLMService):
    """LLM Service using OpenRouter (OpenAI-compatible HTTP API)."""

    def __init__(self, api_key: str, model: str, base_url: str):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def generate_response(
        self, messages: list[dict[str, str]]
    ) -> tuple[str, str, str]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/juancini/ai_chat_demo",
            "X-Title": "AI Chat Demo",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000,
        }

        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 401:
                    logger.error("OpenRouter API Key authentication failed (401).")
                    raise LLMServiceError("Invalid or unauthorized OpenRouter API Key.")

                if response.status_code != 200:
                    error_text = response.text
                    logger.error(
                        "OpenRouter API returned error %d: %s", response.status_code, error_text
                    )
                    raise LLMServiceError(
                        f"OpenRouter API error (HTTP {response.status_code}): {error_text}"
                    )

                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise LLMServiceError("OpenRouter returned no choices in response.")

                content = choices[0].get("message", {}).get("content", "").strip()
                model_used = data.get("model", self.model)
                return content, "openrouter", model_used

        except httpx.TimeoutException as e:
            logger.error("OpenRouter API request timed out: %s", e)
            raise LLMServiceError("OpenRouter API request timed out. Please try again.") from e
        except httpx.RequestError as e:
            logger.error("Network error communicating with OpenRouter: %s", e)
            raise LLMServiceError(f"Network error connecting to OpenRouter: {e}") from e

    async def generate_response_stream(
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/juancini/ai_chat_demo",
            "X-Title": "AI Chat Demo",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code == 401:
                        raise LLMServiceError("Invalid or unauthorized OpenRouter API Key.")

                    if response.status_code != 200:
                        body = await response.aread()
                        err_msg = body.decode()
                        raise LLMServiceError(
                            f"OpenRouter streaming error (HTTP {response.status_code}): {err_msg}"
                        )

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or line.startswith(":"):
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                content_chunk = delta.get("content", "")
                                if content_chunk:
                                    yield content_chunk
                            except json.JSONDecodeError:
                                continue
        except httpx.TimeoutException as e:
            raise LLMServiceError("OpenRouter streaming timed out.") from e
        except httpx.RequestError as e:
            raise LLMServiceError(f"Network error during OpenRouter stream: {e}") from e

    async def generate_title(self, prompt: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You generate short titles (3 to 6 words maximum, no quotes, no period) "
                    "for chat threads based on the user's first message."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        try:
            content, _, _ = await self.generate_response(messages)
            title = content.strip().strip('"').strip("'")
            return title if title else prompt[:30]
        except Exception as e:
            logger.warning("Failed to generate AI title, using fallback prompt slice: %s", e)
            return prompt[:30].strip() + ("..." if len(prompt) > 30 else "")


class MockLLMService(BaseLLMService):
    """Fallback Mock LLM Service with simulated token streaming."""

    def __init__(self):
        self.model = "mock-demo-v1"

    async def generate_response(
        self, messages: list[dict[str, str]]
    ) -> tuple[str, str, str]:
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break

        response_content = (
            f"[🤖 MOCK MODE ACTIVE]\n\n"
            f"I received your message: \"{last_user_msg}\"\n\n"
            f"ℹ️ *Note: `OPENROUTER_API_KEY` is not set in environment settings.\n"
            f"The application is running in Mock LLM mode so you can test all features "
            f"(creation, persistence, history) out-of-the-box without crashing!\n"
            f"Set a valid OPENROUTER_API_KEY in your .env file to enable live AI responses.*"
        )
        return response_content, "mock", self.model

    async def generate_response_stream(
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        full_content, _, _ = await self.generate_response(messages)
        words = full_content.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield chunk
            await asyncio.sleep(0.03)

    async def generate_title(self, prompt: str) -> str:
        clean_prompt = prompt.strip()
        if len(clean_prompt) > 35:
            return clean_prompt[:32] + "..."
        return clean_prompt if clean_prompt else "New Conversation"


def get_llm_service() -> BaseLLMService:
    """Factory function returning active LLM Strategy implementation."""
    api_key = settings.OPENROUTER_API_KEY
    if api_key and api_key.strip():
        logger.info(
            "Initializing OpenRouterLLMService with model '%s'", settings.OPENROUTER_MODEL
        )
        return OpenRouterLLMService(
            api_key=api_key.strip(),
            model=settings.OPENROUTER_MODEL,
            base_url=settings.OPENROUTER_BASE_URL,
        )

    logger.info("No OPENROUTER_API_KEY configured. Falling back to MockLLMService.")
    return MockLLMService()
