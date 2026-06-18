"""
Tests for GroqHealthService.

All openai SDK calls are mocked so these tests run offline.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import groq
import pytest

from app.groq_provider.config import GroqConfig
from app.groq_provider.health import GroqHealthService


def _chat_response(text: str):
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def _status_error(cls, code: int, message: str):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status_code=code, headers={}, request=request)
    return cls(message, response=response, body=None)


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.setattr(GroqConfig, "API_KEY", "test-groq-key")
    GroqHealthService.reset_cache()
    yield
    GroqHealthService.reset_cache()


@pytest.fixture
def mock_sdk():
    with patch("app.groq_provider.health.AsyncGroq") as mock_sdk_cls:
        sdk = MagicMock()
        sdk.chat.completions.create = AsyncMock()
        mock_sdk_cls.return_value = sdk
        yield sdk


class TestMissingApiKey:
    @pytest.mark.asyncio
    async def test_missing_api_key_fails(self, monkeypatch):
        monkeypatch.setattr(GroqConfig, "API_KEY", None)

        result = await GroqHealthService.check_connection()

        assert result == {
            "provider": "groq",
            "status": "failed",
            "authenticated": False,
            "model": GroqConfig.TEXT_MODEL,
            "error": "GROQ_API_KEY environment variable not set",
        }


class TestSuccessfulInitialization:
    @pytest.mark.asyncio
    async def test_healthy_when_generate_content_succeeds(self, mock_sdk):
        mock_sdk.chat.completions.create = AsyncMock(return_value=_chat_response("pong"))

        result = await GroqHealthService.check_connection()

        assert result == {
            "provider": "groq",
            "status": "healthy",
            "authenticated": True,
            "model": GroqConfig.TEXT_MODEL,
        }


class TestPermissionDenied:
    @pytest.mark.asyncio
    async def test_403_permission_denied_fails(self, mock_sdk):
        mock_sdk.chat.completions.create = AsyncMock(
            side_effect=_status_error(groq.PermissionDeniedError, 403, "Your account has been denied access.")
        )

        result = await GroqHealthService.check_connection()

        assert result["status"] == "failed"
        assert result["authenticated"] is False
        assert result["model"] == GroqConfig.TEXT_MODEL
        assert "denied" in result["error"].lower()


class TestUnauthenticated:
    @pytest.mark.asyncio
    async def test_401_unauthenticated_fails(self, mock_sdk):
        mock_sdk.chat.completions.create = AsyncMock(
            side_effect=_status_error(
                groq.AuthenticationError,
                401,
                "Request had invalid authentication credentials.",
            )
        )

        result = await GroqHealthService.check_connection()

        assert result["status"] == "failed"
        assert result["authenticated"] is False
        assert "invalid authentication" in result["error"].lower()


class TestKeyFormatAgnostic:
    """The health service must not validate/reject keys based on their
    prefix — any non-empty string is passed straight to AsyncGroq and
    Groq's backend is the sole arbiter of whether it authenticates."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "api_key",
        [
            "gsk_ExampleKeyFormat1234567890abcdef",
            "sk-AnotherKeyFormatExample0987654321",
        ],
    )
    async def test_key_is_passed_through_regardless_of_prefix(self, monkeypatch, api_key):
        monkeypatch.setattr(GroqConfig, "API_KEY", api_key)
        GroqHealthService.reset_cache()

        with patch("app.groq_provider.health.AsyncGroq") as mock_sdk_cls:
            sdk = MagicMock()
            sdk.chat.completions.create = AsyncMock(return_value=_chat_response("pong"))
            mock_sdk_cls.return_value = sdk

            result = await GroqHealthService.check_connection()

            mock_sdk_cls.assert_called_once_with(api_key=api_key)

        assert result["status"] == "healthy"
        assert result["authenticated"] is True


class TestUnavailableService:
    @pytest.mark.asyncio
    async def test_server_error_fails(self, mock_sdk):
        mock_sdk.chat.completions.create = AsyncMock(
            side_effect=_status_error(groq.InternalServerError, 503, "The service is currently unavailable.")
        )

        result = await GroqHealthService.check_connection()

        assert result["status"] == "failed"
        assert result["authenticated"] is False


class TestCaching:
    @pytest.mark.asyncio
    async def test_cached_result_avoids_second_call(self, mock_sdk):
        mock_sdk.chat.completions.create = AsyncMock(return_value=_chat_response("pong"))

        first = await GroqHealthService.check_connection()
        second = await GroqHealthService.check_connection()

        assert first == second
        assert mock_sdk.chat.completions.create.call_count == 1

    @pytest.mark.asyncio
    async def test_use_cache_false_forces_recheck(self, mock_sdk):
        mock_sdk.chat.completions.create = AsyncMock(return_value=_chat_response("pong"))

        await GroqHealthService.check_connection()
        await GroqHealthService.check_connection(use_cache=False)

        assert mock_sdk.chat.completions.create.call_count == 2
