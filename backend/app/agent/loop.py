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

from anthropic import AsyncAnthropic
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

    def __init__(self, client: AsyncAnthropic, settings: Settings) -> None:
        self.client = client
        self.settings = settings

        registry = ToolRegistry(client, settings)

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

        # ── Step 3: Generate initial plan ───────────────────────────────────────
        initial_tasks = self.planner.generate_initial_plan(state, kb)
        state.pending_tasks = initial_tasks

        plan_summary = " → ".join(t.name for t in initial_tasks)
        self.tracer.record_planning_step(
            reasoning=f"Generated {len(initial_tasks)}-step plan for {len(processed_docs)} documents",
            plan_summary=plan_summary,
            iteration=0,
        )
        logger.info("Initial plan", steps=len(initial_tasks), plan=plan_summary)

        # ── Step 4: Main loop ───────────────────────────────────────────────────
        while not self.terminator.should_stop(state, kb):
            # Skip tasks that can never run
            skippable = self.selector.get_skippable_tasks(state, kb)
            for skip_task in skippable:
                skip_task.status = skip_task.status.__class__("skipped")  # type: ignore
                state.pending_tasks = [t for t in state.pending_tasks if t.task_id != skip_task.task_id]
                state.skipped_tasks.append(skip_task)
                logger.info("Task skipped (precondition unmet)", tool=skip_task.tool_name)

            # Select next task
            task = self.selector.select_next(state, kb)
            if task is None:
                logger.info("No ready tasks — terminating loop")
                break

            # Execute
            self.tracer.start_step(task.task_id)
            result = await self.executor.execute(task, state, kb, db)

            # Evaluate
            should_replan, reasoning, next_action = self.decision_engine.evaluate(
                state, task, result, kb
            )

            # Record trace
            self.tracer.record_step(state, task, result, reasoning, next_action)

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
                    self.tracer.record_replan_step(
                        trigger=task.tool_name,
                        new_task_names=[t.name for t in new_tasks],
                        reasoning=reasoning,
                    )

            state.iteration_count += 1

        # ── Step 5: Finalise ────────────────────────────────────────────────────
        state.completed_at = datetime.utcnow()
        state.status = self.terminator.compute_final_status(state, kb)

        missing = kb.get_missing_critical_fields()
        state.missing_information = list(set(state.missing_information + missing))

        self.tracer.record_termination(
            reason=state.termination_reason or "Loop finished",
            state=state,
        )

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
