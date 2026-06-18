"""
End-to-end test for the real (non-mocked) SummaryGeneratorTool.

Covers the bug: "Run Complete / ESCALATED" but the summary page showed
"Not Found". Root causes fixed elsewhere in this change set:
  1. app/api/summary.py router had a duplicated "/api/v1" prefix, so every
     summary endpoint 404'd regardless of agent run status.
  2. terminator.py stopped the loop the moment escalation_required became
     true, before summary_generator ever ran.
  3. SummaryGeneratorTool.execute() was a no-op stub — it never called the
     real generator/persistence path at all.
  4. DischargeSummaryGenerator.generate() raised and refused to produce a
     summary when the safety gate was BLOCKED (exactly the case for
     escalated runs).
  5. SummaryService._persist() called json.dumps(model.model_dump()) without
     mode="json", which threw on the datetime fields before db.commit().
  6. AuditLogger had no generic .log() method, but safety/engine.py,
     summary/generator.py, and summary_service.py all called audit.log(...).

This test exercises the real SummaryGeneratorTool against a real (test) DB
and asserts a DischargeReport row is actually persisted and retrievable,
including when state.escalation_required is True.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.agent.models import AgentState, AgentTask
from app.agent.tools.summary_generator import SummaryGeneratorTool
from app.config import settings
from app.db.models import AgentRun
from app.db.repositories.patient_repo import PatientRepository
from app.knowledge.models import Diagnosis, EvidencedFact
from app.knowledge.repository import KnowledgeRepository
from app.models.patient import PatientCreate
from app.services.summary_service import SummaryService


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
    return repo.create(PatientCreate(mrn="MRN-SUMMARY-1", first_name="Summary", last_name="Test"))


@pytest.fixture
def agent_run(db, patient):
    run = AgentRun(id="run-summary-test", patient_id=patient.id, status="ESCALATED")
    db.add(run)
    db.commit()
    return run


def _make_client() -> AsyncMock:
    client = AsyncMock()
    client.generate_content.return_value = "Patient tolerated the hospital course well."
    return client


class TestSummaryGeneratorToolPersistence:
    @pytest.mark.asyncio
    async def test_generates_and_persists_real_summary(self, db, patient, agent_run):
        kb = KnowledgeRepository(patient.id)
        kb.add_fact("diagnosis", Diagnosis(name=_fact("Type 2 Diabetes Mellitus"), is_principal=True))

        state = AgentState(run_id=agent_run.id, patient_id=patient.id)
        task = AgentTask(name="Generate Discharge Summary", tool_name="summary_generator", priority=11)

        tool = SummaryGeneratorTool(client=_make_client(), settings=settings)
        result = await tool.execute(task, state, kb, db)

        assert result.success is True
        assert result.findings["persisted"] is True

        service = SummaryService(db, _make_client(), settings)
        saved = service.get_summary_for_run(agent_run.id)
        assert saved is not None
        assert saved.patient_id == patient.id

    @pytest.mark.asyncio
    async def test_escalation_required_does_not_block_summary_persistence(self, db, patient, agent_run):
        """
        The exact reported bug: an escalated run (critical findings) must
        still get a real, persisted discharge summary — escalation must
        never bypass SummaryGenerator.
        """
        kb = KnowledgeRepository(patient.id)
        kb.add_fact("diagnosis", Diagnosis(name=_fact("Acute Myocardial Infarction"), is_principal=True))

        state = AgentState(run_id=agent_run.id, patient_id=patient.id)
        state.escalation_required = True
        state.escalation_reasons = ["Critical drug interaction: Warfarin + Aspirin"]
        task = AgentTask(name="Generate Discharge Summary", tool_name="summary_generator", priority=11)

        tool = SummaryGeneratorTool(client=_make_client(), settings=settings)
        result = await tool.execute(task, state, kb, db)

        assert result.success is True, f"summary_generator must succeed even when escalation_required: {result.error}"

        service = SummaryService(db, _make_client(), settings)
        saved = service.get_summary_for_run(agent_run.id)
        assert saved is not None, "escalation must never bypass SummaryGenerator — a summary must exist"
