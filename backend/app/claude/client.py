"""
Anthropic Claude Client Wrapper

Provides a singleton synchronous Anthropic client. A sync client is used
deliberately — the OCRProvider interface (app/ocr/providers/base.py) is
synchronous, and document_service runs OCR inside a worker thread via
asyncio.to_thread, so there is no event loop to bridge into (unlike the
Gemini provider, which has to juggle run_until_complete + nest_asyncio).
"""

import logging
from typing import Optional

import anthropic

from .config import ClaudeConfig

logger = logging.getLogger(__name__)


class ClaudeClient:
    """Singleton wrapper around the Anthropic SDK client."""

    _instance: Optional["ClaudeClient"] = None
    _client: Optional[anthropic.Anthropic] = None

    def __init__(self):
        if not ClaudeConfig.API_KEY:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self._client = anthropic.Anthropic(api_key=ClaudeConfig.API_KEY)
        logger.info("ClaudeClient initialized successfully")

    @classmethod
    def get_instance(cls) -> "ClaudeClient":
        """Get singleton instance of ClaudeClient"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def raw(self) -> anthropic.Anthropic:
        """The underlying anthropic.Anthropic SDK client."""
        return self._client


def get_claude_client() -> anthropic.Anthropic:
    """Get the underlying Anthropic SDK client instance."""
    return ClaudeClient.get_instance().raw
