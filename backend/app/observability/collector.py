from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from app.observability.models import (
    AgentDecision,
    AgentTrace,
    EventType,
    SafetyEvent,
    TimelineEvent,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ObservabilityCollector:
    """
    Collects and manages observability data for one agent run.

    Intended to be instantiated per AgentLoop.run() invocation and
    passed as context to components that emit events.
    """

    def __init__(self, run_id: str, patient_id: str) -> None:
        self.trace = AgentTrace(run_id=run_id, patient_id=patient_id)
        self._tool_start_times: Dict[str, float] = {}

    # ── Agent lifecycle ────────────────────────────────────────────────────────

    def agent_started(self, document_count: int) -> None:
        self._emit(EventType.AGENT_STARTED, details={"document_count": document_count})

    def agent_completed(self, termination_reason: str, completeness: float) -> None:
        self.trace.completed_at = datetime.utcnow()
        self.trace.termination_reason = termination_reason
        if self.trace.started_at:
            self.trace.total_duration_ms = (
                (self.trace.completed_at - self.trace.started_at).total_seconds() * 1000
            )
        self._emit(
            EventType.AGENT_COMPLETED,
            details={
                "termination_reason": termination_reason,
                "completeness": completeness,
                "total_iterations": self.trace.total_iterations,
            },
        )

    def agent_failed(self, error: str) -> None:
        self._emit(EventType.AGENT_FAILED, details={"error": error})

    # ── Tool lifecycle ─────────────────────────────────────────────────────────

    def tool_started(self, tool_name: str, task_id: str) -> None:
        import time
        self._tool_start_times[task_id] = time.time()
        self._emit(EventType.TOOL_STARTED, tool_name=tool_name, details={"task_id": task_id})

    def tool_completed(
        self,
        tool_name: str,
        task_id: str,
        success: bool,
        tokens: int,
        facts: int,
    ) -> None:
        import time
        start = self._tool_start_times.pop(task_id, time.time())
        duration_ms = (time.time() - start) * 1000

        self.trace.total_tokens_used += tokens
        self.trace.total_facts_extracted += facts
        self.trace.total_iterations += 1
        self.trace.update_tool_stats(tool_name, success, duration_ms, tokens, facts)

        event_type = EventType.TOOL_COMPLETED if success else EventType.TOOL_FAILED
        self._emit(
            event_type,
            tool_name=tool_name,
            duration_ms=duration_ms,
            details={"task_id": task_id, "facts": facts, "tokens": tokens},
        )

    def tool_retried(self, tool_name: str, task_id: str, attempt: int) -> None:
        self._emit(
            EventType.TOOL_RETRIED,
            tool_name=tool_name,
            details={"task_id": task_id, "attempt": attempt},
        )

    # ── Planning ───────────────────────────────────────────────────────────────

    def replan_triggered(self, reason: str, tasks_added: list) -> None:
        self._emit(
            EventType.REPLAN_TRIGGERED,
            details={"reason": reason, "tasks_added": len(tasks_added)},
        )

    def record_decision(
        self,
        step: int,
        reasoning: str,
        selected_tool: Optional[str],
        tasks_added: list,
        tasks_removed: list,
    ) -> None:
        decision = AgentDecision(
            run_id=self.trace.run_id,
            step=step,
            reasoning=reasoning,
            selected_tool=selected_tool,
            tasks_added=tasks_added,
            tasks_removed=tasks_removed,
        )
        self.trace.decisions.append(decision)

    def termination_condition_met(self, condition: str) -> None:
        self._emit(EventType.TERMINATION_CONDITION_MET, details={"condition": condition})

    # ── Safety & summary ──────────────────────────────────────────────────────

    def safety_validation_started(self) -> None:
        self._emit(EventType.SAFETY_VALIDATION_STARTED)

    def safety_validation_completed(
        self, status: str, safety_score: float, flag_count: int
    ) -> None:
        self._emit(
            EventType.SAFETY_VALIDATION_COMPLETED,
            details={
                "status": status,
                "safety_score": safety_score,
                "flag_count": flag_count,
            },
        )

    def record_safety_event(
        self,
        validator_name: str,
        severity: str,
        finding_count: int,
        flag_count: int,
    ) -> None:
        event = SafetyEvent(
            run_id=self.trace.run_id,
            patient_id=self.trace.patient_id,
            validator_name=validator_name,
            severity=severity,
            finding_count=finding_count,
            flag_count=flag_count,
        )
        self.trace.safety_events.append(event)

    def summary_generation_started(self) -> None:
        self._emit(EventType.SUMMARY_GENERATION_STARTED)

    def summary_generation_completed(self, populated_sections: int, total_flags: int) -> None:
        self._emit(
            EventType.SUMMARY_GENERATION_COMPLETED,
            details={"populated_sections": populated_sections, "total_flags": total_flags},
        )

    def escalation_triggered(self, reasons: list) -> None:
        self._emit(EventType.ESCALATION_TRIGGERED, details={"reasons": reasons})

    # ── Internal ──────────────────────────────────────────────────────────────

    def _emit(
        self,
        event_type: EventType,
        tool_name: Optional[str] = None,
        duration_ms: Optional[float] = None,
        details: Optional[dict] = None,
    ) -> None:
        event = TimelineEvent(
            event_type=event_type,
            run_id=self.trace.run_id,
            patient_id=self.trace.patient_id,
            tool_name=tool_name,
            details=details or {},
            duration_ms=duration_ms,
        )
        self.trace.add_event(event)
        logger.debug(
            "Observability event",
            event_type=event_type.value,
            run_id=self.trace.run_id,
        )
