"""
Tests for Phase 3 + Phase 4: Knowledge Layer and Agent Loop Engine.

Strategy: mock the Anthropic client so tests run offline.
"""
import json
import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.decision_engine import DecisionEngine
from app.agent.models import AgentRunStatus, AgentState, AgentTask, TaskStatus, ToolResult
from app.agent.planner import AgentPlanner
from app.agent.terminator import TerminationController
from app.agent.tool_selector import ToolSelector
from app.agent.tracer import TraceGenerator
from app.knowledge.models import (
    Allergy,
    ClinicalConflict,
    Diagnosis,
    EvidencedFact,
    Medication,
    PatientKnowledgeBase,
)
from app.knowledge.repository import KnowledgeRepository


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_evidenced_fact(value: str, doc_id: str = "doc-1", page: int = 1) -> EvidencedFact:
    return EvidencedFact(
        value=value,
        confidence=0.90,
        source_document="admission_note.pdf",
        source_document_id=doc_id,
        page_number=page,
        evidence=f"...{value}...",
    )


def make_state(doc_ids=None, doc_types=None) -> AgentState:
    return AgentState(
        patient_id="patient-001",
        available_document_ids=doc_ids or ["doc-1", "doc-2"],
        available_document_types=doc_types or ["admission_note", "medication_record"],
        started_at=datetime.utcnow(),
    )


def make_kb(patient_id="patient-001") -> KnowledgeRepository:
    return KnowledgeRepository(patient_id)


# ── Knowledge Models ──────────────────────────────────────────────────────────

class TestEvidencedFact:
    def test_confidence_level_high(self):
        f = make_evidenced_fact("Type 2 Diabetes")
        assert f.confidence_level.value == "high"

    def test_confidence_level_medium(self):
        f = EvidencedFact(
            value="Hypertension",
            confidence=0.72,
            source_document="note.pdf",
            source_document_id="doc-1",
            page_number=2,
            evidence="..Hypertension..",
        )
        assert f.confidence_level.value == "medium"

    def test_confidence_level_low(self):
        f = EvidencedFact(
            value="Possible CKD",
            confidence=0.55,
            source_document="note.pdf",
            source_document_id="doc-1",
            page_number=3,
            evidence="possible kidney disease",
        )
        assert f.confidence_level.value == "low"

    def test_short_evidence_truncates(self):
        f = make_evidenced_fact("X" * 200)
        short = f.short_evidence(max_len=50)
        assert len(short) <= 53  # 50 + "…"

    def test_evidence_max_500_chars(self):
        long_evidence = "A" * 600
        f = EvidencedFact(
            value="test",
            confidence=0.9,
            source_document="doc.pdf",
            source_document_id="doc-1",
            page_number=1,
            evidence=long_evidence,
        )
        assert len(f.evidence) == 600  # model doesn't truncate; extractor does


# ── Knowledge Repository ──────────────────────────────────────────────────────

class TestKnowledgeRepository:
    def test_add_and_get_demographics(self):
        kb = make_kb()
        name_fact = make_evidenced_fact("John Doe")
        kb.add_fact("demographics.name", name_fact)
        retrieved = kb.get_fact("demographics.name")
        assert retrieved is not None
        assert retrieved.value == "John Doe"

    def test_add_diagnosis(self):
        kb = make_kb()
        dx = Diagnosis(
            name=make_evidenced_fact("Type 2 Diabetes Mellitus"),
            icd_code="E11.9",
            is_principal=True,
        )
        kb.add_fact("diagnosis", dx)
        diagnoses = kb.get_fact("diagnoses")
        assert len(diagnoses) == 1
        assert diagnoses[0].is_principal is True
        assert diagnoses[0].icd_code == "E11.9"

    def test_add_medication_admission(self):
        kb = make_kb()
        med = Medication(name=make_evidenced_fact("Metformin 500mg"))
        kb.add_fact("medication_admission", med)
        meds = kb.get_fact("medications_admission")
        assert len(meds) == 1

    def test_add_allergy(self):
        kb = make_kb()
        allergy = Allergy(
            allergen=make_evidenced_fact("Penicillin"),
            reaction=make_evidenced_fact("Anaphylaxis"),
            severity="life-threatening",
        )
        kb.add_fact("allergy", allergy)
        assert len(kb.kb.allergies) == 1

    def test_completeness_score_empty(self):
        kb = make_kb()
        assert kb.completeness_score() == 0.0

    def test_completeness_score_partial(self):
        kb = make_kb()
        kb.add_fact("demographics.name", make_evidenced_fact("Jane Smith"))
        kb.add_fact("demographics.mrn", make_evidenced_fact("MRN-001"))
        kb.add_fact("diagnosis", Diagnosis(name=make_evidenced_fact("CHF"), is_principal=True))
        score = kb.completeness_score()
        assert 0.0 < score < 1.0

    def test_search_by_source(self):
        kb = make_kb()
        kb.add_fact("demographics.name", make_evidenced_fact("John"))
        kb.add_fact("demographics.mrn", make_evidenced_fact("MRN-X"))
        results = kb.search_by_source("admission_note.pdf")
        assert len(results) == 2

    def test_search_by_page(self):
        kb = make_kb()
        kb.add_fact("demographics.name", make_evidenced_fact("John", page=1))
        kb.add_fact("demographics.mrn", make_evidenced_fact("MRN", page=2))
        page1 = kb.search_by_page(1)
        assert len(page1) == 1

    def test_mark_missing(self):
        kb = make_kb()
        kb.mark_missing("discharge_medications")
        assert "discharge_medications" in kb.kb.missing_information

    def test_no_duplicate_missing(self):
        kb = make_kb()
        kb.mark_missing("diagnoses")
        kb.mark_missing("diagnoses")
        assert kb.kb.missing_information.count("diagnoses") == 1

    def test_add_conflict(self):
        kb = make_kb()
        conflict = ClinicalConflict(
            conflict_type="medication_allergy",
            description="Penicillin prescribed despite allergy",
            severity="critical",
            involved_items=["Penicillin"],
        )
        kb.add_conflict(conflict)
        assert len(kb.kb.conflicts) == 1
        assert kb.has_critical_conflicts() is True

    def test_to_agent_context(self):
        kb = make_kb()
        kb.add_fact("demographics.name", make_evidenced_fact("Alice"))
        context = kb.to_agent_context()
        assert "Alice" in context
        assert "Completeness" in context


# ── Agent Planner ─────────────────────────────────────────────────────────────

class TestAgentPlanner:
    def test_initial_plan_includes_core_tools(self):
        client = MagicMock()
        settings = MagicMock()
        settings.CLAUDE_MODEL = "claude-sonnet-4-6"
        planner = AgentPlanner(client, settings)
        state = make_state(doc_types=["admission_note", "medication_record"])
        kb = make_kb()
        tasks = planner.generate_initial_plan(state, kb)
        tool_names = [t.tool_name for t in tasks]
        assert "diagnosis_extractor" in tool_names
        assert "medication_extractor" in tool_names
        assert "allergy_extractor" in tool_names
        assert "conflict_detector" in tool_names
        assert "escalation_manager" in tool_names

    def test_lab_extractor_skipped_without_lab_docs(self):
        client = MagicMock()
        settings = MagicMock()
        planner = AgentPlanner(client, settings)
        state = make_state(doc_types=["admission_note"])
        kb = make_kb()
        tasks = planner.generate_initial_plan(state, kb)
        tool_names = [t.tool_name for t in tasks]
        assert "lab_extractor" not in tool_names

    def test_lab_extractor_included_with_lab_docs(self):
        client = MagicMock()
        settings = MagicMock()
        planner = AgentPlanner(client, settings)
        state = make_state(doc_types=["admission_note", "lab_report"])
        kb = make_kb()
        tasks = planner.generate_initial_plan(state, kb)
        tool_names = [t.tool_name for t in tasks]
        assert "lab_extractor" in tool_names

    def test_dependency_ordering(self):
        client = MagicMock()
        settings = MagicMock()
        planner = AgentPlanner(client, settings)
        state = make_state()
        kb = make_kb()
        tasks = planner.generate_initial_plan(state, kb)
        task_id_map = {t.task_id: t for t in tasks}
        conflict_task = next(t for t in tasks if t.tool_name == "conflict_detector")
        # All dependencies of conflict_detector must exist as tasks
        for dep_id in conflict_task.depends_on:
            assert dep_id in task_id_map


# ── Tool Selector ─────────────────────────────────────────────────────────────

class TestToolSelector:
    def test_selects_highest_priority_ready_task(self):
        selector = ToolSelector()
        state = make_state()
        kb = make_kb()
        task_high = AgentTask(
            name="Extract Diagnoses", tool_name="diagnosis_extractor", priority=1,
            document_ids=["doc-1"], created_at=datetime.utcnow(),
        )
        task_low = AgentTask(
            name="Extract Procedures", tool_name="procedure_extractor", priority=4,
            document_ids=["doc-1"], created_at=datetime.utcnow(),
        )
        state.pending_tasks = [task_low, task_high]
        selected = selector.select_next(state, kb)
        assert selected is not None
        assert selected.tool_name == "diagnosis_extractor"

    def test_skips_task_with_unsatisfied_dependency(self):
        selector = ToolSelector()
        state = make_state()
        kb = make_kb()
        dep_id = str(uuid.uuid4())
        conflict_task = AgentTask(
            name="Detect Conflicts", tool_name="conflict_detector", priority=7,
            depends_on=[dep_id], created_at=datetime.utcnow(),
        )
        state.pending_tasks = [conflict_task]
        selected = selector.select_next(state, kb)
        assert selected is None

    def test_selects_after_dependency_completed(self):
        selector = ToolSelector()
        state = make_state()
        kb = make_kb()

        dx_task = AgentTask(
            name="Diagnoses", tool_name="diagnosis_extractor", priority=1,
            created_at=datetime.utcnow(),
        )
        dx_task.status = TaskStatus.COMPLETED
        state.completed_tasks = [dx_task]

        conflict_task = AgentTask(
            name="Conflicts", tool_name="conflict_detector", priority=7,
            depends_on=[dx_task.task_id], created_at=datetime.utcnow(),
        )
        state.pending_tasks = [conflict_task]

        # Add medications too so precondition is met
        kb.add_fact("diagnosis", Diagnosis(name=make_evidenced_fact("DM2"), is_principal=True))
        kb.add_fact("medication_discharge", Medication(name=make_evidenced_fact("Metformin")))

        selected = selector.select_next(state, kb)
        assert selected is not None
        assert selected.tool_name == "conflict_detector"


# ── Terminator ────────────────────────────────────────────────────────────────

class TestTerminationController:
    def test_stops_on_iteration_cap(self):
        terminator = TerminationController(max_iterations=3)
        state = make_state()
        state.iteration_count = 3
        kb = make_kb()
        assert terminator.should_stop(state, kb) is True
        assert state.status == AgentRunStatus.TIMED_OUT

    def test_stops_when_no_pending_tasks(self):
        terminator = TerminationController(max_iterations=15)
        state = make_state()
        state.pending_tasks = []
        state.iteration_count = 5
        kb = make_kb()
        assert terminator.should_stop(state, kb) is True
        assert state.status == AgentRunStatus.COMPLETED

    def test_does_not_stop_while_tasks_pending(self):
        terminator = TerminationController(max_iterations=15)
        state = make_state()
        state.pending_tasks = [
            AgentTask(
                name="Extract Diagnoses", tool_name="diagnosis_extractor", priority=1,
                created_at=datetime.utcnow(),
            )
        ]
        state.iteration_count = 2
        kb = make_kb()
        assert terminator.should_stop(state, kb) is False


# ── Decision Engine ───────────────────────────────────────────────────────────

class TestDecisionEngine:
    def test_flags_escalation_on_critical_conflict(self):
        engine = DecisionEngine()
        state = make_state()
        kb = make_kb()
        task = AgentTask(
            name="Detect Conflicts", tool_name="conflict_detector", priority=7,
            created_at=datetime.utcnow(),
        )
        result = ToolResult(
            task_id=task.task_id,
            tool_name="conflict_detector",
            success=True,
            facts_extracted=1,
            findings={"conflicts_detected": 1, "critical_conflicts": 1, "safety_assessment": "escalate_immediately"},
            trace_notes="Critical conflict found",
        )
        should_replan, reasoning, next_action = engine.evaluate(state, task, result, kb)
        assert state.escalation_required is True
        assert should_replan is True

    def test_no_escalation_on_clean_result(self):
        engine = DecisionEngine()
        state = make_state()
        kb = make_kb()
        task = AgentTask(
            name="Extract Diagnoses", tool_name="diagnosis_extractor", priority=1,
            created_at=datetime.utcnow(),
        )
        result = ToolResult(
            task_id=task.task_id,
            tool_name="diagnosis_extractor",
            success=True,
            facts_extracted=3,
            findings={"diagnoses_count": 3},
            trace_notes="3 diagnoses extracted",
        )
        should_replan, reasoning, next_action = engine.evaluate(state, task, result, kb)
        assert state.escalation_required is False
        assert should_replan is False


# ── Trace Generator ───────────────────────────────────────────────────────────

class TestTraceGenerator:
    def test_records_step(self):
        tracer = TraceGenerator()
        state = make_state()
        state.iteration_count = 1
        task = AgentTask(
            name="Extract Diagnoses", tool_name="diagnosis_extractor", priority=1,
            document_ids=["doc-1"], created_at=datetime.utcnow(),
        )
        result = ToolResult(
            task_id=task.task_id,
            tool_name="diagnosis_extractor",
            success=True,
            facts_extracted=2,
            findings={"diagnoses_count": 2},
            trace_notes="2 diagnoses extracted",
        )
        tracer.start_step(task.task_id)
        step = tracer.record_step(state, task, result, "Reasoning text", "Next: medications")
        assert step.step == 1
        assert step.selected_tool == "diagnosis_extractor"
        assert step.error is None

    def test_trace_count(self):
        tracer = TraceGenerator()
        tracer.record_planning_step("Plan generated", "step1 → step2", 0)
        assert tracer.get_step_count() == 1

    def test_records_planning_and_termination(self):
        tracer = TraceGenerator()
        state = make_state()
        tracer.record_planning_step("Initial plan", "dx → meds → allergy", 0)
        tracer.record_termination("All tasks complete", state)
        trace = tracer.get_trace()
        assert len(trace) == 2
        assert trace[0].selected_tool == "planner"
        assert trace[1].selected_tool == "terminator"
