"""
Groq Rate Limiter

Handles HTTP 429 (rate limit) and 5xx responses from the Groq API: parses a
server-suggested `Retry-After` header when present, otherwise falls back to
exponential backoff. Used as a tenacity `wait` callable by GroqAgentClient
and GroqVisionOCR.
"""

import logging
from typing import Optional

import groq
from tenacity import RetryCallState

from .config import GroqConfig
from .usage import get_groq_usage_stats

logger = logging.getLogger(__name__)


def _parse_retry_after_seconds(exc: BaseException) -> Optional[float]:
    """
    Best-effort extraction of a server-suggested retry delay (in seconds)
    from a 429's `Retry-After` response header.
    """
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    retry_after = headers.get("retry-after")
    if retry_after is None:
        return None
    try:
        return float(retry_after)
    except (TypeError, ValueError):
        return None


def is_retryable_groq_error(exc: BaseException) -> bool:
    """True for 429 (rate limit), connection, timeout, and 5xx errors — the cases worth retrying."""
    if isinstance(exc, (groq.RateLimitError, groq.APIConnectionError, groq.APITimeoutError, groq.InternalServerError)):
        return True
    if isinstance(exc, groq.APIStatusError) and getattr(exc, "status_code", None) and exc.status_code >= 500:
        return True
    return False


class GroqRateLimiter:
    """
    Tenacity `wait` callable for Groq API calls.

    On HTTP 429, waits the server-suggested `Retry-After` header value if
    present; otherwise (and for 5xx/connection errors) falls back to
    exponential backoff between `base_delay` and `max_delay` seconds.
    """

    def __init__(self, base_delay: Optional[float] = None, max_delay: float = 30.0) -> None:
        self.base_delay = base_delay if base_delay is not None else GroqConfig.RETRY_BASE_DELAY
        self.max_delay = max_delay

    def __call__(self, retry_state: RetryCallState) -> float:
        exc: Optional[BaseException] = None
        if retry_state.outcome is not None:
            exc = retry_state.outcome.exception()

        if isinstance(exc, groq.RateLimitError):
            get_groq_usage_stats().record_rate_limited()
            retry_delay = _parse_retry_after_seconds(exc)
            if retry_delay is not None:
                logger.warning(f"Groq rate limited — waiting server-suggested {retry_delay:.1f}s")
                return min(retry_delay, self.max_delay)

        exponential = self.base_delay * (2 ** max(0, retry_state.attempt_number - 1))
        return min(exponential, self.max_delay)
