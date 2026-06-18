"""
Groq Usage Stats

Process-lifetime counters for Groq API calls, OCR calls, response-cache
hits/misses, and rate-limit events — backs the "Groq Status" panel in the
frontend.
"""

import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class GroqUsageStats:
    """Thread-safe in-memory counters for Groq usage."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.text_requests = 0
        self.vision_requests = 0
        self.ocr_requests = 0
        self.errors = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.rate_limited_count = 0
        self.last_request_at: Optional[str] = None
        self.last_error: Optional[str] = None
        self.last_error_at: Optional[str] = None

    def record_request(self, kind: str = "text") -> None:
        with self._lock:
            if kind == "vision":
                self.vision_requests += 1
            elif kind == "ocr":
                self.ocr_requests += 1
            else:
                self.text_requests += 1
            self.last_request_at = datetime.now(timezone.utc).isoformat()

    def record_error(self, message: str) -> None:
        with self._lock:
            self.errors += 1
            self.last_error = message
            self.last_error_at = datetime.now(timezone.utc).isoformat()

    def record_rate_limited(self) -> None:
        with self._lock:
            self.rate_limited_count += 1

    def record_cache_hit(self) -> None:
        with self._lock:
            self.cache_hits += 1

    def record_cache_miss(self) -> None:
        with self._lock:
            self.cache_misses += 1

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_requests": self.text_requests + self.vision_requests + self.ocr_requests,
                "text_requests": self.text_requests,
                "vision_requests": self.vision_requests,
                "ocr_requests": self.ocr_requests,
                "errors": self.errors,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "rate_limited_count": self.rate_limited_count,
                "last_request_at": self.last_request_at,
                "last_error": self.last_error,
                "last_error_at": self.last_error_at,
            }


_usage_instance: Optional[GroqUsageStats] = None


def get_groq_usage_stats() -> GroqUsageStats:
    global _usage_instance
    if _usage_instance is None:
        _usage_instance = GroqUsageStats()
    return _usage_instance
