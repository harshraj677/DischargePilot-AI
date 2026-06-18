from __future__ import annotations

from app.agent.models import AgentRunStatus, AgentState
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class TerminationController:
    """
    Evaluates whether the agent loop should stop.

    Stop conditions (in priority order):
    1. summary_generator has completed — pipeline goal reached, stop
       regardless of any leftover non-essential pending tasks (e.g. a still
       -pending drug_interaction_checker must not block this; "terminator
       runs right after summary generation"). Escalation is reflected in
       the final status (see compute_final_status) but must NEVER short
       -circuit the loop before summary_generator runs — escalation must
       never bypass SummaryGenerator.
    2. Iteration cap exceeded — timeout protection
    3. No pending tasks — all work done
    4. All critical fields populated and no pending tasks remain
    """

    def __init__(self, max_iterations: int = 20) -> None:
        self.max_iterations = max_iterations

    def should_stop(self, state: AgentState, kb: KnowledgeRepository) -> bool:
        reason = self._evaluate(state, kb)
        if reason:
            state.termination_reason = reason
            logger.info("Termination condition met", reason=reason, iteration=state.iteration_count)
            return True
        return False

    def _evaluate(self, state: AgentState, kb: KnowledgeRepository) -> str | None:
        # 1. Summary generated — pipeline goal reached. NOTE: this used to
        # be preceded by an "escalation_required -> stop immediately"
        # condition, which silently ended runs as ESCALATED before
        # summary_generator ever executed — that's exactly why escalated
        # runs had no discharge summary ("Run Complete / ESCALATED" but the
        # summary page showed Not Found). Escalation must never bypass
        # summary generation, so it no longer stops the loop early; it's
        # only reflected in the final status (compute_final_status).
        if state.has_completed("summary_generator"):
            state.status = AgentRunStatus.ESCALATED if state.escalation_required else AgentRunStatus.COMPLETED
            return "Discharge summary generated — pipeline complete"

        # 2. Iteration cap
        if state.iteration_count >= self.max_iterations:
            state.status = AgentRunStatus.TIMED_OUT
            logger.error(
                "TIMEOUT: maximum iteration limit reached without completing the plan",
                iteration=state.iteration_count,
                max_iterations=self.max_iterations,
                pending_tasks=[t.tool_name for t in state.pending_tasks],
                completed_tasks=[t.tool_name for t in state.completed_tasks],
                failed_tasks=[t.tool_name for t in state.failed_tasks],
                summary_generated=state.has_completed("summary_generator"),
            )
            return f"Maximum iteration limit ({self.max_iterations}) reached"

        # 3. No pending tasks
        ready_pending = [t for t in state.pending_tasks if state.is_task_ready(t)]
        if not ready_pending and not state.pending_tasks:
            state.status = AgentRunStatus.ESCALATED if state.escalation_required else AgentRunStatus.COMPLETED
            return "All planned tasks completed"

        # 4. All critical fields present and no blocking tasks remain
        missing = kb.get_missing_critical_fields()
        if not missing and not ready_pending:
            state.status = AgentRunStatus.ESCALATED if state.escalation_required else AgentRunStatus.COMPLETED
            return "All critical clinical fields populated"

        return None

    def compute_final_status(self, state: AgentState, kb: KnowledgeRepository) -> AgentRunStatus:
        if state.escalation_required:
            return AgentRunStatus.ESCALATED
        if state.has_completed("summary_generator"):
            return AgentRunStatus.COMPLETED
        if state.iteration_count >= self.max_iterations:
            return AgentRunStatus.TIMED_OUT
        if state.failed_tasks and not state.completed_tasks:
            return AgentRunStatus.FAILED
        return AgentRunStatus.COMPLETED
