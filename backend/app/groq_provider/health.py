"""
Groq Health Service

Performs a lightweight connectivity/authentication check against the
configured GROQ_API_KEY and model. Used by:
  - app startup (fail-fast logging — see app/main.py)
  - GET /api/v1/system/llm-status
  - AgentService.start_run, which gates extractor execution on this check
    so a bad/expired key produces ONE clear "Groq initialization failed"
    error instead of six identical per-extractor 403s.
"""

import time
from typing import Optional, TypedDict

from groq import AsyncGroq

from app.utils.logging import get_logger

from .config import GroqConfig

logger = get_logger(__name__)

# Re-checked at most this often — config (and therefore the API key) only
# changes on process restart, so a short cache avoids an extra Groq call
# on every status-panel poll / agent run.
_CACHE_TTL_SECONDS = 30.0


class GroqHealthResult(TypedDict, total=False):
    provider: str
    status: str
    authenticated: bool
    model: str
    error: str


class GroqHealthService:
    """Checks whether the configured Groq API key/model can authenticate."""

    _cached_result: Optional[GroqHealthResult] = None
    _cached_at: float = 0.0

    @classmethod
    async def check_connection(cls, use_cache: bool = True) -> GroqHealthResult:
        if (
            use_cache
            and cls._cached_result is not None
            and (time.monotonic() - cls._cached_at) < _CACHE_TTL_SECONDS
        ):
            return cls._cached_result

        result = await cls._check_connection_uncached()
        cls._cached_result = result
        cls._cached_at = time.monotonic()
        return result

    @classmethod
    async def _check_connection_uncached(cls) -> GroqHealthResult:
        logger.info("Initializing Groq...")
        logger.info("Loading GROQ_API_KEY...")

        if not GroqConfig.API_KEY:
            logger.error("Groq authentication failed: GROQ_API_KEY environment variable not set")
            return {
                "provider": "groq",
                "status": "failed",
                "authenticated": False,
                "model": GroqConfig.TEXT_MODEL,
                "error": "GROQ_API_KEY environment variable not set",
            }

        masked_key = f"{GroqConfig.API_KEY[:6]}***" if len(GroqConfig.API_KEY) > 6 else "***"
        logger.info(f"Loaded Groq key: {masked_key}")
        logger.info(f"Using model: {GroqConfig.TEXT_MODEL}")

        try:
            client = AsyncGroq(api_key=GroqConfig.API_KEY)
            await client.chat.completions.create(
                model=GroqConfig.TEXT_MODEL,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
        except Exception as exc:
            logger.error(f"Groq authentication failed: {exc}")
            return {
                "provider": "groq",
                "status": "failed",
                "authenticated": False,
                "model": GroqConfig.TEXT_MODEL,
                "error": str(exc),
            }

        logger.info("Groq initialized successfully.")
        return {
            "provider": "groq",
            "status": "healthy",
            "authenticated": True,
            "model": GroqConfig.TEXT_MODEL,
        }

    @classmethod
    def reset_cache(cls) -> None:
        cls._cached_result = None
        cls._cached_at = 0.0
