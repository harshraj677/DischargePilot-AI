from __future__ import annotations

"""
AgentLoop — the orchestration heart of DischargePilot AI.

Execution sequence per iteration:
  1. ToolSelector  → pick the highest-priority ready task
  2. ExecutionEngine → run the tool with retry + timeout
  3. DecisionEngine  → evaluate findings, produce reasoning + next_action
  4. TraceGenerator  → record the immutable TraceStep
  5. StateManager    → update AgentState (handled inline via AgentState methods)
  6. AgentPlanner    → replan if findings require it
  7. TerminationController → check all stop conditions

The loop never raises. All errors are captured into ToolResult and the trace.
"""

import time
from datetime import datetime
from typing import List, Optional

from app.groq_provider.agent_client import GroqAgentClient
from sqlalchemy.orm import Session

from app.agent.decision_engine import DecisionEngine
from app.agent.executor import ExecutionEngine
from app.agent.memory import MemoryManager
from app.agent.models import AgentRunResult, AgentRunStatus, AgentState, AgentTask, TraceStep
from app.agent.planner import AgentPlanner
from app.agent.terminator import TerminationController
from app.agent.tool_registry import ToolRegistry
from app.agent.tool_selector import ToolSelector
from app.agent.tracer import TraceGenerator
from app.config import Settings
from app.db.repositories.document_repo import DocumentRepository
from app.knowledge.repository import KnowledgeRepository
from app.models.enums import DocumentStatus
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AgentLoop:
    """
    Production-grade agentic loop for clinical discharge summary preparation.

    Architecture:
    ┌──────────────────────────────────────────────────────────────┐
    │  Goal (patient_id + run_id)                                  │
    │     ↓                                                        │
    │  AgentPlanner   → generates initial task plan                │
    │     ↓                                                        │
    │  ToolSelector   → picks highest-priority ready task          │
    │     ↓                                                        │
    │  ExecutionEngine → runs tool (retry + timeout)               │
    │     ↓                                                        │
    │  DecisionEngine → evaluates findings + produces reasoning    │
    │     ↓                                                        │
    │  TraceGenerator → records immutable TraceStep                │
    │     ↓                                                        │
    │  AgentPlanner   → replans if needed                          │
    │     ↓                                                        │
    │  TerminationController → checks all stop conditions          │
    └──────────────────────────────────────────────────────────────┘
    """

    def __init__(self, client: GroqAgentClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

        registry = ToolRegistry(client, settings)
        logger.info("Tool registry initialized")

        self.planner = AgentPlanner(client, settings)
        self.selector = ToolSelector()
        self.executor = ExecutionEngine(registry)
        self.decision_engine = DecisionEngine()
        self.terminator = TerminationController(max_iterations=settings.AGENT_MAX_ITERATIONS)
        self.tracer = TraceGenerator()
        self.memory = MemoryManager()

    async def run(
        self,
        patient_id: str,
        run_id: str,
        db: Session,
    ) -> AgentRunResult:
        """
        Execute the full agent loop for a patient.

        Steps:
        1. Load processed documents for the patient
        2. Build initial AgentState
        3. Generate initial plan
        4. Iterative tool execution loop
        5. Return AgentRunResult with KB + full trace

        Returns AgentRunResult regardless of success/failure.
        """
        loop_start = time.time()
        logger.info("Agent loop starting", patient_id=patient_id, run_id=run_id)

        # ── Step 1: Load documents ──────────────────────────────────────────────
        doc_repo = DocumentRepository(db)
        all_docs = doc_repo.list_for_patient(patient_id)
        processed_docs = [d for d in all_docs if d.status == DocumentStatus.PROCESSED.value]

        if not processed_docs:
            logger.warning("No processed documents found", patient_id=patient_id)
            return self._error_result(
                run_id=run_id,
                patient_id=patient_id,
                error="No processed documents available for this patient",
                duration_ms=(time.time() - loop_start) * 1000,
            )

        doc_ids = [d.id for d in processed_docs]
        doc_types = list({d.document_type for d in processed_docs})

        logger.info(
            "Documents loaded",
            count=len(processed_docs),
            types=doc_types,
            patient_id=patient_id,
        )

        # ── Step 2: Initialise state and knowledge base ─────────────────────────
        state = AgentState(
            run_id=run_id,
            patient_id=patient_id,
            available_document_ids=doc_ids,
            available_document_types=doc_types,
            started_at=datetime.utcnow(),
        )
        kb = KnowledgeRepository(patient_id)
        for doc_id in doc_ids:
            kb.add_source_document(doc_id)
        logger.info("Knowledge base initialized")

        # ── Step 3: Generate initial plan ───────────────────────────────────────
        initial_tasks = self.planner.generate_initial_plan(state, kb)
        state.pending_tasks = initial_tasks

        plan_summary = " → ".join(t.name for t in initial_tasks)
        plan_step = self.tracer.record_planning_step(
            reasoning=f"Generated {len(initial_tasks)}-step plan for {len(processed_docs)} documents",
            plan_summary=plan_summary,
            iteration=0,
        )
        self._save_db_trace_step(db, run_id, plan_step)
        logger.info("Initial plan", steps=len(initial_tasks), plan=plan_summary)

        # ── Step 4: Main loop ───────────────────────────────────────────────────
        while not self.terminator.should_stop(state, kb):
            current_iteration = state.iteration_count + 1
            logger.info(f"Starting iteration {current_iteration}")

            # Safety net (requirement: MAX_ITERATIONS guard): if we're about
            # to exhaust the iteration cap and summary_generator still
            # hasn't run, force it (and the terminator check right after)
            # instead of silently falling into TIMED_OUT. This is the path
            # that protects against any dependency that stalls forever —
            # e.g. a tool that keeps failing without ever being skippable.
            if current_iteration >= self.terminator.max_iterations and not state.has_completed("summary_generator"):
                logger.error(
                    "TIMEOUT GUARD: max iterations reached before natural completion — "
                    "forcing summary_generator + terminator instead of timing out",
                    iteration=current_iteration,
                    max_iterations=self.terminator.max_iterations,
                    pending_tasks=[t.tool_name for t in state.pending_tasks],
                    completed_tasks=[t.tool_name for t in state.completed_tasks],
                )
                await self._force_finalize(state, kb, db, run_id)
                break

            # Skip tasks that can never run
            skippable = self.selector.get_skippable_tasks(state, kb)
            for skip_task in skippable:
                skip_task.status = skip_task.status.__class__("skipped")  # type: ignore
                state.pending_tasks = [t for t in state.pending_tasks if t.task_id != skip_task.task_id]
                state.skipped_tasks.append(skip_task)
                logger.info("Task skipped (precondition unmet)", tool=skip_task.tool_name)

            # Select next task
            task = self.selector.select_next(state, kb)

            pending_names = [t.tool_name for t in state.pending_tasks]
            completed_names = [t.tool_name for t in state.completed_tasks]
            next_name = task.tool_name if task else None
            print(
                f"[Iteration {current_iteration}] "
                f"Pending: {pending_names} | Completed: {completed_names} | Next: {next_name}"
            )
            logger.info(
                "Loop iteration state",
                iteration=current_iteration,
                pending_tasks=pending_names,
                completed_tasks=completed_names,
                next_task=next_name,
            )

            if task is None:
                if not state.has_completed("summary_generator"):
                    # No ready task, but the pipeline goal hasn't been
                    # reached — typically a stuck dependency (e.g. a tool
                    # that permanently failed, so summary_generator's
                    # is_task_ready() never becomes true). Force the
                    # summary instead of silently ending the run without
                    # one — this is the same safety net as the iteration
                    # -cap guard above, just reached a different way.
                    logger.warning(
                        "No ready tasks but summary_generator hasn't run — forcing it",
                        iteration=current_iteration,
                        pending_tasks=pending_names,
                        completed_tasks=completed_names,
                        failed_tasks=[t.tool_name for t in state.failed_tasks],
                    )
                    await self._force_finalize(state, kb, db, run_id)
                else:
                    logger.info("No ready tasks — terminating loop")
                break

            # Execute
            self.tracer.start_step(task.task_id)
            result = await self.executor.execute(task, state, kb, db)

            # Evaluate
            should_replan, reasoning, next_action = self.decision_engine.evaluate(
                state, task, result, kb
            )

            # Requirement: verify completed tools are actually removed from
            # pending_tasks — mark_task_completed already does this, but
            # assert it here as well so a regression is caught immediately
            # instead of silently re-selecting a "completed" task forever.
            if result.success and any(t.task_id == task.task_id for t in state.pending_tasks):
                logger.error(
                    "Invariant violated: completed task still in pending_tasks — removing",
                    tool=task.tool_name,
                    task_id=task.task_id,
                )
                state.pending_tasks = [t for t in state.pending_tasks if t.task_id != task.task_id]

            # Record trace
            step = self.tracer.record_step(state, task, result, reasoning, next_action)
            self._save_db_trace_step(db, run_id, step)

            # Memory
            self.memory.record_tool_result(
                tool_name=task.tool_name,
                success=result.success,
                summary=result.trace_notes,
                findings=result.findings,
            )

            # Replan if needed
            if should_replan:
                new_tasks = await self.planner.replan(
                    state=state,
                    kb=kb,
                    last_tool=task.tool_name,
                    findings=result.findings,
                    memory_context=self.memory.get_prompt_context(),
                )
                if new_tasks:
                    state.pending_tasks.extend(new_tasks)
                    replan_step = self.tracer.record_replan_step(
                        trigger=task.tool_name,
                        new_task_names=[t.name for t in new_tasks],
                        reasoning=reasoning,
                    )
                    self._save_db_trace_step(db, run_id, replan_step)

            state.iteration_count += 1

        # ── Step 5: Finalise ────────────────────────────────────────────────────
        state.completed_at = datetime.utcnow()
        state.status = self.terminator.compute_final_status(state, kb)

        missing = kb.get_missing_critical_fields()
        state.missing_information = list(set(state.missing_information + missing))

        term_step = self.tracer.record_termination(
            reason=state.termination_reason or "Loop finished",
            state=state,
        )
        self._save_db_trace_step(db, run_id, term_step)

        completeness = kb.completeness_score()
        memory_snapshot = self.memory.persist_snapshot(kb.kb)
        duration_ms = (time.time() - loop_start) * 1000

        logger.info(
            "Agent loop complete",
            patient_id=patient_id,
            status=state.status.value,
            iterations=state.iteration_count,
            completeness=f"{completeness:.0%}",
            duration_ms=round(duration_ms),
            total_tokens=sum(state.token_usage.values()),
        )

        return AgentRunResult(
            run_id=run_id,
            patient_id=patient_id,
            status=state.status,
            knowledge_base=kb.kb,
            trace=self.tracer.get_trace(),
            final_state=state,
            completeness_score=completeness,
            escalation_required=state.escalation_required,
            escalation_reasons=state.escalation_reasons,
            token_usage=state.token_usage,
            duration_ms=duration_ms,
        )

    async def _force_finalize(
        self,
        state: AgentState,
        kb: KnowledgeRepository,
        db: Session,
        run_id: str,
    ) -> None:
        """
        MAX_ITERATIONS safety net: force summary_generator to run right now,
        bypassing the normal selector/dependency-readiness check, so the run
        ends with a usable summary instead of silently timing out. The
        terminator's "summary_generator completed" condition then takes
        over on the next should_stop() check, ending the run as COMPLETED
        rather than TIMED_OUT.
        """
        if state.has_completed("summary_generator"):
            return

        task = next((t for t in state.pending_tasks if t.tool_name == "summary_generator"), None)
        if task is None:
            task = AgentTask(
                name="Generate Discharge Summary (forced — iteration cap reached)",
                tool_name="summary_generator",
                priority=11,
                document_ids=state.available_document_ids,
            )
            state.pending_tasks.append(task)

        self.tracer.start_step(task.task_id)
        result = await self.executor.execute(task, state, kb, db)
        _, reasoning, next_action = self.decision_engine.evaluate(state, task, result, kb)
        step = self.tracer.record_step(state, task, result, reasoning, next_action)
        self._save_db_trace_step(db, run_id, step)
        state.iteration_count += 1

        logger.info(
            "Forced summary_generator execution complete",
            success=result.success,
            iteration=state.iteration_count,
        )

    def _error_result(
        self,
        run_id: str,
        patient_id: str,
        error: str,
        duration_ms: float,
    ) -> AgentRunResult:
        from app.knowledge.models import PatientKnowledgeBase

        failed_state = AgentState(
            run_id=run_id,
            patient_id=patient_id,
            status=AgentRunStatus.FAILED,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        return AgentRunResult(
            run_id=run_id,
            patient_id=patient_id,
            status=AgentRunStatus.FAILED,
            knowledge_base=PatientKnowledgeBase(patient_id=patient_id),
            trace=[],
            final_state=failed_state,
            completeness_score=0.0,
            escalation_required=False,
            escalation_reasons=[],
            token_usage={"input": 0, "output": 0},
            duration_ms=duration_ms,
            error=error,
        )

    def _save_db_trace_step(self, db: Session, run_id: str, step: TraceStep) -> None:
        try:
            import json
            from app.db.models import TraceStep as DBTraceStep
            db_step = DBTraceStep(
                run_id=run_id,
                step=step.step,
                component=step.selected_tool,
                input=json.dumps(step.tool_input),
                output=json.dumps(step.tool_output) if step.tool_output is not None else None,
                duration=step.duration_ms,
                error=step.error,
            )
            db.add(db_step)
            db.commit()
        except Exception as exc:
            logger.error("Failed to save DB trace step", error=str(exc))
