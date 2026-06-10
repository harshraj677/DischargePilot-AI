"""
Tests for ClaudeAgentClient (STEP 2 + STEP 7 of the Gemini -> Claude migration).

All Anthropic SDK calls are mocked so these tests run offline.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest
import tenacity

from app.claude import agent_client as agent_client_module
from app.claude.agent_client import ClaudeAgentClient, ClaudeUnavailableError
from app.claude.config import ClaudeConfig
from app.claude.usage import get_claude_usage_stats


def _text_response(text: str):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.setattr(ClaudeConfig, "API_KEY", "test-anthropic-key")
    ClaudeAgentClient._instance = None

    stats = get_claude_usage_stats()
    for attr in ("text_requests", "vision_requests", "ocr_requests", "errors", "cache_hits", "cache_misses"):
        setattr(stats, attr, 0)
    stats.last_request_at = None
    stats.last_error = None
    stats.last_error_at = None

    yield

    ClaudeAgentClient._instance = None


@pytest.fixture
def client_with_mock_sdk():
    with patch("app.claude.agent_client.anthropic.AsyncAnthropic") as mock_sdk_cls:
        mock_sdk = MagicMock()
        mock_sdk_cls.return_value = mock_sdk
        client = ClaudeAgentClient.get_instance()
        yield client, mock_sdk


# ── Initialization ──────────────────────────────────────────────────────────────

class TestClaudeAgentClientInit:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.setattr(ClaudeConfig, "API_KEY", None)
        ClaudeAgentClient._instance = None
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            ClaudeAgentClient()

    def test_get_instance_is_singleton(self, client_with_mock_sdk):
        client, _ = client_with_mock_sdk
        assert ClaudeAgentClient.get_instance() is client


# ── generate_content: text ───────────────────────────────────────────────────────

class TestGenerateContentText:
    @pytest.mark.asyncio
    async def test_text_prompt_uses_text_model(self, client_with_mock_sdk):
        client, mock_sdk = client_with_mock_sdk
        mock_sdk.messages.create = AsyncMock(return_value=_text_response("hello world"))

        result = await client.generate_content(prompt="Summarize this chart")

        assert result == "hello world"
        _, kwargs = mock_sdk.messages.create.call_args
        assert kwargs["model"] == ClaudeConfig.TEXT_MODEL

    @pytest.mark.asyncio
    async def test_records_usage_on_success(self, client_with_mock_sdk):
        client, mock_sdk = client_with_mock_sdk
        mock_sdk.messages.create = AsyncMock(return_value=_text_response("ok"))

        await client.generate_content(prompt="hi")

        usage = get_claude_usage_stats().to_dict()
        assert usage["text_requests"] == 1
        assert usage["total_requests"] == 1
        assert usage["last_request_at"] is not None


# ── generate_content: vision ─────────────────────────────────────────────────────

class TestGenerateContentVision:
    @pytest.mark.asyncio
    async def test_image_prompt_uses_vision_model(self, client_with_mock_sdk):
        from PIL import Image

        client, mock_sdk = client_with_mock_sdk
        mock_sdk.messages.create = AsyncMock(return_value=_text_response("extracted text"))

        img = Image.new("RGB", (10, 10), color="white")
        result = await client.generate_content(prompt="OCR this", images=[img], model_type="vision")

        assert result == "extracted text"
        _, kwargs = mock_sdk.messages.create.call_args
        assert kwargs["model"] == ClaudeConfig.VISION_MODEL

        content = kwargs["messages"][0]["content"]
        assert any(block["type"] == "image" for block in content)
        assert any(block["type"] == "text" for block in content)

        usage = get_claude_usage_stats().to_dict()
        assert usage["vision_requests"] == 1


# ── STEP 7: failure handling ─────────────────────────────────────────────────────

class TestFailureHandling:
    @pytest.mark.asyncio
    async def test_rate_limit_exhausted_raises_claude_unavailable(self, client_with_mock_sdk):
        client, _mock_sdk = client_with_mock_sdk
        error = anthropic.RateLimitError("rate limited", response=httpx.Response(429, request=_request()), body=None)
        client._create_with_retry = AsyncMock(side_effect=error)

        with pytest.raises(ClaudeUnavailableError):
            await client.generate_content(prompt="hi")

        usage = get_claude_usage_stats().to_dict()
        assert usage["errors"] == 1
        assert usage["last_error_at"] is not None

    @pytest.mark.asyncio
    async def test_authentication_error_raises_claude_unavailable(self, client_with_mock_sdk):
        client, _mock_sdk = client_with_mock_sdk
        error = anthropic.AuthenticationError(
            "bad key", response=httpx.Response(401, request=_request()), body=None
        )
        client._create_with_retry = AsyncMock(side_effect=error)

        with pytest.raises(ClaudeUnavailableError, match="authentication failed"):
            await client.generate_content(prompt="hi")

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_failure(self, client_with_mock_sdk):
        client, _mock_sdk = client_with_mock_sdk
        client._create_with_retry = AsyncMock(side_effect=Exception("boom"))

        assert await client.health_check() is False


# ── STEP 7: retry / exponential backoff configuration ────────────────────────────

class TestRetryConfiguration:
    def test_retries_up_to_max_retries(self):
        retrying = agent_client_module.ClaudeAgentClient._create_with_retry.retry
        assert retrying.stop.max_attempt_number == ClaudeConfig.MAX_RETRIES == 3

    def test_uses_exponential_backoff(self):
        retrying = agent_client_module.ClaudeAgentClient._create_with_retry.retry
        assert isinstance(retrying.wait, tenacity.wait_exponential)

    def test_only_retries_transient_errors(self):
        retrying = agent_client_module.ClaudeAgentClient._create_with_retry.retry
        assert retrying.retry.exception_types == (
            anthropic.RateLimitError,
            anthropic.APIConnectionError,
            anthropic.InternalServerError,
        )

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self, client_with_mock_sdk):
        """A transient connection error is retried and the second attempt succeeds."""
        client, mock_sdk = client_with_mock_sdk
        retrying = agent_client_module.ClaudeAgentClient._create_with_retry.retry
        original_wait = retrying.wait
        retrying.wait = tenacity.wait_none()
        try:
            error = anthropic.APIConnectionError(message="connection reset", request=_request())
            mock_sdk.messages.create = AsyncMock(side_effect=[error, _text_response("recovered")])

            result = await client.generate_content(prompt="hi")

            assert result == "recovered"
            assert mock_sdk.messages.create.call_count == 2
        finally:
            retrying.wait = original_wait
