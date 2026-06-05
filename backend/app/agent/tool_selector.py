from __future__ import annotations

from typing import List, Optional

from app.agent.models import AgentState, AgentTask
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ToolSelector:
    """
    Priority-based tool selection with dependency resolution.

    Selection algorithm:
    1. Filter to tasks whose dependencies are all satisfied
    2. Among ready tasks, select the lowest priority number (highest urgency)
    3. Skip tasks for which preconditions are not met (e.g., no docs of required type)
    """

    # Tools that require prior extraction to have run
    _ANALYSIS_TOOLS = {
        "conflict_detector",
        "medication_reconciler",
        "drug_interaction_checker",
        "escalation_manager",
    }

    def select_next(self, state: AgentState, kb: KnowledgeRepository) -> Optional[AgentTask]:
        """Return the highest-priority ready task, or None if no tasks are ready."""
        ready = self._get_ready_tasks(state, kb)
        if not ready:
            return None

        # Sort by priority (lowest number first), then creation time
        ready.sort(key=lambda t: (t.priority, t.created_at))
        selected = ready[0]
        logger.debug(
            "Tool selected",
            tool=selected.tool_name,
            priority=selected.priority,
            pending_count=len(state.pending_tasks),
        )
        return selected

    def _get_ready_tasks(self, state: AgentState, kb: KnowledgeRepository) -> List[AgentTask]:
        ready = []
        for task in state.pending_tasks:
            if task.status.value != "pending":
                continue
            if not state.is_task_ready(task):
                continue
            if not self._preconditions_met(task, state, kb):
                continue
            ready.append(task)
        return ready

    def _preconditions_met(self, task: AgentTask, state: AgentState, kb: KnowledgeRepository) -> bool:
        """
        Check tool-specific preconditions before selection.
        Returns False to skip a tool that cannot meaningfully run yet.
        """
        tool_name = task.tool_name

        if tool_name == "lab_extractor":
            # Only run if lab_report documents are available
            return "lab_report" in state.available_document_types

        if tool_name == "conflict_detector":
            # Only run after diagnoses and medications have been extracted
            has_dx = len(kb.kb.diagnoses) > 0
            has_meds = len(kb.kb.medications_discharge) > 0 or len(kb.kb.medications_admission) > 0
            if not has_dx and not has_meds:
                return False

        if tool_name in ("medication_reconciler", "drug_interaction_checker"):
            # Only run if we have at least some medications
            total_meds = len(kb.kb.medications_admission) + len(kb.kb.medications_discharge)
            if total_meds == 0:
                return False

        if tool_name == "escalation_manager":
            # Only run after all extraction and analysis tools have been attempted
            analysis_tools_done = all(
                state.has_completed(t) for t in ["conflict_detector", "drug_interaction_checker"]
            )
            return analysis_tools_done

        return True

    def get_skippable_tasks(self, state: AgentState, kb: KnowledgeRepository) -> List[AgentTask]:
        """Tasks that should be skipped because their preconditions can never be met."""
        skippable = []
        for task in state.pending_tasks:
            if task.tool_name == "lab_extractor" and "lab_report" not in state.available_document_types:
                skippable.append(task)
            if task.tool_name in ("medication_reconciler", "drug_interaction_checker"):
                if (not kb.kb.medications_admission and not kb.kb.medications_discharge
                        and state.has_completed("medication_extractor")):
                    skippable.append(task)
        return skippable
