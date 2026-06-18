from __future__ import annotations

from typing import Tuple

from app.agent.models import AgentState, AgentTask, MAX_REPLAN_ATTEMPTS, ToolResult
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _escalation_already_scheduled(state: AgentState) -> bool:
    return state.has_completed("escalation_manager") or any(
        t.tool_name == "escalation_manager" for t in state.pending_tasks
    )


def _replan_allowed(state: AgentState, trigger_tool: str) -> bool:
    """
    Guards against infinite replanning loops:
    - Never replan twice for the same trigger tool (each tool only runs
      once per run, so a second trigger would mean something upstream is
      already broken — don't make it worse by calling the LLM again).
    - Stop replanning once the run-wide cap is reached.
    """
    if trigger_tool in state.replanned_triggers:
        return False
    if len(state.replanned_triggers) >= MAX_REPLAN_ATTEMPTS:
        logger.warning(
            "Replan cap reached — refusing to trigger another replan",
            trigger_tool=trigger_tool,
            replanned_triggers=state.replanned_triggers,
        )
        return False
    return True


class DecisionEngine:
    """
    After each tool execution, the decision engine evaluates:
    1. Should the agent replan? (new findings changed the situation)
    2. Should the agent escalate immediately? (critical safety issue)
    3. What reasoning should be recorded in the trace?
    """

    def evaluate(
        self,
        state: AgentState,
        task: AgentTask,
        result: ToolResult,
        kb: KnowledgeRepository,
    ) -> Tuple[bool, str, str]:
        """
        Return (should_replan, reasoning, next_action).

        reasoning: text explaining why this decision was made
        next_action: description of what happens next
        """
        findings = result.findings

        # -- Immediate escalation check --
        if findings.get("escalation_required") or (
            findings.get("critical_conflicts", 0) > 0
            or findings.get("critical_interactions", 0) > 0
            or findings.get("critical_count", 0) > 0
        ):
            state.escalation_required = True
            reasoning = (
                f"{task.tool_name} detected critical safety issue. "
                f"Escalation flagged for clinician review. "
                f"Details: {result.trace_notes}"
            )
            next_action = "Flag for clinician review; continue plan to collect remaining data"
            return True, reasoning, next_action

        # -- Failure handling --
        if not result.success:
            reasoning = (
                f"{task.tool_name} failed: {result.error}. "
                f"Continuing with remaining tasks — partial knowledge base may result."
            )
            next_action = "Continue with next pending task"
            missing_field = _tool_to_missing_field(task.tool_name)
            if missing_field:
                kb.mark_missing(missing_field)
            return False, reasoning, next_action

        # -- Conflict detection triggered replan --
        if task.tool_name == "conflict_detector" and findings.get("conflicts_detected", 0) > 0:
            if _escalation_already_scheduled(state):
                # escalation_manager is already in the initial plan (or
                # done) — no need to call the LLM replanner at all. This is
                # the common case and the main thing that used to cause
                # repeated, unnecessary (and hallucination-prone) replan
                # calls on every conflict_detector run.
                pass
            elif _replan_allowed(state, task.tool_name):
                state.replanned_triggers.append(task.tool_name)
                reasoning = (
                    f"Conflict detection found {findings['conflicts_detected']} conflict(s). "
                    f"Safety assessment: {findings.get('safety_assessment', 'unknown')}. "
                    f"Replanning to ensure escalation_manager is in the plan."
                )
                next_action = "Replan to add escalation_manager if not already pending"
                return True, reasoning, next_action

        # -- High-risk medication changes --
        if task.tool_name == "medication_reconciler" and findings.get("high_risk_changes"):
            if _escalation_already_scheduled(state):
                pass
            elif _replan_allowed(state, task.tool_name):
                state.replanned_triggers.append(task.tool_name)
                reasoning = (
                    f"Medication reconciliation found high-risk changes: "
                    f"{', '.join(findings['high_risk_changes'][:3])}. "
                    f"Replanning to ensure escalation."
                )
                next_action = "Replan to add escalation_manager if not already pending"
                return True, reasoning, next_action

        # -- Normal success --
        facts = result.facts_extracted
        reasoning = (
            f"{task.tool_name} completed successfully. "
            f"{facts} fact(s) added to knowledge base. "
            f"{result.trace_notes}"
        )
        next_action = _determine_next_action(state, kb)
        return False, reasoning, next_action


def _tool_to_missing_field(tool_name: str) -> str:
    mapping = {
        "diagnosis_extractor": "diagnoses",
        "medication_extractor": "medications",
        "allergy_extractor": "allergy_status",
        "lab_extractor": "lab_results",
        "pending_result_extractor": "pending_results",
    }
    return mapping.get(tool_name, "")


def _determine_next_action(state: AgentState, kb: KnowledgeRepository) -> str:
    if not state.pending_tasks:
        return "All tasks complete — proceed to AgentRunResult"
    pending_names = [t.name for t in state.pending_tasks[:3]]
    return f"Continue with next pending task(s): {', '.join(pending_names)}"
