"""
Groq Client Wrapper

Provides a singleton synchronous Groq SDK client. A sync client is used
deliberately — the OCRProvider interface (app/ocr/providers/base.py) is
synchronous, and document_service runs OCR inside a worker thread via
asyncio.to_thread, so there is no event loop to bridge into.
"""

import logging
from typing import Optional

from groq import Groq

from .config import GroqConfig

logger = logging.getLogger(__name__)


class GroqClient:
    """Singleton wrapper around the Groq SDK client."""

    _instance: Optional["GroqClient"] = None
    _client: Optional[Groq] = None

    def __init__(self):
        if not GroqConfig.API_KEY:
            raise ValueError("GROQ_API_KEY environment variable not set")

        self._client = Groq(api_key=GroqConfig.API_KEY)
        logger.info("GroqClient initialized successfully")

    @classmethod
    def get_instance(cls) -> "GroqClient":
        """Get singleton instance of GroqClient"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def raw(self) -> Groq:
        """The underlying Groq SDK client."""
        return self._client


def get_groq_client() -> Groq:
    """Get the underlying Groq SDK client instance."""
    return GroqClient.get_instance().raw
