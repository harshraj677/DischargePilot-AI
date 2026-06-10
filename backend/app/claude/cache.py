"""
Claude Response Cache

SHA256(document_content)-keyed file cache for the Clinical Knowledge
Extraction Engine. If a document set has already been processed, the cached
structured extraction is reused and Claude is never called again for it.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import BASE_DIR, settings
from app.claude.usage import get_claude_usage_stats

logger = logging.getLogger(__name__)

CACHE_DIR = BASE_DIR / "cache" / "claude_responses"


class ClaudeResponseCache:
    """File-based cache for Claude extraction responses, keyed by content hash."""

    def __init__(self, cache_dir: Path = CACHE_DIR) -> None:
        self._dir = cache_dir

    @staticmethod
    def hash_content(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get(self, content_hash: str) -> Optional[Dict[str, Any]]:
        if not settings.CLAUDE_RESPONSE_CACHE_ENABLED:
            return None
        usage = get_claude_usage_stats()
        path = self._dir / f"{content_hash}.json"
        if not path.exists():
            usage.record_cache_miss()
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            usage.record_cache_hit()
            return data
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Failed to read cache entry {content_hash}: {exc}")
            usage.record_cache_miss()
            return None

    def set(self, content_hash: str, data: Dict[str, Any]) -> None:
        if not settings.CLAUDE_RESPONSE_CACHE_ENABLED:
            return
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            path = self._dir / f"{content_hash}.json"
            path.write_text(json.dumps(data), encoding="utf-8")
        except OSError as exc:
            logger.warning(f"Failed to write cache entry {content_hash}: {exc}")


_cache_instance: Optional[ClaudeResponseCache] = None


def get_claude_response_cache() -> ClaudeResponseCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ClaudeResponseCache()
    return _cache_instance
