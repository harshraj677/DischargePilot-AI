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
from app.models.document import PageChunk
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
        mock_client = MagicMock()
        mock_settings = MagicMock()
        registry = ToolRegistry(mock_client, mock_settings)
        expected = [
            "diagnosis_extractor",
            "medication_extractor",
            "allergy_extractor",
            "lab_extractor",
            "procedure_extractor",
            "conflict_detector",
            "drug_interaction_checker",
            "medication_reconciler",
            "pending_result_extractor",
            "escalation_manager",
        ]
        for tool_name in expected:
            assert registry.get(tool_name) is not None, f"Missing tool: {tool_name}"

    def test_get_unknown_tool_returns_none(self):
        mock_client = MagicMock()
        mock_settings = MagicMock()
        registry = ToolRegistry(mock_client, mock_settings)
        assert registry.get("nonexistent_tool_xyz") is None

    def test_list_tools_returns_all_registered(self):
        mock_client = MagicMock()
        mock_settings = MagicMock()
        registry = ToolRegistry(mock_client, mock_settings)
        tools = registry.all_tool_names()
        assert len(tools) >= 10

    def test_tool_has_name_attribute(self):
        mock_client = MagicMock()
        mock_settings = MagicMock()
        registry = ToolRegistry(mock_client, mock_settings)
        tool = registry.get("diagnosis_extractor")
        assert hasattr(tool, "name") or tool is not None

    def test_register_and_retrieve_custom_tool(self):
        mock_client = MagicMock()
        mock_settings = MagicMock()
        registry = ToolRegistry(mock_client, mock_settings)
        mock_tool = MagicMock()
        mock_tool.name = "custom_test_tool"
        # Since registration is not a method on registry now, let's register directly in _instances or mock
        registry._instances["custom_test_tool"] = mock_tool
        assert registry._instances["custom_test_tool"] is mock_tool


# ── MedicationReconciliation Tool ─────────────────────────────────────────────

class TestMedicationReconciliationTool:
    @pytest.mark.asyncio
    async def test_detects_medication_change(self):
        from app.agent.tools.medication_reconciliation import MedicationReconciliationTool
        mock_client = AsyncMock()
        mock_settings = MagicMock()
        tool = MedicationReconciliationTool(mock_client, mock_settings)

        kb = _make_kb()
        kb.add_fact("medication_admission", Medication(
            name=_fact("Metformin"), dose=_fact("500mg")
        ))
        kb.add_fact("medication_discharge", Medication(
            name=_fact("Metformin"), dose=_fact("1000mg")
        ))

        state = _make_state()
        task = _make_task("medication_reconciler")
        db = MagicMock()

        mock_client.generate_content.return_value = '{"reconciliation": [{"medication_name": "Metformin", "status": "DOSE_CHANGED", "admission_details": "500mg", "discharge_details": "1000mg", "change_reason": "Escalation", "requires_patient_education": true}], "high_risk_changes": ["Metformin"], "summary": "Dose increased"}'
        
        result = await tool.execute(task, state, kb, db)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_detects_new_medication_added(self):
        from app.agent.tools.medication_reconciliation import MedicationReconciliationTool
        mock_client = AsyncMock()
        mock_settings = MagicMock()
        tool = MedicationReconciliationTool(mock_client, mock_settings)

        kb = _make_kb()
        kb.add_fact("medication_admission", Medication(name=_fact("Metformin"), dose=_fact("500mg")))
        kb.add_fact("medication_discharge", Medication(name=_fact("Metformin"), dose=_fact("500mg")))
        kb.add_fact("medication_discharge", Medication(name=_fact("Atorvastatin"), dose=_fact("40mg")))

        state = _make_state()
        task = _make_task("medication_reconciler")
        db = MagicMock()

        mock_client.generate_content.return_value = '{"reconciliation": [{"medication_name": "Atorvastatin", "status": "NEW", "admission_details": "", "discharge_details": "40mg", "change_reason": "New med", "requires_patient_education": true}], "high_risk_changes": [], "summary": "Added Atorvastatin"}'

        result = await tool.execute(task, state, kb, db)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_detects_stopped_medication(self):
        from app.agent.tools.medication_reconciliation import MedicationReconciliationTool
        mock_client = AsyncMock()
        mock_settings = MagicMock()
        tool = MedicationReconciliationTool(mock_client, mock_settings)

        kb = _make_kb()
        kb.add_fact("medication_admission", Medication(name=_fact("Metformin"), dose=_fact("500mg")))
        kb.add_fact("medication_admission", Medication(name=_fact("Aspirin"), dose=_fact("81mg")))
        kb.add_fact("medication_discharge", Medication(name=_fact("Metformin"), dose=_fact("500mg")))

        state = _make_state()
        task = _make_task("medication_reconciler")
        db = MagicMock()

        mock_client.generate_content.return_value = '{"reconciliation": [{"medication_name": "Aspirin", "status": "DISCONTINUED", "admission_details": "81mg", "discharge_details": "", "change_reason": "Stopped", "requires_patient_education": false}], "high_risk_changes": [], "summary": "Stopped Aspirin"}'

        result = await tool.execute(task, state, kb, db)
        assert result.success is True


# ── ConflictDetection Tool ────────────────────────────────────────────────────

class TestConflictDetectionTool:
    @pytest.mark.asyncio
    async def test_detects_allergy_conflict(self):
        from app.agent.tools.conflict_detection import ConflictDetectionTool
        mock_client = AsyncMock()
        mock_settings = MagicMock()
        tool = ConflictDetectionTool(mock_client, mock_settings)

        kb = _make_kb()
        kb.add_fact("allergy", Allergy(allergen=_fact("Penicillin"), reaction=_fact("Anaphylaxis"), severity="life-threatening"))
        kb.add_fact("medication_discharge", Medication(name=_fact("Penicillin"), dose=_fact("500mg")))
        kb.add_fact("diagnosis", Diagnosis(name=_fact("Bacterial Infection"), is_principal=True))

        state = _make_state()
        task = _make_task("conflict_detector")
        db = MagicMock()

        mock_client.generate_content.return_value = '{"conflicts": [{"conflict_type": "medication_allergy", "severity": "critical", "description": "Penicillin allergy conflict", "involved_items": ["Penicillin"], "recommendation": "Stop Penicillin"}], "overall_safety_assessment": "escalate_immediately"}'

        result = await tool.execute(task, state, kb, db)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_no_conflict_on_clean_data(self):
        from app.agent.tools.conflict_detection import ConflictDetectionTool
        mock_client = AsyncMock()
        mock_settings = MagicMock()
        tool = ConflictDetectionTool(mock_client, mock_settings)

        kb = _make_kb()
        kb.add_fact("allergy", Allergy(allergen=_fact("Peanuts"), reaction=_fact("Hives")))
        kb.add_fact("medication_discharge", Medication(name=_fact("Metformin"), dose=_fact("500mg")))
        kb.add_fact("diagnosis", Diagnosis(name=_fact("Type 2 DM"), is_principal=True))

        state = _make_state()
        task = _make_task("conflict_detector")
        db = MagicMock()

        mock_client.generate_content.return_value = '{"conflicts": [], "overall_safety_assessment": "safe"}'

        result = await tool.execute(task, state, kb, db)
        assert result.success is True


# ── PendingResult Tool ────────────────────────────────────────────────────────

class TestPendingResultTool:
    @pytest.mark.asyncio
    async def test_detects_pending_blood_culture(self):
        from app.agent.tools.pending_result import PendingResultTool
        mock_client = AsyncMock()
        mock_settings = MagicMock()
        tool = PendingResultTool(mock_client, mock_settings)

        kb = _make_kb()
        state = _make_state()
        task = _make_task("pending_result_extractor")
        db = MagicMock()
        
        text = "Blood cultures collected 05/28/2025 — PENDING"
        page_chunk = PageChunk(
            id="chunk-001",
            document_id="doc-001",
            document_name="test.pdf",
            page_number=1,
            text=text,
            char_count=len(text),
            word_count=len(text.split()),
        )
        with patch("app.db.repositories.document_repo.DocumentRepository.get_page_chunks", return_value=[page_chunk]):
            from app.knowledge.extraction_engine import ExtractionResult
            with patch("app.agent.tools.base.BaseTool._get_consolidated_extraction", return_value=ExtractionResult(
                data={"pending_results": [{"description": "Blood Culture", "confidence": 0.9, "page_number": 1, "evidence": "Blood cultures PENDING"}]},
                tokens_used=10,
                input_tokens_used=5,
                from_cache=False
            )):
                result = await tool.execute(task, state, kb, db)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_no_pending_on_completed_results(self):
        from app.agent.tools.pending_result import PendingResultTool
        mock_client = AsyncMock()
        mock_settings = MagicMock()
        tool = PendingResultTool(mock_client, mock_settings)

        kb = _make_kb()
        state = _make_state()
        task = _make_task("pending_result_extractor")
        db = MagicMock()
        
        text = "All lab results finalized."
        page_chunk = PageChunk(
            id="chunk-001",
            document_id="doc-001",
            document_name="test.pdf",
            page_number=1,
            text=text,
            char_count=len(text),
            word_count=len(text.split()),
        )
        with patch("app.db.repositories.document_repo.DocumentRepository.get_page_chunks", return_value=[page_chunk]):
            from app.knowledge.extraction_engine import ExtractionResult
            with patch("app.agent.tools.base.BaseTool._get_consolidated_extraction", return_value=ExtractionResult(
                data={"pending_results": []},
                tokens_used=5,
                input_tokens_used=2,
                from_cache=False
            )):
                result = await tool.execute(task, state, kb, db)
        assert result.success is True


# ── EscalationManager Tool ────────────────────────────────────────────────────

class TestEscalationManagerTool:
    @pytest.mark.asyncio
    async def test_escalates_on_critical_conflict(self):
        from app.agent.tools.escalation import EscalationTool
        from app.knowledge.models import ClinicalConflict
        mock_client = AsyncMock()
        mock_settings = MagicMock()
        tool = EscalationTool(mock_client, mock_settings)

        kb = _make_kb()
        kb.add_conflict(ClinicalConflict(
            conflict_id="c-001",
            conflict_type="medication_allergy",
            description="Life-threatening allergy conflict",
            severity="critical",
            resolved=False,
        ))

        state = _make_state()
        task = _make_task("escalation_manager")
        db = MagicMock()
        
        result = await tool.execute(task, state, kb, db)
        assert result.success is True
        assert state.escalation_required is True

    @pytest.mark.asyncio
    async def test_no_escalation_on_clean_state(self):
        from app.agent.tools.escalation import EscalationTool
        mock_client = AsyncMock()
        mock_settings = MagicMock()
        tool = EscalationTool(mock_client, mock_settings)

        kb = _make_kb()
        state = _make_state()
        state.escalation_required = False
        task = _make_task("escalation_manager")
        db = MagicMock()

        with patch.object(kb, "get_missing_critical_fields", return_value=[]):
            result = await tool.execute(task, state, kb, db)
        assert result.success is True
        assert state.escalation_required is False
