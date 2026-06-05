from __future__ import annotations

from app.agent.models import AgentRunStatus, AgentState
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class TerminationController:
    """
    Evaluates whether the agent loop should stop.

    Stop conditions (in priority order):
    1. Critical escalation required — stop immediately
    2. Iteration cap exceeded — timeout protection
    3. No pending tasks — all work done
    4. All critical fields populated and no pending tasks remain
    """

    def __init__(self, max_iterations: int = 15) -> None:
        self.max_iterations = max_iterations

    def should_stop(self, state: AgentState, kb: KnowledgeRepository) -> bool:
        reason = self._evaluate(state, kb)
        if reason:
            state.termination_reason = reason
            logger.info("Termination condition met", reason=reason, iteration=state.iteration_count)
            return True
        return False

    def _evaluate(self, state: AgentState, kb: KnowledgeRepository) -> str | None:
        # 1. Immediate escalation (critical conflicts found)
        if state.escalation_required and len(state.completed_tasks) >= 3:
            state.status = AgentRunStatus.ESCALATED
            return "Critical clinical conflict requires clinician review — escalating"

        # 2. Iteration cap
        if state.iteration_count >= self.max_iterations:
            state.status = AgentRunStatus.TIMED_OUT
            return f"Maximum iteration limit ({self.max_iterations}) reached"

        # 3. No pending tasks
        ready_pending = [t for t in state.pending_tasks if state.is_task_ready(t)]
        if not ready_pending and not state.pending_tasks:
            state.status = AgentRunStatus.COMPLETED
            return "All planned tasks completed"

        # 4. All critical fields present and no blocking tasks remain
        missing = kb.get_missing_critical_fields()
        if not missing and not ready_pending:
            state.status = AgentRunStatus.COMPLETED
            return "All critical clinical fields populated"

        return None

    def compute_final_status(self, state: AgentState, kb: KnowledgeRepository) -> AgentRunStatus:
        if state.escalation_required:
            return AgentRunStatus.ESCALATED
        if state.iteration_count >= self.max_iterations:
            return AgentRunStatus.TIMED_OUT
        if state.failed_tasks and not state.completed_tasks:
            return AgentRunStatus.FAILED
        return AgentRunStatus.COMPLETED
