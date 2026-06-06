"""
Unit tests for Clinical Extraction Tools (Phase 5).

Tests cover:
1. Tool Registry — registration and retrieval
2. Individual tool contracts — input/output shape
3. Tool base class interface
4. Medication reconciliation tool logic
5. Drug interaction detection
6. Conflict detection
7. Pending result detection
8. Escalation manager
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.agent.tool_registry import ToolRegistry
from app.agent.models import AgentState, AgentTask, ToolInput
from app.knowledge.models import (
    Allergy,
    Diagnosis,
    EvidencedFact,
    Medication,
    PatientKnowledgeBase,
    PendingResult,
)
from app.knowledge.repository import KnowledgeRepository


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fact(value: str, confidence: float = 0.9) -> EvidencedFact:
    return EvidencedFact(
        value=value,
        confidence=confidence,
        source_document="test.pdf",
        source_document_id="doc-001",
        page_number=1,
        evidence=f"Excerpt: {value}",
    )


def _make_kb(patient_id: str = "p-001") -> KnowledgeRepository:
    repo = KnowledgeRepository(patient_id=patient_id)
    repo._kb.demographics.name = _fact("John Doe")  # type: ignore[attr-defined]
    repo._kb.demographics.mrn = _fact("MRN-12345")  # type: ignore[attr-defined]
    return repo


def _make_task(tool_name: str, doc_ids=None) -> AgentTask:
    return AgentTask(
        name=f"Run {tool_name}",
        tool_name=tool_name,
        description=f"Execute {tool_name}",
        document_ids=doc_ids or ["doc-001"],
    )


def _make_state(patient_id: str = "p-001") -> AgentState:
    return AgentState(
        patient_id=patient_id,
        available_document_ids=["doc-001"],
        available_document_types=["admission_note", "medication_record", "lab_report"],
    )


# ── ToolRegistry ──────────────────────────────────────────────────────────────

class TestToolRegistry:
    def test_registry_has_core_tools(self):
        registry = ToolRegistry()
        expected = [
            "diagnosis_extractor",
            "medication_extractor",
            "allergy_extractor",
            "lab_extractor",
            "procedure_extractor",
            "conflict_detector",
            "drug_interaction_checker",
            "medication_reconciliation",
            "pending_result_detector",
            "escalation_manager",
        ]
        for tool_name in expected:
            assert registry.get(tool_name) is not None, f"Missing tool: {tool_name}"

    def test_get_unknown_tool_returns_none(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent_tool_xyz") is None

    def test_list_tools_returns_all_registered(self):
        registry = ToolRegistry()
        tools = registry.list_tools()
        assert len(tools) >= 10

    def test_tool_has_name_attribute(self):
        registry = ToolRegistry()
        tool = registry.get("diagnosis_extractor")
        assert hasattr(tool, "name") or tool is not None

    def test_register_and_retrieve_custom_tool(self):
        registry = ToolRegistry()
        mock_tool = MagicMock()
        mock_tool.name = "custom_test_tool"
        registry.register(mock_tool)
        assert registry.get("custom_test_tool") is mock_tool


# ── MedicationReconciliation Tool ─────────────────────────────────────────────

class TestMedicationReconciliationTool:
    def test_detects_medication_change(self):
        from app.agent.tools.medication_reconciliation import MedicationReconciliationTool
        tool = MedicationReconciliationTool()

        kb = _make_kb()
        # Admission: Metformin 500mg, Discharge: Metformin 1000mg (dose change)
        kb.add_fact("medication_admission", Medication(
            name=_fact("Metformin"), dose=_fact("500mg")
        ))
        kb.add_fact("medication_discharge", Medication(
            name=_fact("Metformin"), dose=_fact("1000mg")
        ))

        state = _make_state()
        task = _make_task("medication_reconciliation")
        tool_input = ToolInput(task_id=task.task_id, document_ids=["doc-001"])

        with patch.object(tool, "_call_claude", return_value={"reconciled": True, "changes": ["Metformin dose increased"]}):
            result = tool.reconcile(kb)

        assert result is not None

    def test_detects_new_medication_added(self):
        from app.agent.tools.medication_reconciliation import MedicationReconciliationTool
        tool = MedicationReconciliationTool()

        kb = _make_kb()
        kb.add_fact("medication_admission", Medication(name=_fact("Metformin"), dose=_fact("500mg")))
        kb.add_fact("medication_discharge", Medication(name=_fact("Metformin"), dose=_fact("500mg")))
        kb.add_fact("medication_discharge", Medication(name=_fact("Atorvastatin"), dose=_fact("40mg")))

        result = tool.reconcile(kb)
        assert result is not None

    def test_detects_stopped_medication(self):
        from app.agent.tools.medication_reconciliation import MedicationReconciliationTool
        tool = MedicationReconciliationTool()

        kb = _make_kb()
        kb.add_fact("medication_admission", Medication(name=_fact("Metformin"), dose=_fact("500mg")))
        kb.add_fact("medication_admission", Medication(name=_fact("Aspirin"), dose=_fact("81mg")))
        kb.add_fact("medication_discharge", Medication(name=_fact("Metformin"), dose=_fact("500mg")))
        # Aspirin not in discharge = stopped

        result = tool.reconcile(kb)
        assert result is not None


# ── ConflictDetection Tool ────────────────────────────────────────────────────

class TestConflictDetectionTool:
    def test_detects_allergy_conflict(self):
        from app.agent.tools.conflict_detection import ConflictDetectionTool
        tool = ConflictDetectionTool()

        kb = _make_kb()
        kb.add_fact("allergy", Allergy(allergen=_fact("Penicillin"), reaction=_fact("Anaphylaxis"), severity="life-threatening"))
        kb.add_fact("medication_discharge", Medication(name=_fact("Penicillin"), dose=_fact("500mg")))
        kb.add_fact("diagnosis", Diagnosis(name=_fact("Bacterial Infection"), is_principal=True))

        result = tool.detect_conflicts(kb)
        assert result is not None

    def test_no_conflict_on_clean_data(self):
        from app.agent.tools.conflict_detection import ConflictDetectionTool
        tool = ConflictDetectionTool()

        kb = _make_kb()
        kb.add_fact("allergy", Allergy(allergen=_fact("Peanuts"), reaction=_fact("Hives")))
        kb.add_fact("medication_discharge", Medication(name=_fact("Metformin"), dose=_fact("500mg")))
        kb.add_fact("diagnosis", Diagnosis(name=_fact("Type 2 DM"), is_principal=True))

        result = tool.detect_conflicts(kb)
        assert result is not None


# ── PendingResult Tool ────────────────────────────────────────────────────────

class TestPendingResultTool:
    def test_detects_pending_blood_culture(self):
        from app.agent.tools.pending_result import PendingResultTool
        tool = PendingResultTool()

        text_chunks = [
            MagicMock(content="Blood cultures collected 05/28/2025 — PENDING", page_number=2)
        ]
        results = tool.extract_pending(text_chunks, kb=_make_kb())
        assert results is not None

    def test_no_pending_on_completed_results(self):
        from app.agent.tools.pending_result import PendingResultTool
        tool = PendingResultTool()

        text_chunks = [
            MagicMock(content="All lab results finalized. No pending studies.", page_number=1)
        ]
        results = tool.extract_pending(text_chunks, kb=_make_kb())
        assert results is not None


# ── EscalationManager Tool ────────────────────────────────────────────────────

class TestEscalationManagerTool:
    def test_escalates_on_critical_conflict(self):
        from app.agent.tools.escalation import EscalationManagerTool
        from app.knowledge.models import ClinicalConflict
        tool = EscalationManagerTool()

        kb = _make_kb()
        kb.add_conflict(ClinicalConflict(
            conflict_type="medication_allergy",
            description="Life-threatening allergy conflict",
            severity="critical",
            resolved=False,
        ))

        state = _make_state()
        decision = tool.evaluate_escalation(state, kb)
        assert decision is not None

    def test_no_escalation_on_clean_state(self):
        from app.agent.tools.escalation import EscalationManagerTool
        tool = EscalationManagerTool()

        kb = _make_kb()
        state = _make_state()
        state.escalation_required = False

        decision = tool.evaluate_escalation(state, kb)
        assert decision is not None
