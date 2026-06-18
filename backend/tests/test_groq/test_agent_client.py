"""
Tests for GroqAgentClient.

All groq SDK calls are mocked so these tests run offline.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import groq
import pytest
import tenacity

from app.groq_provider import agent_client as agent_client_module
from app.groq_provider.agent_client import GroqAgentClient, GroqUnavailableError
from app.groq_provider.config import GroqConfig
from app.groq_provider.rate_limiter import GroqRateLimiter, is_retryable_groq_error
from app.groq_provider.usage import get_groq_usage_stats


def _chat_response(text: str):
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def _status_error(cls, code: int, message: str = "error", headers: dict | None = None):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status_code=code, headers=headers or {}, request=request)
    return cls(message, response=response, body=None)


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.setattr(GroqConfig, "API_KEY", "test-groq-key")
    GroqAgentClient._instance = None

    stats = get_groq_usage_stats()
    for attr in ("text_requests", "vision_requests", "ocr_requests", "errors", "cache_hits", "cache_misses", "rate_limited_count"):
        setattr(stats, attr, 0)
    stats.last_request_at = None
    stats.last_error = None
    stats.last_error_at = None

    yield

    GroqAgentClient._instance = None


@pytest.fixture
def client_with_mock_sdk():
    with patch("app.groq_provider.agent_client.AsyncGroq") as mock_sdk_cls:
        mock_sdk = MagicMock()
        mock_sdk.chat.completions.create = AsyncMock()
        mock_sdk_cls.return_value = mock_sdk
        client = GroqAgentClient.get_instance()
        yield client, mock_sdk


# ── Initialization ──────────────────────────────────────────────────────────────

class TestGroqAgentClientInit:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.setattr(GroqConfig, "API_KEY", None)
        GroqAgentClient._instance = None
        with pytest.raises(ValueError, match="GROQ_API_KEY"):
            GroqAgentClient()

    def test_get_instance_is_singleton(self, client_with_mock_sdk):
        client, _ = client_with_mock_sdk
        assert GroqAgentClient.get_instance() is client


# ── generate_content: text ───────────────────────────────────────────────────────

class TestGenerateContentText:
    @pytest.mark.asyncio
    async def test_text_prompt_uses_text_model(self, client_with_mock_sdk):
        client, mock_sdk = client_with_mock_sdk
        mock_sdk.chat.completions.create = AsyncMock(return_value=_chat_response("hello world"))

        result = await client.generate_content(prompt="Summarize this chart")

        assert result == "hello world"
        _, kwargs = mock_sdk.chat.completions.create.call_args
        assert kwargs["model"] == GroqConfig.TEXT_MODEL
        assert kwargs["messages"][0]["content"][0]["text"] == "Summarize this chart"

    @pytest.mark.asyncio
    async def test_records_usage_on_success(self, client_with_mock_sdk):
        client, mock_sdk = client_with_mock_sdk
        mock_sdk.chat.completions.create = AsyncMock(return_value=_chat_response("ok"))

        await client.generate_content(prompt="hi")

        usage = get_groq_usage_stats().to_dict()
        assert usage["text_requests"] == 1
        assert usage["total_requests"] == 1
        assert usage["last_request_at"] is not None


# ── generate_content: vision ─────────────────────────────────────────────────────

class TestGenerateContentVision:
    @pytest.mark.asyncio
    async def test_image_prompt_uses_vision_model(self, client_with_mock_sdk):
        from PIL import Image

        client, mock_sdk = client_with_mock_sdk
        mock_sdk.chat.completions.create = AsyncMock(return_value=_chat_response("extracted text"))

        img = Image.new("RGB", (10, 10), color="white")
        result = await client.generate_content(prompt="OCR this", images=[img], model_type="vision")

        assert result == "extracted text"
        _, kwargs = mock_sdk.chat.completions.create.call_args
        assert kwargs["model"] == GroqConfig.VISION_MODEL

        content_blocks = kwargs["messages"][0]["content"]
        assert any(block["type"] == "image_url" for block in content_blocks)
        assert any(block.get("text") == "OCR this" for block in content_blocks if block["type"] == "text")

        usage = get_groq_usage_stats().to_dict()
        assert usage["vision_requests"] == 1


# ── failure handling ──────────────────────────────────────────────────────────────

class TestFailureHandling:
    @pytest.mark.asyncio
    async def test_rate_limit_exhausted_raises_groq_unavailable(self, client_with_mock_sdk):
        client, _mock_sdk = client_with_mock_sdk
        error = _status_error(groq.RateLimitError, 429, "rate limited")
        client._generate_with_retry = AsyncMock(side_effect=error)

        with pytest.raises(GroqUnavailableError):
            await client.generate_content(prompt="hi")

        usage = get_groq_usage_stats().to_dict()
        assert usage["errors"] == 1
        assert usage["last_error_at"] is not None

    @pytest.mark.asyncio
    async def test_server_error_raises_groq_unavailable(self, client_with_mock_sdk):
        client, _mock_sdk = client_with_mock_sdk
        error = _status_error(groq.InternalServerError, 503, "overloaded")
        client._generate_with_retry = AsyncMock(side_effect=error)

        with pytest.raises(GroqUnavailableError, match="Groq API unavailable"):
            await client.generate_content(prompt="hi")

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_failure(self, client_with_mock_sdk):
        client, _mock_sdk = client_with_mock_sdk
        client._generate_with_retry = AsyncMock(side_effect=Exception("boom"))

        assert await client.health_check() is False


# ── retry / rate-limit-aware backoff configuration ────────────────────────────────

class TestRetryConfiguration:
    def test_retries_up_to_max_retries(self):
        retrying = agent_client_module.GroqAgentClient._generate_with_retry.retry
        assert retrying.stop.max_attempt_number == GroqConfig.MAX_RETRIES == 3

    def test_uses_groq_rate_limiter_for_wait(self):
        retrying = agent_client_module.GroqAgentClient._generate_with_retry.retry
        assert isinstance(retrying.wait, GroqRateLimiter)

    def test_only_retries_retryable_errors(self):
        retrying = agent_client_module.GroqAgentClient._generate_with_retry.retry
        assert retrying.retry.predicate is is_retryable_groq_error

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self, client_with_mock_sdk):
        """A transient 5xx server error is retried and the second attempt succeeds."""
        client, mock_sdk = client_with_mock_sdk
        retrying = agent_client_module.GroqAgentClient._generate_with_retry.retry
        original_wait = retrying.wait
        retrying.wait = tenacity.wait_none()
        try:
            error = _status_error(groq.InternalServerError, 503, "temporarily overloaded")
            mock_sdk.chat.completions.create = AsyncMock(side_effect=[error, _chat_response("recovered")])

            result = await client.generate_content(prompt="hi")

            assert result == "recovered"
            assert mock_sdk.chat.completions.create.call_count == 2
        finally:
            retrying.wait = original_wait

    @pytest.mark.asyncio
    async def test_429_with_retry_after_is_retried_and_succeeds(self, client_with_mock_sdk):
        """A 429 with a server-suggested Retry-After is retried until success."""
        client, mock_sdk = client_with_mock_sdk
        retrying = agent_client_module.GroqAgentClient._generate_with_retry.retry
        original_wait = retrying.wait
        retrying.wait = tenacity.wait_none()
        try:
            error = _status_error(groq.RateLimitError, 429, "rate limited", headers={"retry-after": "0.01"})
            mock_sdk.chat.completions.create = AsyncMock(side_effect=[error, _chat_response("recovered")])

            result = await client.generate_content(prompt="hi")

            assert result == "recovered"
            assert mock_sdk.chat.completions.create.call_count == 2
        finally:
            retrying.wait = original_wait
