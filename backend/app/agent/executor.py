from __future__ import annotations

import asyncio
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.agent.models import AgentState, AgentTask, ToolResult
from app.agent.tool_registry import ToolRegistry
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

_TOOL_TIMEOUT_SECONDS = 120


class ExecutionEngine:
    """
    Runs a single AgentTask through its corresponding tool.

    Guarantees:
    - Never raises: all exceptions are caught and returned as ToolResult(success=False)
    - Retry logic: retries up to task.max_attempts times on failure
    - Timeout protection: cancels tools that run longer than _TOOL_TIMEOUT_SECONDS
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def execute(
        self,
        task: AgentTask,
        state: AgentState,
        kb: KnowledgeRepository,
        db: Session,
    ) -> ToolResult:
        tool = self.registry.get(task.tool_name)
        if tool is None:
            error = f"Tool '{task.tool_name}' not found in registry"
            logger.error("Unknown tool requested", tool_name=task.tool_name)
            return ToolResult(
                task_id=task.task_id,
                tool_name=task.tool_name,
                success=False,
                error=error,
            )

        state.mark_task_in_progress(task)
        last_error: Optional[str] = None

        for attempt in range(1, task.max_attempts + 1):
            try:
                logger.info(
                    "Executing tool",
                    tool=task.tool_name,
                    task=task.name,
                    attempt=attempt,
                    iteration=state.iteration_count,
                )
                result = await asyncio.wait_for(
                    tool.execute(task, state, kb, db),
                    timeout=_TOOL_TIMEOUT_SECONDS,
                )

                if result.success:
                    state.mark_task_completed(task, result.findings)
                    logger.info(
                        "Tool succeeded",
                        tool=task.tool_name,
                        facts=result.facts_extracted,
                        tokens=result.tokens_used,
                        duration_ms=result.duration_ms,
                    )
                    return result

                last_error = result.error
                logger.warning(
                    "Tool returned failure",
                    tool=task.tool_name,
                    attempt=attempt,
                    error=last_error,
                )

            except asyncio.TimeoutError:
                last_error = f"Tool timed out after {_TOOL_TIMEOUT_SECONDS}s"
                logger.error("Tool timed out", tool=task.tool_name, attempt=attempt)

            except Exception as exc:
                last_error = f"Unexpected error: {exc}"
                logger.error("Tool raised exception", tool=task.tool_name, error=str(exc))

            # Exponential back-off between retries
            if attempt < task.max_attempts:
                await asyncio.sleep(2 ** (attempt - 1))

        # All attempts exhausted
        state.mark_task_failed(task, last_error or "All retry attempts failed")
        state.missing_information.append(
            f"Could not extract data via {task.tool_name}: {last_error}"
        )

        return ToolResult(
            task_id=task.task_id,
            tool_name=task.tool_name,
            success=False,
            error=last_error,
            trace_notes=f"Failed after {task.max_attempts} attempt(s): {last_error}",
        )
