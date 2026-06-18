"""
Tests for LLMClinicalSafetyReviewer and SafetyValidationEngine.validate_with_llm_review().

Covers:
1. A well-formed LLM response is parsed into SafetyFinding/ReviewFlag
   objects with the correct severity/category/confidence/evidence mapping.
2. Only HIGH severity + High confidence findings require acknowledgment
   (per the review spec) — HIGH + Moderate confidence must NOT require it.
3. Findings with no evidence are dropped even if the model returns them
   (defense in depth for "never generate findings without evidence").
4. Groq failures (GroqUnavailableError, generic exception) and
   unparseable responses degrade to an empty, passing result instead of
   raising.
5. SafetyValidationEngine.validate_with_llm_review() merges the LLM
   findings into the same aggregate pool as the deterministic validators
   (HIGH findings push overall_status to REVIEW_REQUIRED, contribute to
   the safety_score formula, etc).
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.groq_provider.agent_client import GroqUnavailableError
from app.knowledge.models import (
    Allergy,
    Diagnosis,
    EvidencedFact,
    FollowUp,
    HospitalInfo,
    Medication,
    PatientDemographics,
    PatientKnowledgeBase,
)
from app.knowledge.repository import KnowledgeRepository
from app.models.enums import SafetySeverity
from app.safety.engine import SafetyValidationEngine
from app.safety.llm_reviewer import LLMClinicalSafetyReviewer
from app.safety.models import ReviewFlagCategory, SafetyStatus


def _fact(value: str) -> EvidencedFact:
    return EvidencedFact(
        value=value,
        confidence=0.9,
        source_document="test_doc.pdf",
        source_document_id="doc-001",
        page_number=1,
        evidence=f"Verbatim excerpt: {value}",
    )


def _minimal_kb(patient_id: str = "p-llm-1") -> KnowledgeRepository:
    kb = PatientKnowledgeBase(patient_id=patient_id)
    kb.demographics = PatientDemographics(name=_fact("Jane Roe"), mrn=_fact("MRN-9001"))
    kb.hospital_info = HospitalInfo(admission_date=_fact("2026-01-01"))
    kb.diagnoses = [Diagnosis(name=_fact("Community Acquired Pneumonia"), is_principal=True)]
    kb.medications_discharge = [Medication(name=_fact("Ceftriaxone"), dose=_fact("1g"))]
    kb.allergies = [Allergy(allergen=_fact("NKDA"), severity="none")]
    kb.hospital_course = _fact("Treated for CAP with IV antibiotics, improved.")
    kb.discharge_condition = _fact("Stable")
    kb.follow_ups = [FollowUp(instruction=_fact("Follow up with PCP in 1 week"))]

    repo = KnowledgeRepository(patient_id=patient_id)
    repo._kb = kb
    return repo


def _client_returning(payload: str) -> AsyncMock:
    client = AsyncMock()
    client.generate_content.return_value = payload
    return client


class TestLLMClinicalSafetyReviewer:
    @pytest.mark.asyncio
    async def test_parses_findings_with_correct_severity_category_and_evidence(self):
        payload = """{
            "findings": [
                {"severity": "HIGH", "category": "conflict", "title": "Allergy conflict",
                 "explanation": "Patient allergic to penicillin but prescribed amoxicillin",
                 "recommendation": "Discontinue amoxicillin", "confidence": "High",
                 "requires_acknowledgment": true,
                 "evidence": ["Allergy list: Penicillin", "Discharge meds: Amoxicillin 500mg"]},
                {"severity": "LOW", "category": "other", "title": "Diabetes meds",
                 "explanation": "No diabetes medication changes documented",
                 "recommendation": "No action required", "confidence": "Moderate",
                 "requires_acknowledgment": false,
                 "evidence": ["Discharge medication list unchanged from admission"]}
            ],
            "overall_safety_score": 70,
            "completeness_score": 80,
            "high_findings_count": 1, "medium_findings_count": 0,
            "low_findings_count": 1, "info_findings_count": 0
        }"""
        reviewer = LLMClinicalSafetyReviewer(_client_returning(payload))
        result = await reviewer.review(_minimal_kb())

        assert len(result.findings) == 2
        assert result.findings[0].severity == SafetySeverity.HIGH
        assert result.findings[0].confidence == "High"
        assert result.findings[0].evidence == ["Allergy list: Penicillin", "Discharge meds: Amoxicillin 500mg"]
        assert result.findings[1].severity == SafetySeverity.LOW
        assert result.review_flags[1].category == ReviewFlagCategory.OTHER
        assert result.severity == SafetySeverity.HIGH

    @pytest.mark.asyncio
    async def test_high_severity_requires_high_confidence_to_require_acknowledgment(self):
        payload = """{
            "findings": [
                {"severity": "HIGH", "category": "conflict", "title": "A",
                 "explanation": "high conf high sev", "recommendation": "act",
                 "confidence": "High", "evidence": ["lab result X"]},
                {"severity": "HIGH", "category": "conflict", "title": "B",
                 "explanation": "moderate conf high sev", "recommendation": "act",
                 "confidence": "Moderate", "evidence": ["lab result Y"]}
            ],
            "overall_safety_score": 50, "completeness_score": 50,
            "high_findings_count": 2, "medium_findings_count": 0,
            "low_findings_count": 0, "info_findings_count": 0
        }"""
        reviewer = LLMClinicalSafetyReviewer(_client_returning(payload))
        result = await reviewer.review(_minimal_kb())

        assert result.review_flags[0].requires_acknowledgment is True
        assert result.review_flags[1].requires_acknowledgment is False

    @pytest.mark.asyncio
    async def test_finding_without_evidence_is_dropped(self):
        """
        Defense in depth for "Never generate findings without evidence" /
        "If evidence is insufficient, generate no finding" — enforced in
        code, not just left to the model's compliance with the prompt.
        """
        payload = """{
            "findings": [
                {"severity": "HIGH", "category": "conflict", "title": "No evidence cited",
                 "explanation": "should be dropped", "recommendation": "n/a",
                 "confidence": "High", "evidence": []},
                {"severity": "HIGH", "category": "conflict", "title": "Has evidence",
                 "explanation": "should be kept", "recommendation": "act",
                 "confidence": "High", "evidence": ["medication list: Warfarin 5mg"]}
            ],
            "overall_safety_score": 60, "completeness_score": 60,
            "high_findings_count": 2, "medium_findings_count": 0,
            "low_findings_count": 0, "info_findings_count": 0
        }"""
        reviewer = LLMClinicalSafetyReviewer(_client_returning(payload))
        result = await reviewer.review(_minimal_kb())

        assert len(result.findings) == 1
        assert "Has evidence" in result.findings[0].description

    @pytest.mark.asyncio
    async def test_no_findings_when_response_is_empty_list(self):
        payload = '{"findings": [], "overall_safety_score": 100, "completeness_score": 100, "high_findings_count": 0, "medium_findings_count": 0, "low_findings_count": 0, "info_findings_count": 0}'
        reviewer = LLMClinicalSafetyReviewer(_client_returning(payload))
        result = await reviewer.review(_minimal_kb())

        assert result.findings == []
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_groq_unavailable_degrades_gracefully(self):
        client = AsyncMock()
        client.generate_content.side_effect = GroqUnavailableError("down")
        reviewer = LLMClinicalSafetyReviewer(client)
        result = await reviewer.review(_minimal_kb())

        assert result.passed is True
        assert result.findings == []
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_unparseable_response_degrades_gracefully(self):
        reviewer = LLMClinicalSafetyReviewer(_client_returning("not json at all"))
        result = await reviewer.review(_minimal_kb())

        assert result.passed is True
        assert result.findings == []
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_malformed_individual_finding_is_skipped_not_fatal(self):
        payload = """{
            "findings": [
                {"severity": "HIGH", "category": "conflict", "title": "Good",
                 "explanation": "fine", "recommendation": "act", "confidence": "High",
                 "evidence": ["citation"]},
                {"severity": "UNKNOWN_SEVERITY_VALUE"}
            ],
            "overall_safety_score": 60, "completeness_score": 60,
            "high_findings_count": 1, "medium_findings_count": 0,
            "low_findings_count": 0, "info_findings_count": 0
        }"""
        reviewer = LLMClinicalSafetyReviewer(_client_returning(payload))
        result = await reviewer.review(_minimal_kb())

        # The second entry has no "evidence" key at all, so it's dropped
        # by the evidence-required rule before severity parsing even
        # matters — only the well-formed finding survives.
        assert len(result.findings) == 1
        assert "Good" in result.findings[0].description


class TestSafetyValidationEngineLLMMerge:
    @pytest.mark.asyncio
    async def test_llm_high_finding_merges_into_overall_report(self):
        payload = """{
            "findings": [
                {"severity": "HIGH", "category": "conflict", "title": "Critical drug interaction",
                 "explanation": "Major interaction found", "recommendation": "Review with pharmacist",
                 "confidence": "High", "evidence": ["medication list: Warfarin + NSAID"]}
            ],
            "overall_safety_score": 40, "completeness_score": 80,
            "high_findings_count": 1, "medium_findings_count": 0,
            "low_findings_count": 0, "info_findings_count": 0
        }"""
        client = _client_returning(payload)
        engine = SafetyValidationEngine()
        report = await engine.validate_with_llm_review(_minimal_kb(), client)

        assert report.overall_status in (SafetyStatus.REVIEW_REQUIRED, SafetyStatus.BLOCKED)
        assert any(f.validator == "llm_clinical_reviewer" for f in report.safety_findings)
        assert any(flag.requires_acknowledgment for flag in report.review_flags if flag.severity == SafetySeverity.HIGH)

    @pytest.mark.asyncio
    async def test_llm_failure_does_not_break_deterministic_report(self):
        client = AsyncMock()
        client.generate_content.side_effect = Exception("network down")
        engine = SafetyValidationEngine()

        report = await engine.validate_with_llm_review(_minimal_kb(), client)

        assert report is not None
        assert report.patient_id == "p-llm-1"
