"""
Unit tests for Phase 6 Discharge Summary Generator.

Tests are split into:
1. Template-based section builders (synchronous, no Claude calls)
2. DischargeSummary model behavior
3. SummaryFormatter
4. Integration: generate() with mocked Claude client
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.knowledge.models import (
    Allergy,
    Diagnosis,
    EvidencedFact,
    FollowUp,
    HospitalInfo,
    LabResult,
    Medication,
    PatientDemographics,
    PatientKnowledgeBase,
    PendingResult,
    Procedure,
)
from app.knowledge.repository import KnowledgeRepository
from app.models.enums import SafetySeverity
from app.safety.models import SafetyReport, SafetyStatus, SectionName
from app.summary.formatter import format_as_text
from app.summary.models import DischargeSummary, DischargeSummaryStatus, SummaryStatus


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _fact(value: str, confidence: float = 0.90) -> EvidencedFact:
    return EvidencedFact(
        value=value,
        confidence=confidence,
        source_document="test.pdf",
        source_document_id="doc-001",
        page_number=1,
        evidence=f"Evidence for: {value}",
    )


def _full_kb() -> KnowledgeRepository:
    kb = PatientKnowledgeBase(patient_id="p-test")
    kb.demographics = PatientDemographics(
        name=_fact("Alice Smith"),
        mrn=_fact("MRN-999"),
        date_of_birth=_fact("1970-05-15"),
        age=_fact("55"),
        gender=_fact("Female"),
    )
    kb.hospital_info = HospitalInfo(
        facility=_fact("City Hospital"),
        admission_date=_fact("2026-01-10"),
        discharge_date=_fact("2026-01-15"),
        attending_physician=_fact("Dr. Jones"),
        ward=_fact("Cardiology"),
    )
    kb.diagnoses = [
        Diagnosis(name=_fact("Acute MI"), is_principal=True, icd_code="I21.9"),
        Diagnosis(name=_fact("Hypertension"), is_principal=False, icd_code="I10"),
    ]
    kb.medications_admission = [
        Medication(name=_fact("Aspirin"), dose=_fact("100mg"), frequency=_fact("OD")),
    ]
    kb.medications_discharge = [
        Medication(name=_fact("Aspirin"), dose=_fact("100mg"), frequency=_fact("OD")),
        Medication(name=_fact("Atorvastatin"), dose=_fact("40mg"), frequency=_fact("ON")),
    ]
    kb.allergies = [
        Allergy(allergen=_fact("Ibuprofen"), reaction=_fact("Rash"), severity="mild")
    ]
    kb.procedures = [
        Procedure(name=_fact("PCI"), date=_fact("2026-01-11"), outcome=_fact("Successful"))
    ]
    kb.lab_results = [
        LabResult(
            test_name=_fact("Troponin I"),
            value=_fact("4.2"),
            unit="ng/mL",
            is_abnormal=True,
        )
    ]
    kb.pending_results = [
        PendingResult(
            description=_fact("Lipid panel"),
            expected_by="2026-01-20",
        )
    ]
    kb.follow_ups = [
        FollowUp(
            instruction=_fact("Cardiology follow-up"),
            specialist="Cardiologist",
            timeframe="2 weeks",
        )
    ]
    kb.hospital_course = _fact("Patient admitted with STEMI. Underwent PCI. Stable recovery.")
    kb.discharge_condition = _fact("Stable")

    repo = KnowledgeRepository(patient_id="p-test")
    repo._kb = kb
    return repo


def _approved_safety_report() -> SafetyReport:
    return SafetyReport(
        patient_id="p-test",
        run_id="run-001",
        overall_status=SafetyStatus.APPROVED,
        can_generate_summary=True,
        completeness_score=0.9,
        safety_score=0.95,
    )


# ── DischargeSummary model ────────────────────────────────────────────────────

class TestDischargeSummaryModel:
    def test_default_status_is_pending_review(self):
        summary = DischargeSummary(patient_id="p-001", agent_run_id="run-001")
        assert summary.status == DischargeSummaryStatus.PENDING_REVIEW

    def test_sections_property_returns_all_sections(self):
        summary = DischargeSummary(patient_id="p-001", agent_run_id="run-001")
        assert len(summary.sections) == 14

    def test_populated_section_count(self):
        from app.summary.models import SummarySection
        summary = DischargeSummary(patient_id="p-001", agent_run_id="run-001")
        summary.patient_info = SummarySection(
            name="patient_info", content="Alice", status=SummaryStatus.POPULATED
        )
        summary.hospital_info = SummarySection(
            name="hospital_info", content="City Hospital", status=SummaryStatus.POPULATED
        )
        assert summary.populated_section_count == 2

    def test_to_dict_structure(self):
        summary = DischargeSummary(patient_id="p-001", agent_run_id="run-001")
        d = summary.to_dict()
        assert "summary_id" in d
        assert "sections" in d
        assert "review_flags" in d


# ── Template-based sections (no Claude) ──────────────────────────────────────

class TestTemplateSections:
    """
    These tests instantiate DischargeSummaryGenerator and call the private
    _build_* methods directly to avoid Claude API calls.
    """

    def _generator(self):
        from app.config import settings
        from app.summary.generator import DischargeSummaryGenerator
        mock_client = MagicMock()
        return DischargeSummaryGenerator(mock_client, settings)

    def test_patient_info_populated(self):
        gen = self._generator()
        repo = _full_kb()
        section = gen._build_patient_info(repo)
        assert section.status == SummaryStatus.POPULATED
        assert "Alice Smith" in section.content
        assert "MRN-999" in section.content

    def test_principal_diagnosis_populated(self):
        gen = self._generator()
        repo = _full_kb()
        section = gen._build_principal_diagnosis(repo)
        assert section.status == SummaryStatus.POPULATED
        assert "Acute MI" in section.content
        assert "I21.9" in section.content

    def test_secondary_diagnoses_excludes_principal(self):
        gen = self._generator()
        repo = _full_kb()
        section = gen._build_secondary_diagnoses(repo)
        assert "Hypertension" in section.content
        assert "Acute MI" not in section.content

    def test_allergies_populated(self):
        gen = self._generator()
        repo = _full_kb()
        section = gen._build_allergies(repo)
        assert "Ibuprofen" in section.content
        assert "Rash" in section.content

    def test_allergies_missing_when_no_allergies(self):
        gen = self._generator()
        repo = _full_kb()
        repo._kb.allergies = []
        section = gen._build_allergies(repo)
        assert section.status == SummaryStatus.MISSING

    def test_discharge_meds_populated(self):
        gen = self._generator()
        repo = _full_kb()
        section = gen._build_discharge_meds(repo)
        assert section.status == SummaryStatus.POPULATED
        assert "Aspirin" in section.content
        assert "Atorvastatin" in section.content

    def test_lab_results_marks_critical(self):
        gen = self._generator()
        repo = _full_kb()
        repo._kb.lab_results = [
            LabResult(
                test_name=_fact("Potassium"),
                value=_fact("6.8"),
                unit="mmol/L",
                is_critical=True,
            )
        ]
        section = gen._build_lab_results(repo)
        assert "CRITICAL" in section.content

    def test_pending_results_populated(self):
        gen = self._generator()
        repo = _full_kb()
        section = gen._build_pending_results(repo)
        assert "Lipid panel" in section.content

    def test_follow_up_populated(self):
        gen = self._generator()
        repo = _full_kb()
        section = gen._build_follow_up(repo)
        assert "Cardiology follow-up" in section.content
        assert "2 weeks" in section.content

    def test_missing_when_no_follow_up(self):
        gen = self._generator()
        repo = _full_kb()
        repo._kb.follow_ups = []
        section = gen._build_follow_up(repo)
        assert section.status == SummaryStatus.MISSING


# ── DischargeSummaryGenerator.generate() integration ──────────────────────────

class TestGenerateSummary:
    """Tests for the async generate() method with mocked Claude."""

    @pytest.mark.asyncio
    async def test_generate_returns_summary(self):
        from app.config import settings
        from app.summary.generator import DischargeSummaryGenerator

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Patient had a successful PCI procedure.")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        gen = DischargeSummaryGenerator(mock_client, settings)
        repo = _full_kb()
        safety_report = _approved_safety_report()

        summary = await gen.generate(repo, safety_report, run_id="run-001")

        assert summary.patient_id == "p-test"
        assert summary.status == DischargeSummaryStatus.PENDING_REVIEW
        assert summary.hospital_course.status != SummaryStatus.MISSING
        assert "Alice Smith" in summary.patient_info.content

    @pytest.mark.asyncio
    async def test_generate_raises_when_blocked(self):
        from app.config import settings
        from app.safety.models import SafetyReport, SafetyStatus
        from app.summary.generator import DischargeSummaryGenerator

        mock_client = AsyncMock()
        gen = DischargeSummaryGenerator(mock_client, settings)
        repo = _full_kb()
        blocked_report = SafetyReport(
            patient_id="p-test",
            run_id="run-001",
            overall_status=SafetyStatus.BLOCKED,
            can_generate_summary=False,
            blocking_issues=["Critical allergy conflict"],
            completeness_score=0.5,
            safety_score=0.0,
        )
        with pytest.raises(ValueError, match="Cannot generate summary"):
            await gen.generate(repo, blocked_report, run_id="run-001")

    @pytest.mark.asyncio
    async def test_claude_failure_falls_back_to_template(self):
        from app.config import settings
        from app.summary.generator import DischargeSummaryGenerator

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API timeout"))

        gen = DischargeSummaryGenerator(mock_client, settings)
        repo = _full_kb()
        safety_report = _approved_safety_report()

        summary = await gen.generate(repo, safety_report, run_id="run-001")

        # Falls back to raw fact value
        assert summary.hospital_course.status == SummaryStatus.PARTIAL
        assert len(summary.hospital_course.content) > 0


# ── SummaryFormatter ─────────────────────────────────────────────────────────

class TestSummaryFormatter:
    def _make_populated_summary(self) -> DischargeSummary:
        from app.summary.models import SummarySection
        summary = DischargeSummary(patient_id="p-001", agent_run_id="run-001")
        summary.patient_info = SummarySection(
            name="patient_info",
            content="Name: Alice\nMRN: 999",
            status=SummaryStatus.POPULATED,
            generated_by="template",
        )
        summary.principal_diagnosis = SummarySection(
            name="principal_diagnosis",
            content="Acute MI (I21.9)",
            status=SummaryStatus.POPULATED,
        )
        summary.hospital_course = SummarySection(
            name="hospital_course",
            content="Patient had uneventful recovery.",
            status=SummaryStatus.POPULATED,
            generated_by="claude",
        )
        return summary

    def test_format_as_text_includes_header(self):
        summary = self._make_populated_summary()
        text = format_as_text(summary)
        assert "DISCHARGE SUMMARY" in text
        assert "AI-generated draft" in text

    def test_format_as_text_includes_sections(self):
        summary = self._make_populated_summary()
        text = format_as_text(summary)
        assert "Alice" in text
        assert "Acute MI" in text
        assert "uneventful recovery" in text

    def test_format_as_text_skips_missing_sections(self):
        summary = self._make_populated_summary()
        text = format_as_text(summary)
        # follow_up is MISSING → its header should NOT appear
        assert "FOLLOW-UP INSTRUCTIONS" not in text

    def test_format_includes_review_flags(self):
        from app.safety.models import ReviewFlag, ReviewFlagCategory, SectionName
        summary = self._make_populated_summary()
        summary.review_flags = [
            ReviewFlag(
                category=ReviewFlagCategory.MISSING_DATA,
                severity=SafetySeverity.HIGH,
                description="Follow-up not documented",
                affected_section=SectionName.FOLLOW_UP,
                recommendation="Add follow-up instructions",
            )
        ]
        text = format_as_text(summary)
        assert "REVIEW FLAGS" in text
        assert "Follow-up not documented" in text
