from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.agent.models import AgentState, AgentTask, ToolResult, TraceStep
from app.utils.logging import get_logger

logger = get_logger(__name__)


class TraceGenerator:
    """
    Records every agent reasoning step as an immutable TraceStep.

    The complete trace provides full auditability of how the agent
    reached its conclusions — critical for clinical accountability.
    """

    def __init__(self) -> None:
        self._trace: List[TraceStep] = []
        self._step_start_times: Dict[str, float] = {}

    def start_step(self, task_id: str) -> None:
        self._step_start_times[task_id] = time.time()

    def record_step(
        self,
        state: AgentState,
        task: AgentTask,
        result: ToolResult,
        reasoning: str,
        next_action: str,
    ) -> TraceStep:
        start = self._step_start_times.pop(task.task_id, time.time())
        duration_ms = (time.time() - start) * 1000

        state_changes = _describe_state_changes(task, result)

        step = TraceStep(
            step=len(self._trace) + 1,
            reasoning=reasoning,
            selected_tool=task.tool_name,
            tool_input={
                "task_name": task.name,
                "document_ids": task.document_ids,
                "parameters": task.parameters,
            },
            tool_output=result.findings if result.success else {"error": result.error},
            state_changes=state_changes,
            next_action=next_action,
            duration_ms=round(duration_ms, 1),
            error=result.error if not result.success else None,
            tokens_used=result.tokens_used,
        )

        self._trace.append(step)
        self._log_step(step)
        return step

    def record_planning_step(
        self,
        reasoning: str,
        plan_summary: str,
        iteration: int,
    ) -> None:
        step = TraceStep(
            step=len(self._trace) + 1,
            reasoning=reasoning,
            selected_tool="planner",
            tool_input={"iteration": iteration},
            tool_output={"plan": plan_summary},
            state_changes="Plan generated",
            next_action="Execute first pending task",
        )
        self._trace.append(step)
        logger.info("Planning step recorded", step=step.step, iteration=iteration)

    def record_replan_step(
        self,
        trigger: str,
        new_task_names: List[str],
        reasoning: str,
    ) -> None:
        step = TraceStep(
            step=len(self._trace) + 1,
            reasoning=reasoning,
            selected_tool="replanner",
            tool_input={"trigger": trigger},
            tool_output={"new_tasks": new_task_names},
            state_changes=f"Added {len(new_task_names)} new task(s): {', '.join(new_task_names)}",
            next_action="Resume execution with updated plan",
        )
        self._trace.append(step)
        logger.info("Replanning step recorded", trigger=trigger, new_tasks=new_task_names)

    def record_termination(
        self,
        reason: str,
        state: AgentState,
    ) -> None:
        step = TraceStep(
            step=len(self._trace) + 1,
            reasoning=reason,
            selected_tool="terminator",
            tool_input={},
            tool_output={
                "status": state.status.value,
                "iterations": state.iteration_count,
                "completed_tasks": len(state.completed_tasks),
                "failed_tasks": len(state.failed_tasks),
            },
            state_changes=f"Agent terminated: {reason}",
            next_action="Return AgentRunResult to caller",
        )
        self._trace.append(step)
        logger.info("Termination step recorded", reason=reason, status=state.status.value)

    def get_trace(self) -> List[TraceStep]:
        return list(self._trace)

    def get_step_count(self) -> int:
        return len(self._trace)

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return [s.model_dump(mode="json") for s in self._trace]

    def _log_step(self, step: TraceStep) -> None:
        if step.error:
            logger.warning(
                "Agent step failed",
                step=step.step,
                tool=step.selected_tool,
                error=step.error,
                duration_ms=step.duration_ms,
            )
        else:
            logger.info(
                "Agent step completed",
                step=step.step,
                tool=step.selected_tool,
                duration_ms=step.duration_ms,
                tokens=step.tokens_used,
            )


def _describe_state_changes(task: AgentTask, result: ToolResult) -> str:
    if not result.success:
        return f"Tool {task.tool_name} failed: {result.error}"

    parts = []
    if result.facts_extracted > 0:
        parts.append(f"{result.facts_extracted} facts extracted")
    for key, val in result.findings.items():
        if isinstance(val, (int, float)) and val > 0:
            parts.append(f"{key}={val}")
    return "; ".join(parts) if parts else "Tool completed, no facts extracted"
