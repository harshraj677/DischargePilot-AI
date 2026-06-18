"""
End-to-end AgentLoop regression tests for the TIMED_OUT root-cause fix.

Root cause that used to cause every run to time out at iteration 15:
  1. summary_generator was never added to the initial plan (and isn't even
     mentioned in REPLANNING_PROMPT), so it could never be reached via the
     natural "no pending tasks" completion path.
  2. ExecutionEngine never marked an unknown-tool task as failed, so it
     stayed in pending_tasks forever and was reselected every iteration.
  3. The tool registry registered "medication_reconciler" under two
     different key strings, defeating the replanner's string-based
     duplicate-task guard.
  4. decision_engine triggered an LLM replan on every conflict_detector /
     medication_reconciler success, regardless of whether escalation_manager
     was already scheduled — wasteful and a vector for (3).

These tests run the real AgentLoop/AgentPlanner/ToolSelector/DecisionEngine/
TerminationController stack against a real (test) DB, with only the tool
*execution* mocked out (canned ToolResult per tool name) so no network call
is made and no LLM-specific parsing logic is exercised here (that's covered
elsewhere) — this isolates the orchestration logic that actually caused the
timeout.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.loop import AgentLoop
from app.agent.models import AgentRunStatus, AgentTask, ToolResult
from app.config import settings
from app.db.models import Document
from app.db.repositories.patient_repo import PatientRepository
from app.knowledge.models import Diagnosis, EvidencedFact, Medication
from app.models.patient import PatientCreate


def _fact(value: str) -> EvidencedFact:
    return EvidencedFact(
        value=value,
        confidence=0.9,
        source_document="admission.pdf",
        source_document_id="doc-1",
        page_number=1,
        evidence=value,
    )


@pytest.fixture
def patient(db):
    repo = PatientRepository(db)
    return repo.create(PatientCreate(mrn="MRN-LOOP-1", first_name="Loop", last_name="Test"))


@pytest.fixture
def processed_document(db, patient):
    doc = Document(
        patient_id=patient.id,
        document_type="admission_note",
        file_name="admission.pdf",
        file_path="/tmp/admission.pdf",
        status="PROCESSED",
    )
    db.add(doc)
    db.commit()
    return doc


def _ok(task: AgentTask, **findings) -> ToolResult:
    return ToolResult(
        task_id=task.task_id,
        tool_name=task.tool_name,
        success=True,
        facts_extracted=1,
        findings=findings,
        trace_notes="ok",
    )


def _fail(task: AgentTask, error: str = "boom") -> ToolResult:
    return ToolResult(task_id=task.task_id, tool_name=task.tool_name, success=False, error=error)


class _FakeTool:
    """Stands in for every real tool — execute() returns a canned result."""

    def __init__(self, behavior):
        self._behavior = behavior

    async def execute(self, task, state, kb, db):
        # Mirror real extractor behavior: diagnosis/medication extractors
        # populate the KB, which conflict_detector's precondition (it only
        # becomes selectable once diagnoses or medications exist) depends
        # on. Without this, conflict_detector/summary_generator would never
        # become ready in this test for reasons unrelated to the loop logic
        # under test.
        if task.tool_name == "diagnosis_extractor":
            kb.add_fact("diagnosis", Diagnosis(name=_fact("Type 2 Diabetes Mellitus"), is_principal=True))
        if task.tool_name == "medication_extractor":
            kb.add_fact("medication_discharge", Medication(name=_fact("Metformin 500mg"), is_admission=False))
        return self._behavior(task)


@pytest.fixture(autouse=True)
def _fast_replan(monkeypatch):
    # Tools below never set should_replan in a way that needs a real LLM
    # call, but guard against any accidental real network call regardless.
    from app.agent.planner import AgentPlanner
    monkeypatch.setattr(AgentPlanner, "replan", AsyncMock(return_value=[]))


def _make_loop() -> AgentLoop:
    client = AsyncMock()
    return AgentLoop(client=client, settings=settings)


class TestAgentLoopReachesCompleted:
    @pytest.mark.asyncio
    async def test_happy_path_runs_summary_generator_and_completes(self, db, patient, processed_document):
        """
        All 10 tools succeed, including conflict_detector reporting a
        conflict and medication_reconciler reporting a high-risk change —
        the exact findings that used to trigger an unconditional replan on
        every run. With escalation_manager already in the initial plan,
        no replan should be needed, and the run must reach COMPLETED with
        summary_generator executed, far under the iteration cap.
        """
        loop = _make_loop()

        def behavior(task: AgentTask) -> ToolResult:
            if task.tool_name == "conflict_detector":
                return _ok(task, conflicts_detected=2, critical_conflicts=0)
            if task.tool_name == "medication_reconciler":
                return _ok(task, high_risk_changes=["warfarin dose increased"])
            return _ok(task)

        fake = _FakeTool(behavior)
        with patch("app.agent.tool_registry.ToolRegistry.get", return_value=fake):
            result = await loop.run(patient_id=patient.id, run_id="run-happy", db=db)

        assert result.status == AgentRunStatus.COMPLETED
        assert result.error is None
        completed_tools = {t.tool_name for t in result.final_state.completed_tasks}
        assert "summary_generator" in completed_tools
        for required in (
            "diagnosis_extractor", "medication_extractor", "allergy_extractor",
            "procedure_extractor", "pending_result_extractor",
            "conflict_detector", "medication_reconciler",
        ):
            assert required in completed_tools

        # The old unconditional-replan bug would have called replan() at
        # least twice (conflict_detector + medication_reconciler) even
        # though escalation_manager was already scheduled.
        assert result.final_state.replan_count == 0
        assert result.final_state.iteration_count < settings.AGENT_MAX_ITERATIONS

    @pytest.mark.asyncio
    async def test_unknown_tool_task_does_not_loop_forever(self, db, patient, processed_document):
        """
        Directly reproduces the original bug: a task with a tool_name not
        in the registry must be marked failed and removed from
        pending_tasks on the first attempt — not reselected every
        iteration until the run times out.
        """
        loop = _make_loop()

        def behavior(task: AgentTask) -> ToolResult:
            return _ok(task)

        fake = _FakeTool(behavior)
        real_get = type(loop.executor.registry).get

        def get_with_one_bogus_tool(self, tool_name):
            if tool_name == "diagnosis_extractor":
                return None  # simulate an unregistered/hallucinated tool name
            return fake

        with patch("app.agent.tool_registry.ToolRegistry.get", get_with_one_bogus_tool):
            result = await loop.run(patient_id=patient.id, run_id="run-bogus", db=db)

        failed_tools = {t.tool_name for t in result.final_state.failed_tasks}
        assert "diagnosis_extractor" in failed_tools
        # Must not still be sitting in pending_tasks after the first attempt
        assert not any(t.tool_name == "diagnosis_extractor" for t in result.final_state.pending_tasks)
        # And the run must still reach a terminal state well under the cap,
        # not silently consume all iterations reselecting the bogus task.
        assert result.final_state.iteration_count < settings.AGENT_MAX_ITERATIONS

    @pytest.mark.asyncio
    async def test_stuck_dependency_forces_summary_instead_of_timing_out(self, db, patient, processed_document):
        """
        pending_result_extractor fails on every attempt (e.g. a persistently
        broken extractor) — summary_generator depends on it, so under the
        normal dependency graph summary_generator would never become ready
        and the run would previously have burned every iteration before
        hitting TIMED_OUT. The MAX_ITERATIONS force-finalize guard must
        force summary_generator to run anyway and end the run COMPLETED.
        """
        loop = _make_loop()

        def behavior(task: AgentTask) -> ToolResult:
            if task.tool_name == "pending_result_extractor":
                return _fail(task, "persistent extractor failure")
            return _ok(task)

        fake = _FakeTool(behavior)
        with patch("app.agent.tool_registry.ToolRegistry.get", return_value=fake):
            result = await loop.run(patient_id=patient.id, run_id="run-stuck", db=db)

        assert result.status == AgentRunStatus.COMPLETED
        completed_tools = {t.tool_name for t in result.final_state.completed_tasks}
        assert "summary_generator" in completed_tools
        assert "pending_result_extractor" in {t.tool_name for t in result.final_state.failed_tasks}
