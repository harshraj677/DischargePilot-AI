from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.groq_provider.agent_client import GroqAgentClient, GroqUnavailableError

from app.agent.models import AgentState, AgentTask, MAX_REPLAN_ATTEMPTS
from app.agent.prompts import AGENT_SYSTEM_PROMPT, REPLANNING_PROMPT
from app.agent.tool_registry import known_tool_names
from app.config import Settings
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AgentPlanner:
    """
    Hybrid planner:
    - Initial plan is generated deterministically from available document types
    - Replanning uses Groq when new findings require plan adjustments
    """

    def __init__(self, client: GroqAgentClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        logger.info("Planner initialized")


    # ── Initial plan ─────────────────────────────────────────────────────────────

    def generate_initial_plan(
        self, state: AgentState, kb: KnowledgeRepository
    ) -> List[AgentTask]:
        """
        Rule-based initial plan.

        Order: extraction tools first (1-6), then analysis tools (7-10).
        Lab extractor is only added if lab documents are present.
        Analysis tools declare dependencies on extraction tools.
        """
        doc_types = set(state.available_document_types)
        doc_ids = state.available_document_ids

        tasks: List[AgentTask] = []

        dx_task = self._make_task("Extract Diagnoses", "diagnosis_extractor", 1, doc_ids)
        med_task = self._make_task("Extract Medications", "medication_extractor", 2, doc_ids)
        allergy_task = self._make_task("Extract Allergies", "allergy_extractor", 3, doc_ids)
        proc_task = self._make_task("Extract Procedures", "procedure_extractor", 4, doc_ids)
        pending_task = self._make_task("Identify Pending Results", "pending_result_extractor", 6, doc_ids)

        tasks.extend([dx_task, med_task, allergy_task, proc_task, pending_task])

        if "lab_report" in doc_types:
            lab_ids = [d for d in doc_ids]  # all docs — tool filters internally
            lab_task = self._make_task("Extract Lab Results", "lab_extractor", 5, lab_ids)
            tasks.append(lab_task)
        else:
            logger.info("No lab_report documents — skipping lab_extractor")

        # Analysis tools depend on extraction tasks
        extraction_ids = [dx_task.task_id, med_task.task_id, allergy_task.task_id]

        conflict_task = self._make_task(
            "Detect Clinical Conflicts", "conflict_detector", 7, [],
            depends_on=extraction_ids,
        )
        reconcile_task = self._make_task(
            "Reconcile Medications", "medication_reconciler", 8, [],
            depends_on=[med_task.task_id],
        )
        drug_ix_task = self._make_task(
            "Check Drug Interactions", "drug_interaction_checker", 9, [],
            depends_on=[med_task.task_id],
        )
        # escalation_manager depends only on conflict_detector +
        # medication_reconciler — deliberately NOT on drug_interaction_checker,
        # so a stuck/failed optional check can never block the
        # escalation -> summary critical path (same reasoning as below).
        escalation_task = self._make_task(
            "Evaluate Escalation", "escalation_manager", 10, [],
            depends_on=[conflict_task.task_id, reconcile_task.task_id],
        )

        # summary_generator depends on the core extraction + analysis
        # pipeline (diagnosis, medication, allergy, procedure, pending
        # results, conflict_detector, medication_reconciler) PLUS
        # escalation_manager — matching the required pipeline order
        # (Conflict Detector -> Medication Reconciler -> Escalation Manager
        # -> Summary Generator). Deliberately NOT on drug_interaction_checker,
        # so a stuck/failed optional check never blocks summary generation.
        # Without this task in the initial plan, summary_generator was never
        # scheduled at all (it isn't even mentioned in REPLANNING_PROMPT),
        # which is why runs completed extraction/analysis but never produced
        # a summary and never reached COMPLETED via the natural path.
        summary_task = self._make_task(
            "Generate Discharge Summary", "summary_generator", 11, [],
            depends_on=[
                dx_task.task_id,
                med_task.task_id,
                allergy_task.task_id,
                proc_task.task_id,
                pending_task.task_id,
                conflict_task.task_id,
                reconcile_task.task_id,
                escalation_task.task_id,
            ],
        )

        tasks.extend([conflict_task, reconcile_task, drug_ix_task, escalation_task, summary_task])

        logger.info(
            "Initial plan generated",
            task_count=len(tasks),
            doc_types=list(doc_types),
        )
        return tasks

    # ── Replanning ───────────────────────────────────────────────────────────────

    async def should_replan(
        self, state: AgentState, last_tool: str, findings: Dict[str, Any]
    ) -> bool:
        """
        Heuristic-based replan trigger — no Claude call needed.
        Returns True if the last tool's findings imply new tasks are required.
        """
        # Conflict found and conflict_detector not yet in pending or completed
        if findings.get("conflicts_detected", 0) > 0:
            if not state.has_completed("conflict_detector") and not any(
                t.tool_name == "conflict_detector" for t in state.pending_tasks
            ):
                return True

        # Critical labs found
        if findings.get("critical_count", 0) > 0:
            if not state.has_completed("escalation_manager") and not any(
                t.tool_name == "escalation_manager" for t in state.pending_tasks
            ):
                return True

        # High-risk medication changes
        if findings.get("high_risk_changes") and not state.has_completed("escalation_manager"):
            return True

        return False

    async def replan(
        self,
        state: AgentState,
        kb: KnowledgeRepository,
        last_tool: str,
        findings: Dict[str, Any],
        memory_context: str,
    ) -> List[AgentTask]:
        """Use Groq to determine what additional tasks are needed."""
        # Backstop against infinite replanning loops — decision_engine
        # already gates *when* replan() is called, but this is enforced
        # here too so no future caller can bypass the cap.
        state.replan_count += 1
        if state.replan_count > MAX_REPLAN_ATTEMPTS:
            logger.warning(
                "Max replan attempts exceeded — refusing further replanning",
                replan_count=state.replan_count,
                limit=MAX_REPLAN_ATTEMPTS,
                last_tool=last_tool,
            )
            return []

        completed_tools = [t.tool_name for t in state.completed_tasks]
        pending_task_names = [f"{t.name} ({t.tool_name})" for t in state.pending_tasks]

        prompt = REPLANNING_PROMPT.format(
            last_tool=last_tool,
            success=True,
            findings=json.dumps(findings, indent=2),
            trace_notes=findings.get("trace_notes", ""),
            completed_tools=", ".join(completed_tools),
            pending_tasks=", ".join(pending_task_names),
            conflicts=", ".join(state.identified_conflicts[:5]),
            missing_info=", ".join(state.missing_information[:5]),
            kb_summary=kb.to_agent_context(),
        )

        try:
            response_text = await self.client.generate_content(
                prompt=f"{AGENT_SYSTEM_PROMPT}\n\n{prompt}",
                model_type="text"
            )
            raw_text = response_text.strip()
            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                raw_text = "\n".join(raw_text.split("\n")[1:])
                raw_text = raw_text.rsplit("```", 1)[0]
            plan_data = json.loads(raw_text)
        except GroqUnavailableError as exc:
            logger.warning("Replanning Groq call unavailable, using heuristics", error=str(exc))
            reason = f"replanner: Groq unavailable, manual review required ({exc})"
            if reason not in state.escalation_reasons:
                state.escalation_reasons.append(reason)
            plan_data = {"needs_replan": False, "new_tasks": []}
        except Exception as exc:
            logger.warning("Replanning Groq call failed, using heuristics", error=str(exc))
            plan_data = {"needs_replan": False, "new_tasks": []}

        if not plan_data.get("needs_replan", False):
            return []

        valid_tools = known_tool_names()
        new_tasks: List[AgentTask] = []
        for t_raw in plan_data.get("new_tasks", []):
            tool_name = t_raw.get("tool_name", "")
            if not tool_name:
                continue
            if tool_name not in valid_tools:
                # Reject hallucinated/misspelled tool names outright — an
                # unknown tool_name would otherwise become a task that can
                # never succeed and (absent the executor fix) never leaves
                # pending_tasks, looping forever until the iteration cap.
                logger.warning("Replanner proposed unknown tool — rejected", tool_name=tool_name)
                continue
            # Centralized duplicate guard: skip if this tool already has a
            # task anywhere (pending/completed/failed) OR was already added
            # earlier in this same replan batch.
            if state.has_task(tool_name) or any(t.tool_name == tool_name for t in new_tasks):
                continue
            task = self._make_task(
                name=t_raw.get("name", tool_name),
                tool_name=tool_name,
                priority=int(t_raw.get("priority", 8)),
                doc_ids=state.available_document_ids,
            )
            new_tasks.append(task)

        if new_tasks:
            logger.info("Replan added new tasks", count=len(new_tasks), tools=[t.tool_name for t in new_tasks])

        return new_tasks

    # ── Helpers ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _make_task(
        name: str,
        tool_name: str,
        priority: int,
        doc_ids: List[str],
        depends_on: Optional[List[str]] = None,
    ) -> AgentTask:
        return AgentTask(
            name=name,
            tool_name=tool_name,
            priority=priority,
            document_ids=list(doc_ids),
            depends_on=depends_on or [],
            created_at=datetime.utcnow(),
        )
