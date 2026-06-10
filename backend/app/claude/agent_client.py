"""
Claude Agent Client

Async Anthropic-backed client providing the same generate_content() interface
as the former GeminiClient, so the agent loop, tools, planner, summary
generator, document classifier, and learning system can call Claude with no
logic changes beyond the import/type swap.
"""

import base64
import io
import logging
from typing import Any, Dict, List, Optional

import anthropic
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import ClaudeConfig
from .usage import get_claude_usage_stats

logger = logging.getLogger(__name__)


class ClaudeUnavailableError(Exception):
    """Raised when Claude is unavailable after all retries are exhausted."""


def _encode_image(image: Any) -> tuple[str, str]:
    """Serialize a PIL image to base64 plus its Anthropic media type."""
    fmt = (image.format or "PNG").upper()
    save_format = "JPEG" if fmt == "JPG" else fmt
    media_type = f"image/{save_format.lower()}"
    buffer = io.BytesIO()
    image.save(buffer, format=save_format)
    return media_type, base64.standard_b64encode(buffer.getvalue()).decode("utf-8")


_text_retry = retry(
    stop=stop_after_attempt(ClaudeConfig.MAX_RETRIES),
    wait=wait_exponential(
        multiplier=ClaudeConfig.RETRY_BASE_DELAY,
        min=ClaudeConfig.RETRY_BASE_DELAY,
        max=30,
    ),
    retry=retry_if_exception_type(
        (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError)
    ),
    reraise=True,
)


class ClaudeAgentClient:
    """
    Singleton async wrapper around the Anthropic SDK.

    generate_content() mirrors the former GeminiClient signature
    (prompt, images, model_type, config) -> str, so every call site that used
    `await self.client.generate_content(prompt=..., model_type="text")` keeps
    working unchanged.
    """

    _instance: Optional["ClaudeAgentClient"] = None

    def __init__(self) -> None:
        if not ClaudeConfig.API_KEY:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self._client = anthropic.AsyncAnthropic(api_key=ClaudeConfig.API_KEY)
        logger.info("ClaudeAgentClient initialized successfully")

    @classmethod
    def get_instance(cls) -> "ClaudeAgentClient":
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
        Generate content using Claude.

        Retries up to ClaudeConfig.MAX_RETRIES times with exponential backoff
        on rate limits / transient errors. On final failure raises
        ClaudeUnavailableError — callers catch this (and Exception generally)
        and continue the agent loop without crashing.
        """
        model = (
            ClaudeConfig.VISION_MODEL
            if (images or model_type == "vision")
            else ClaudeConfig.TEXT_MODEL
        )
        max_tokens = (config or {}).get("max_output_tokens", ClaudeConfig.MAX_OUTPUT_TOKENS)

        content: List[Dict[str, Any]] = []
        if images:
            for image in images:
                media_type, image_b64 = _encode_image(image)
                content.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": image_b64},
                    }
                )
        content.append({"type": "text", "text": prompt})

        usage = get_claude_usage_stats()
        request_kind = "vision" if (images or model_type == "vision") else "text"

        try:
            response = await self._create_with_retry(model=model, max_tokens=max_tokens, content=content)
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
            logger.error(f"Claude unavailable after {ClaudeConfig.MAX_RETRIES} attempts: {exc}")
            usage.record_error(str(exc))
            raise ClaudeUnavailableError(f"Claude API unavailable: {exc}") from exc
        except anthropic.AuthenticationError as exc:
            logger.error(f"Claude authentication failed: {exc}")
            usage.record_error(str(exc))
            raise ClaudeUnavailableError(f"Claude authentication failed: {exc}") from exc

        usage.record_request(request_kind)
        text_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        result = "".join(text_parts)
        logger.info(f"Generated {len(result)} chars (model={model})")
        return result

    @_text_retry
    async def _create_with_retry(self, model: str, max_tokens: int, content: List[Dict[str, Any]]):
        return await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": content}],
        )

    async def health_check(self) -> bool:
        """Verify the Claude API is accessible."""
        try:
            text = await self.generate_content(prompt="Respond with: OK", config={"max_output_tokens": 10})
            return "OK" in text or len(text) > 0
        except Exception as exc:
            logger.error(f"Health check failed: {exc}")
            return False


def get_claude_agent_client() -> ClaudeAgentClient:
    """Get the singleton ClaudeAgentClient instance."""
    return ClaudeAgentClient.get_instance()
