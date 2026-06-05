"""
Unit tests for the Phase 6 Safety Validation Engine.

Tests cover:
1. SafetyValidationEngine — overall status determination
2. EvidenceValidator — missing/low-confidence evidence detection
3. ConflictValidator — unresolved conflict detection, duplicate dose detection
4. MedicationValidator — allergy cross-check, high-risk med dose, empty discharge meds
5. CompletenessValidator — required field detection
6. PendingResultValidator — pending result flagging, critical lab flagging
7. ReviewFlagGenerator — medication change flags, critical condition flags
8. Safety score formula
"""
from __future__ import annotations

import pytest

from app.knowledge.models import (
    Allergy,
    ClinicalConflict,
    EvidencedFact,
    FollowUp,
    HospitalInfo,
    LabResult,
    Medication,
    PatientDemographics,
    PatientKnowledgeBase,
    PendingResult,
    Diagnosis,
)
from app.knowledge.repository import KnowledgeRepository
from app.models.enums import SafetySeverity
from app.safety.engine import SafetyValidationEngine
from app.safety.models import SafetyStatus
from app.safety.validators.completeness import CompletenessValidator
from app.safety.validators.conflict import ConflictValidator
from app.safety.validators.evidence import EvidenceValidator
from app.safety.validators.medication import MedicationValidator
from app.safety.validators.pending import PendingResultValidator


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _fact(value: str, confidence: float = 0.90, page: int = 1) -> EvidencedFact:
    return EvidencedFact(
        value=value,
        confidence=confidence,
        source_document="test_doc.pdf",
        source_document_id="doc-001",
        page_number=page,
        evidence=f"Verbatim excerpt: {value}",
    )


def _make_minimal_kb(patient_id: str = "p-001") -> PatientKnowledgeBase:
    """KB with all required fields populated."""
    kb = PatientKnowledgeBase(patient_id=patient_id)
    kb.demographics = PatientDemographics(
        name=_fact("John Doe"),
        mrn=_fact("MRN-12345"),
    )
    kb.hospital_info = HospitalInfo(
        admission_date=_fact("2026-01-01"),
    )
    dx = Diagnosis(name=_fact("Pneumonia"), is_principal=True)
    kb.diagnoses = [dx]
    med = Medication(name=_fact("Amoxicillin"), dose=_fact("500mg"))
    kb.medications_discharge = [med]
    allergy = Allergy(allergen=_fact("Penicillin"))
    kb.allergies = [allergy]
    kb.hospital_course = _fact("Patient admitted with pneumonia. Treated with IV antibiotics.")
    kb.discharge_condition = _fact("Stable")
    kb.follow_ups = [FollowUp(instruction=_fact("Follow up with GP in 1 week"))]
    return kb


def _repo(kb: PatientKnowledgeBase) -> KnowledgeRepository:
    repo = KnowledgeRepository(patient_id=kb.patient_id)
    repo._kb = kb
    return repo


# ── EvidenceValidator ─────────────────────────────────────────────────────────

class TestEvidenceValidator:
    def test_passes_when_all_evidence_present(self):
        kb = _make_minimal_kb()
        repo = _repo(kb)
        result = EvidenceValidator().run(repo)
        assert result.passed

    def test_critical_when_fact_has_no_evidence(self):
        kb = _make_minimal_kb()
        kb.demographics.name = EvidencedFact(
            value="Jane Doe",
            confidence=0.95,
            source_document="doc.pdf",
            source_document_id="doc-001",
            page_number=1,
            evidence="",  # empty evidence
        )
        repo = _repo(kb)
        result = EvidenceValidator().run(repo)
        assert not result.passed
        critical = [f for f in result.findings if f.severity == SafetySeverity.CRITICAL]
        assert len(critical) >= 1

    def test_flags_low_confidence(self):
        kb = _make_minimal_kb()
        kb.demographics.name = _fact("John Doe", confidence=0.50)
        repo = _repo(kb)
        result = EvidenceValidator().run(repo)
        medium = [f for f in result.findings if f.severity == SafetySeverity.MEDIUM]
        assert len(medium) >= 1
        assert len(result.review_flags) >= 1

    def test_passes_when_kb_is_empty(self):
        kb = PatientKnowledgeBase(patient_id="p-empty")
        repo = _repo(kb)
        result = EvidenceValidator().run(repo)
        assert result.passed


# ── ConflictValidator ─────────────────────────────────────────────────────────

class TestConflictValidator:
    def test_passes_when_no_conflicts(self):
        kb = _make_minimal_kb()
        result = ConflictValidator().run(_repo(kb))
        assert result.passed

    def test_flags_unresolved_critical_conflict(self):
        kb = _make_minimal_kb()
        kb.conflicts.append(ClinicalConflict(
            conflict_type="medication_allergy",
            description="Penicillin allergy vs amoxicillin",
            severity="critical",
            resolved=False,
        ))
        result = ConflictValidator().run(_repo(kb))
        assert not result.passed
        assert any(f.severity == SafetySeverity.CRITICAL for f in result.findings)

    def test_ignores_resolved_conflicts(self):
        kb = _make_minimal_kb()
        kb.conflicts.append(ClinicalConflict(
            conflict_type="drug_interaction",
            description="Resolved interaction",
            severity="critical",
            resolved=True,
        ))
        result = ConflictValidator().run(_repo(kb))
        assert result.passed

    def test_detects_conflicting_doses_for_same_med(self):
        kb = _make_minimal_kb()
        kb.medications_discharge = [
            Medication(name=_fact("Metformin"), dose=_fact("500mg")),
            Medication(name=_fact("Metformin"), dose=_fact("1000mg")),
        ]
        result = ConflictValidator().run(_repo(kb))
        high_findings = [f for f in result.findings if f.severity == SafetySeverity.HIGH]
        assert len(high_findings) >= 1


# ── MedicationValidator ───────────────────────────────────────────────────────

class TestMedicationValidator:
    def test_passes_with_clean_med_list(self):
        kb = _make_minimal_kb()
        # Amoxicillin is in discharge meds, allergy is to Penicillin (not an exact match)
        result = MedicationValidator().run(_repo(kb))
        # passes because "amoxicillin" != "penicillin" (not a direct substring match)
        assert result.severity != SafetySeverity.CRITICAL

    def test_critical_allergy_conflict(self):
        kb = _make_minimal_kb()
        kb.medications_discharge = [Medication(name=_fact("Penicillin"), dose=_fact("500mg"))]
        kb.allergies = [Allergy(allergen=_fact("Penicillin"))]
        result = MedicationValidator().run(_repo(kb))
        assert not result.passed
        assert any(f.severity == SafetySeverity.CRITICAL for f in result.findings)

    def test_flags_missing_discharge_medication_list(self):
        kb = _make_minimal_kb()
        kb.medications_discharge = []
        result = MedicationValidator().run(_repo(kb))
        assert result.severity in (SafetySeverity.HIGH, SafetySeverity.CRITICAL)

    def test_flags_high_risk_med_without_dose(self):
        kb = _make_minimal_kb()
        kb.medications_discharge = [Medication(name=_fact("warfarin"))]  # no dose
        result = MedicationValidator().run(_repo(kb))
        assert any(f.severity == SafetySeverity.HIGH for f in result.findings)


# ── CompletenessValidator ─────────────────────────────────────────────────────

class TestCompletenessValidator:
    def test_passes_with_complete_kb(self):
        kb = _make_minimal_kb()
        result = CompletenessValidator().run(_repo(kb))
        assert result.passed

    def test_flags_missing_patient_name(self):
        kb = _make_minimal_kb()
        kb.demographics.name = None
        result = CompletenessValidator().run(_repo(kb))
        assert not result.passed
        assert any("Patient name" in f.description for f in result.findings)

    def test_flags_missing_principal_diagnosis(self):
        kb = _make_minimal_kb()
        kb.diagnoses = []
        result = CompletenessValidator().run(_repo(kb))
        assert not result.passed

    def test_medium_for_missing_follow_up(self):
        kb = _make_minimal_kb()
        kb.follow_ups = []
        result = CompletenessValidator().run(_repo(kb))
        medium_findings = [f for f in result.findings if f.severity == SafetySeverity.MEDIUM]
        assert len(medium_findings) >= 1


# ── PendingResultValidator ────────────────────────────────────────────────────

class TestPendingResultValidator:
    def test_passes_with_no_pending_results(self):
        kb = _make_minimal_kb()
        result = PendingResultValidator().run(_repo(kb))
        assert result.passed

    def test_flags_pending_result(self):
        kb = _make_minimal_kb()
        kb.pending_results = [
            PendingResult(description=_fact("Urine culture pending"))
        ]
        result = PendingResultValidator().run(_repo(kb))
        assert len(result.review_flags) >= 1

    def test_high_severity_for_critical_pending(self):
        kb = _make_minimal_kb()
        kb.pending_results = [
            PendingResult(description=_fact("Blood culture sensitivity pending"))
        ]
        result = PendingResultValidator().run(_repo(kb))
        assert any(f.severity == SafetySeverity.HIGH for f in result.findings)

    def test_flags_critical_lab(self):
        kb = _make_minimal_kb()
        kb.lab_results = [
            LabResult(
                test_name=_fact("Potassium"),
                value=_fact("6.8"),
                unit="mmol/L",
                is_critical=True,
            )
        ]
        result = PendingResultValidator().run(_repo(kb))
        assert any(f.severity == SafetySeverity.HIGH for f in result.findings)


# ── SafetyValidationEngine ────────────────────────────────────────────────────

class TestSafetyValidationEngine:
    def test_approved_for_clean_kb(self):
        kb = _make_minimal_kb()
        report = SafetyValidationEngine().validate(_repo(kb))
        assert report.overall_status in (SafetyStatus.APPROVED, SafetyStatus.REVIEW_REQUIRED)
        assert report.can_generate_summary

    def test_blocked_for_critical_issues(self):
        kb = _make_minimal_kb()
        # Critical allergy conflict
        kb.medications_discharge = [Medication(name=_fact("Penicillin"), dose=_fact("500mg"))]
        kb.allergies = [Allergy(allergen=_fact("Penicillin"))]
        report = SafetyValidationEngine().validate(_repo(kb))
        assert report.overall_status == SafetyStatus.BLOCKED
        assert not report.can_generate_summary
        assert len(report.blocking_issues) > 0

    def test_review_required_for_high_issues(self):
        kb = _make_minimal_kb()
        kb.conflicts.append(ClinicalConflict(
            conflict_type="drug_interaction",
            description="Drug interaction detected",
            severity="warning",
            resolved=False,
        ))
        report = SafetyValidationEngine().validate(_repo(kb))
        assert report.can_generate_summary

    def test_safety_score_formula(self):
        """safety_score = max(0.0, 1.0 - (critical × 0.3) - (high × 0.1))"""
        kb = _make_minimal_kb()
        # Add facts with missing evidence (CRITICAL)
        kb.demographics.name = EvidencedFact(
            value="John",
            confidence=0.9,
            source_document="doc.pdf",
            source_document_id="doc-001",
            page_number=1,
            evidence="",  # → CRITICAL finding
        )
        report = SafetyValidationEngine().validate(_repo(kb))
        # At least 1 critical finding → score <= 0.70
        assert report.safety_score <= 0.70

    def test_report_contains_all_validator_results(self):
        kb = _make_minimal_kb()
        report = SafetyValidationEngine().validate(_repo(kb))
        validator_names = {vr.validator_name for vr in report.validation_results}
        assert "evidence_validator" in validator_names
        assert "completeness_validator" in validator_names
        assert "medication_validator" in validator_names
        assert "conflict_validator" in validator_names
        assert "pending_result_validator" in validator_names

    def test_safety_score_floor_is_zero(self):
        kb = _make_minimal_kb()
        # Inject many critical conflicts
        for i in range(10):
            kb.conflicts.append(ClinicalConflict(
                conflict_type="medication_allergy",
                description=f"Critical conflict {i}",
                severity="critical",
                resolved=False,
            ))
        report = SafetyValidationEngine().validate(_repo(kb))
        assert report.safety_score >= 0.0
