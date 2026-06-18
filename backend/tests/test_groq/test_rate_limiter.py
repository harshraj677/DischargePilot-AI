"""
Tests for GroqRateLimiter and is_retryable_groq_error.

Covers:
- Parsing the server-suggested Retry-After header from a 429 response
- Falling back to exponential backoff when no Retry-After is present
- Capping at max_delay
- Recording rate-limit hits for the "Rate Limit" status panel
- Retryable-error classification (429, 5xx, connection/timeout) vs
  non-retryable (4xx other than 429)
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import groq
import pytest

from app.groq_provider.config import GroqConfig
from app.groq_provider.rate_limiter import GroqRateLimiter, is_retryable_groq_error
from app.groq_provider.usage import get_groq_usage_stats


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def _status_error(cls, code: int, headers: dict | None = None, message: str = "error"):
    response = httpx.Response(status_code=code, headers=headers or {}, request=_request())
    return cls(message, response=response, body=None)


def _retry_state(exc: BaseException, attempt_number: int = 1) -> SimpleNamespace:
    outcome = MagicMock()
    outcome.exception.return_value = exc
    return SimpleNamespace(outcome=outcome, attempt_number=attempt_number)


@pytest.fixture(autouse=True)
def _reset_usage():
    stats = get_groq_usage_stats()
    stats.rate_limited_count = 0
    yield


class TestIsRetryableGroqError:
    def test_429_is_retryable(self):
        error = _status_error(groq.RateLimitError, 429)
        assert is_retryable_groq_error(error) is True

    def test_5xx_is_retryable(self):
        error = _status_error(groq.InternalServerError, 503)
        assert is_retryable_groq_error(error) is True

    def test_connection_error_is_retryable(self):
        error = groq.APIConnectionError(request=_request())
        assert is_retryable_groq_error(error) is True

    def test_400_is_not_retryable(self):
        error = _status_error(groq.APIStatusError, 400)
        assert is_retryable_groq_error(error) is False

    def test_401_is_not_retryable(self):
        error = _status_error(groq.APIStatusError, 401)
        assert is_retryable_groq_error(error) is False

    def test_generic_exception_is_not_retryable(self):
        assert is_retryable_groq_error(ValueError("boom")) is False


class TestRetryDelayParsing:
    def test_429_with_retry_after_waits_server_suggested_seconds(self):
        limiter = GroqRateLimiter(base_delay=2.0, max_delay=30.0)
        error = _status_error(groq.RateLimitError, 429, headers={"retry-after": "13"})

        wait_time = limiter(_retry_state(error, attempt_number=1))

        assert wait_time == 13.0

    def test_429_without_retry_after_falls_back_to_exponential(self):
        limiter = GroqRateLimiter(base_delay=2.0, max_delay=30.0)
        error = _status_error(groq.RateLimitError, 429)

        wait_time = limiter(_retry_state(error, attempt_number=2))

        assert wait_time == pytest.approx(4.0)

    def test_retry_delay_capped_at_max_delay(self):
        limiter = GroqRateLimiter(base_delay=2.0, max_delay=20.0)
        error = _status_error(groq.RateLimitError, 429, headers={"retry-after": "60"})

        wait_time = limiter(_retry_state(error, attempt_number=1))

        assert wait_time == 20.0

    def test_429_records_rate_limited_usage_stat(self):
        limiter = GroqRateLimiter(base_delay=2.0, max_delay=30.0)
        error = _status_error(groq.RateLimitError, 429)

        limiter(_retry_state(error, attempt_number=1))

        usage = get_groq_usage_stats().to_dict()
        assert usage["rate_limited_count"] == 1

    def test_5xx_uses_exponential_backoff(self):
        limiter = GroqRateLimiter(base_delay=2.0, max_delay=30.0)
        error = _status_error(groq.InternalServerError, 503)

        wait_time = limiter(_retry_state(error, attempt_number=3))

        assert wait_time == pytest.approx(8.0)

    def test_5xx_does_not_record_rate_limited_stat(self):
        limiter = GroqRateLimiter(base_delay=2.0, max_delay=30.0)
        error = _status_error(groq.InternalServerError, 503)

        limiter(_retry_state(error, attempt_number=1))

        usage = get_groq_usage_stats().to_dict()
        assert usage["rate_limited_count"] == 0


class TestDefaultConfiguration:
    def test_default_base_delay_from_config(self):
        limiter = GroqRateLimiter()
        assert limiter.base_delay == GroqConfig.RETRY_BASE_DELAY

    def test_custom_max_delay_overrides_default(self):
        limiter = GroqRateLimiter(max_delay=20.0)
        assert limiter.max_delay == 20.0
