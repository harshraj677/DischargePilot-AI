"""
Tests for ClaudeResponseCache (STEP 5 of the Gemini -> Claude migration).

SHA256(document_content)-keyed file cache: if a document set has already been
processed, the cached structured extraction is reused and Claude is never
called again for it.
"""
import hashlib

import pytest

from app.claude.cache import ClaudeResponseCache
from app.claude.usage import get_claude_usage_stats
from app.config import settings


@pytest.fixture(autouse=True)
def _reset_usage():
    stats = get_claude_usage_stats()
    stats.cache_hits = 0
    stats.cache_misses = 0
    yield


@pytest.fixture
def cache(tmp_path):
    return ClaudeResponseCache(cache_dir=tmp_path / "claude_responses")


class TestHashContent:
    def test_hash_is_sha256_hexdigest(self):
        content = "ADMISSION NOTE\nPatient: John Doe"
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert ClaudeResponseCache.hash_content(content) == expected

    def test_same_content_same_hash(self):
        content = "Some clinical document text"
        assert ClaudeResponseCache.hash_content(content) == ClaudeResponseCache.hash_content(content)

    def test_different_content_different_hash(self):
        assert ClaudeResponseCache.hash_content("doc A") != ClaudeResponseCache.hash_content("doc B")


class TestGetSet:
    def test_get_returns_none_for_missing_entry(self, cache):
        assert cache.get("does-not-exist") is None

    def test_set_then_get_returns_same_data(self, cache):
        content_hash = ClaudeResponseCache.hash_content("doc text")
        data = {"diagnoses": [{"name": "Type 2 Diabetes Mellitus"}], "medications": []}

        cache.set(content_hash, data)
        result = cache.get(content_hash)

        assert result == data

    def test_cache_hit_increments_usage_stats(self, cache):
        content_hash = ClaudeResponseCache.hash_content("doc text")
        cache.set(content_hash, {"diagnoses": []})

        cache.get(content_hash)

        usage = get_claude_usage_stats().to_dict()
        assert usage["cache_hits"] == 1
        assert usage["cache_misses"] == 0

    def test_cache_miss_increments_usage_stats(self, cache):
        cache.get("nonexistent-hash")

        usage = get_claude_usage_stats().to_dict()
        assert usage["cache_hits"] == 0
        assert usage["cache_misses"] == 1

    def test_corrupted_cache_entry_is_treated_as_miss(self, cache, tmp_path):
        content_hash = "corrupted"
        cache._dir.mkdir(parents=True, exist_ok=True)
        (cache._dir / f"{content_hash}.json").write_text("{not valid json", encoding="utf-8")

        result = cache.get(content_hash)

        assert result is None
        usage = get_claude_usage_stats().to_dict()
        assert usage["cache_misses"] == 1


class TestCacheDisabled:
    def test_get_returns_none_when_disabled(self, cache, monkeypatch):
        content_hash = ClaudeResponseCache.hash_content("doc text")
        cache.set(content_hash, {"diagnoses": []})

        monkeypatch.setattr(settings, "CLAUDE_RESPONSE_CACHE_ENABLED", False)

        assert cache.get(content_hash) is None

    def test_set_is_noop_when_disabled(self, cache, monkeypatch):
        monkeypatch.setattr(settings, "CLAUDE_RESPONSE_CACHE_ENABLED", True)
        content_hash = ClaudeResponseCache.hash_content("doc text")

        monkeypatch.setattr(settings, "CLAUDE_RESPONSE_CACHE_ENABLED", False)
        cache.set(content_hash, {"diagnoses": []})

        monkeypatch.setattr(settings, "CLAUDE_RESPONSE_CACHE_ENABLED", True)
        assert cache.get(content_hash) is None
