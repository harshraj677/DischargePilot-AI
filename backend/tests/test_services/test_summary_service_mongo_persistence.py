from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.config import settings
from app.db.models import Document
from app.db.repositories.patient_repo import PatientRepository
from app.models.patient import PatientCreate
from app.models.enums import SafetySeverity
from app.repositories.document_repository import DocumentRepository
from app.repositories.finding_repository import FindingRepository
from app.repositories.patient_repository import PatientRepository as MongoPatientRepository
from app.repositories.summary_repository import SummaryRepository
from app.safety.models import (
    ReviewFlag, ReviewFlagCategory, SafetyFinding, SafetyReport, SafetyStatus, SectionName,
)
from app.services.summary_service import SummaryService
from app.summary.models import DischargeSummary, DischargeSummaryStatus


def _review_flag(description: str, severity: SafetySeverity, requires_ack: bool = True) -> ReviewFlag:
    return ReviewFlag(
        category=ReviewFlagCategory.MISSING_DATA,
        severity=severity,
        description=description,
        affected_section=SectionName.ALLERGIES,
        recommendation="Document allergy status",
        requires_acknowledgment=requires_ack,
    )


def _safety_finding(description: str, confidence: str = "High", evidence=None) -> SafetyFinding:
    return SafetyFinding(
        validator="completeness_validator",
        severity=SafetySeverity.HIGH,
        description=description,
        confidence=confidence,
        evidence=evidence or ["source excerpt"],
    )


def _safety_report(patient_id: str, run_id: str, flags, findings) -> SafetyReport:
    return SafetyReport(
        patient_id=patient_id,
        run_id=run_id,
        overall_status=SafetyStatus.REVIEW_REQUIRED,
        review_flags=flags,
        safety_findings=findings,
        can_generate_summary=True,
        completeness_score=0.8,
        safety_score=0.7,
    )


class TestCountFindingsBySeverity:
    def test_rolls_critical_into_high(self):
        flags = [
            _review_flag("a", SafetySeverity.CRITICAL),
            _review_flag("b", SafetySeverity.HIGH),
            _review_flag("c", SafetySeverity.MEDIUM),
            _review_flag("d", SafetySeverity.LOW),
            _review_flag("e", SafetySeverity.INFO),
        ]
        counts = SummaryService._count_findings_by_severity(flags)
        assert counts == {"HIGH": 2, "MEDIUM": 1, "LOW": 1, "INFO": 1}

    def test_empty_list_returns_zeroed_counts(self):
        assert SummaryService._count_findings_by_severity([]) == {
            "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0,
        }


class TestFindingsFromReviewFlags:
    def test_matches_confidence_and_evidence_by_description(self):
        flag = _review_flag("Allergy status is not documented", SafetySeverity.HIGH)
        finding = _safety_finding("Allergy status is not documented", confidence="High", evidence=["chart note"])

        results = SummaryService._findings_from_review_flags("s1", [flag], [finding])
        assert len(results) == 1
        assert results[0].confidence == "High"
        assert results[0].evidence == ["chart note"]
        assert results[0].id == flag.flag_id
        assert results[0].summary_id == "s1"
        assert results[0].requires_acknowledgment is True

    def test_defaults_when_no_matching_safety_finding(self):
        flag = _review_flag("Hospital course is not documented", SafetySeverity.MEDIUM)
        results = SummaryService._findings_from_review_flags("s1", [flag], [])
        assert results[0].confidence == "Moderate"
        assert results[0].evidence == []

    def test_empty_flags_returns_empty_list(self):
        assert SummaryService._findings_from_review_flags("s1", [], []) == []


@pytest.fixture
def patient(db):
    repo = PatientRepository(db)
    return repo.create(PatientCreate(mrn=f"MRN-{uuid.uuid4().hex[:8]}", first_name="Mongo", last_name="Test"))


@pytest.fixture
def mongo_db():
    client = AsyncMongoMockClient()
    return client["test_dischargepilot"]


def _summary(patient_id: str, run_id: str) -> DischargeSummary:
    return DischargeSummary(
        patient_id=patient_id,
        agent_run_id=run_id,
        status=DischargeSummaryStatus.PENDING_REVIEW,
        completeness_score=0.8,
        safety_score=0.7,
    )


class TestPersistToMongo:
    @pytest.mark.asyncio
    async def test_noop_when_mongo_unavailable(self, db, patient):
        service = SummaryService(db, AsyncMock(), settings)
        with patch("app.services.summary_service.mongodb_manager.get_database", return_value=None):
            await service._persist_to_mongo(
                patient.id, "run-1", _summary(patient.id, "run-1"),
                _safety_report(patient.id, "run-1", [], []),
            )
        # No exception means success — nothing else to assert without a database.

    @pytest.mark.asyncio
    async def test_writes_patient_document_summary_and_findings(self, db, patient, mongo_db):
        doc = Document(
            patient_id=patient.id,
            document_type="admission_note",
            file_name="admission.pdf",
            file_path="/uploads/admission.pdf",
            extracted_text="patient has no known drug allergies",
        )
        db.add(doc)
        db.commit()

        flag = _review_flag("Allergy status is not documented", SafetySeverity.HIGH)
        finding = _safety_finding("Allergy status is not documented")
        safety_report = _safety_report(patient.id, "run-1", [flag], [finding])
        summary = _summary(patient.id, "run-1")

        service = SummaryService(db, AsyncMock(), settings)
        with patch("app.services.summary_service.mongodb_manager.get_database", return_value=mongo_db):
            await service._persist_to_mongo(patient.id, "run-1", summary, safety_report)

        saved_patient = await MongoPatientRepository(mongo_db).get_by_id(patient.id)
        assert saved_patient is not None
        assert saved_patient.name == "Mongo Test"

        saved_docs = await DocumentRepository(mongo_db).list_for_patient(patient.id)
        assert len(saved_docs) == 1
        assert saved_docs[0].content == "patient has no known drug allergies"

        saved_summary = await SummaryRepository(mongo_db).get_by_id(summary.summary_id)
        assert saved_summary is not None
        assert saved_summary.high_findings_count == 1

        saved_findings = await FindingRepository(mongo_db).get_by_summary_id(summary.summary_id)
        assert len(saved_findings) == 1
        assert saved_findings[0].id == flag.flag_id

    @pytest.mark.asyncio
    async def test_swallows_exceptions_without_raising(self, db, patient, mongo_db):
        service = SummaryService(db, AsyncMock(), settings)
        with patch("app.services.summary_service.mongodb_manager.get_database", return_value=mongo_db), \
             patch(
                 "app.services.summary_service.PatientRepository.upsert",
                 side_effect=RuntimeError("boom"),
             ):
            # Must not raise even though the upsert inside fails.
            await service._persist_to_mongo(
                patient.id, "run-1", _summary(patient.id, "run-1"),
                _safety_report(patient.id, "run-1", [], []),
            )
