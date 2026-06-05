"""
Phase 5 enhanced tool framework types.

Provides enhanced execution records, retry policy, and timeout helpers
that wrap the base tool execution lifecycle.
"""
from __future__ import annotations

import asyncio
import time
from typing import Callable, Optional

from app.safety.models import ToolError, ToolExecutionRecord, ToolStatus
from app.utils.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_TIMEOUT_SECONDS = 120


class RetryPolicy:
    """Exponential back-off retry policy for tool execution."""

    def __init__(
        self,
        max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
        base_delay_seconds: float = 2.0,
        max_delay_seconds: float = 30.0,
    ) -> None:
        self.max_attempts = max_attempts
        self.base_delay = base_delay_seconds
        self.max_delay = max_delay_seconds

    def delay_for_attempt(self, attempt: int) -> float:
        """Return seconds to wait before the given attempt (0-indexed)."""
        if attempt == 0:
            return 0.0
        raw = self.base_delay * (2 ** (attempt - 1))
        return min(raw, self.max_delay)

    def should_retry(self, attempt: int, error: ToolError) -> bool:
        return attempt < self.max_attempts and error.is_retryable


async def execute_with_policy(
    tool_name: str,
    task_id: str,
    fn: Callable,
    retry_policy: Optional[RetryPolicy] = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> ToolExecutionRecord:
    """
    Wrap a tool coroutine with retry logic and timeout.

    Returns a ToolExecutionRecord regardless of outcome (never raises).
    The caller is responsible for inspecting `record.status`.
    """
    policy = retry_policy or RetryPolicy()
    record = ToolExecutionRecord(
        tool_name=tool_name,
        task_id=task_id,
        status=ToolStatus.RUNNING,
    )
    start = time.time()

    for attempt in range(policy.max_attempts):
        record.attempts = attempt + 1
        delay = policy.delay_for_attempt(attempt)
        if delay > 0:
            record.status = ToolStatus.RETRYING
            logger.debug("Retrying tool", tool=tool_name, attempt=attempt, delay=delay)
            await asyncio.sleep(delay)

        try:
            result = await asyncio.wait_for(fn(), timeout=timeout_seconds)
            record.status = ToolStatus.SUCCEEDED
            record.facts_extracted = getattr(result, "facts_extracted", 0)
            record.tokens_used = getattr(result, "tokens_used", 0)
            record.findings = getattr(result, "findings", {})
            record.trace_notes = getattr(result, "trace_notes", "")
            break

        except asyncio.TimeoutError:
            err = ToolError(
                error_code="TIMEOUT",
                message=f"Tool {tool_name} timed out after {timeout_seconds}s",
                tool_name=tool_name,
                attempt=attempt + 1,
                is_retryable=False,
            )
            record.errors.append(err)
            record.status = ToolStatus.TIMED_OUT
            logger.warning("Tool timed out", tool=tool_name, attempt=attempt + 1)
            break

        except Exception as exc:
            err = ToolError(
                error_code="EXECUTION_ERROR",
                message=str(exc)[:500],
                tool_name=tool_name,
                attempt=attempt + 1,
                is_retryable=True,
            )
            record.errors.append(err)
            logger.warning("Tool execution failed", tool=tool_name, attempt=attempt + 1, error=str(exc))

            if not policy.should_retry(attempt + 1, err):
                record.status = ToolStatus.FAILED
                break

    record.duration_ms = (time.time() - start) * 1000
    from datetime import datetime
    record.completed_at = datetime.utcnow()
    return record
