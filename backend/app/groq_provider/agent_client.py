"""
Groq Agent Client

Async Groq SDK client providing the same generate_content() interface as
the former GrokAgentClient/GeminiAgentClient, so the agent loop, tools,
planner, summary generator, document classifier, and learning system can
call Groq with no logic changes beyond the import/type swap.
"""

import base64
import io
import logging
from typing import Any, Dict, List, Optional

import groq
from groq import AsyncGroq
from tenacity import retry, retry_if_exception, stop_after_attempt

from .config import GroqConfig
from .rate_limiter import GroqRateLimiter, is_retryable_groq_error
from .usage import get_groq_usage_stats

logger = logging.getLogger(__name__)


class GroqUnavailableError(Exception):
    """Raised when Groq is unavailable after all retries are exhausted."""


def _encode_image(image: Any) -> Dict[str, Any]:
    """Serialize a PIL image to a Groq/OpenAI-style image_url content block."""
    fmt = (image.format or "PNG").upper()
    save_format = "JPEG" if fmt == "JPG" else fmt
    media_type = f"image/{save_format.lower()}"
    buffer = io.BytesIO()
    image.save(buffer, format=save_format)
    b64_data = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{media_type};base64,{b64_data}"},
    }


_text_retry = retry(
    stop=stop_after_attempt(GroqConfig.MAX_RETRIES),
    wait=GroqRateLimiter(),
    retry=retry_if_exception(is_retryable_groq_error),
    reraise=True,
)


class GroqAgentClient:
    """
    Singleton async wrapper around the Groq SDK.

    generate_content() mirrors the former GrokAgentClient/GeminiAgentClient
    signature (prompt, images, model_type, config) -> str, so every call
    site that used `await self.client.generate_content(prompt=..., model_type="text")`
    keeps working unchanged.
    """

    _instance: Optional["GroqAgentClient"] = None

    def __init__(self) -> None:
        if not GroqConfig.API_KEY:
            raise ValueError("GROQ_API_KEY environment variable not set")
        self._client = AsyncGroq(api_key=GroqConfig.API_KEY)
        logger.info("GroqAgentClient initialized successfully")

    @classmethod
    def get_instance(cls) -> "GroqAgentClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def generate_content(
        self,
        prompt: str,
        images: Optional[List[Any]] = None,
        model_type: str = "text",
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate content using Groq.

        Retries up to GroqConfig.MAX_RETRIES times — waiting the
        server-suggested Retry-After on 429s, exponential backoff otherwise —
        on rate limits / transient errors. On final failure raises
        GroqUnavailableError — callers catch this (and Exception generally)
        and continue the agent loop without crashing.
        """
        model = (
            GroqConfig.VISION_MODEL
            if (images or model_type == "vision")
            else GroqConfig.TEXT_MODEL
        )
        max_tokens = (config or {}).get("max_output_tokens", GroqConfig.MAX_OUTPUT_TOKENS)

        content: List[Dict[str, Any]] = []
        if images:
            for image in images:
                content.append(_encode_image(image))
        content.append({"type": "text", "text": prompt})

        messages = [{"role": "user", "content": content}]

        usage = get_groq_usage_stats()
        request_kind = "vision" if (images or model_type == "vision") else "text"

        try:
            response = await self._generate_with_retry(model=model, messages=messages, max_tokens=max_tokens)
        except groq.APIError as exc:
            logger.error(f"Groq unavailable after {GroqConfig.MAX_RETRIES} attempts: {exc}")
            usage.record_error(str(exc))
            raise GroqUnavailableError(f"Groq API unavailable: {exc}") from exc

        usage.record_request(request_kind)
        result = response.choices[0].message.content or ""
        logger.info(f"Generated {len(result)} chars (model={model})")
        return result

    @_text_retry
    async def _generate_with_retry(self, model: str, messages: List[Dict[str, Any]], max_tokens: int):
        return await self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )

    async def health_check(self) -> bool:
        """Verify the Groq API is accessible."""
        try:
            text = await self.generate_content(prompt="Respond with: OK", config={"max_output_tokens": 10})
            return "OK" in text or len(text) > 0
        except Exception as exc:
            logger.error(f"Health check failed: {exc}")
            return False


def get_groq_agent_client() -> GroqAgentClient:
    """Get the singleton GroqAgentClient instance."""
    return GroqAgentClient.get_instance()
