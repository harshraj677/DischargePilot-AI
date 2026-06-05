from __future__ import annotations

from typing import List

from app.knowledge.models import EvidencedFact
from app.knowledge.repository import KnowledgeRepository, _iter_all_facts
from app.models.enums import SafetySeverity
from app.safety.models import (
    ReviewFlag, ReviewFlagCategory, SafetyFinding, SectionName, ValidationResult
)
from app.safety.validators.base import BaseValidator

_LOW_CONFIDENCE_THRESHOLD = 0.60
_MIN_EVIDENCE_LENGTH = 5


class EvidenceValidator(BaseValidator):
    """
    Validates that every clinical fact in the knowledge base has:
    1. A non-empty evidence excerpt
    2. A source document reference
    3. A plausible page number (>= 1)
    4. A confidence score >= threshold

    Facts failing any check are flagged for clinician review.
    Facts with missing evidence are CRITICAL — they cannot appear in the summary.
    """

    name = "evidence_validator"

    def validate(self, kb: KnowledgeRepository) -> ValidationResult:
        findings: List[SafetyFinding] = []
        flags: List[ReviewFlag] = []
        worst = SafetySeverity.INFO

        for category, fact in _iter_all_facts(kb.kb):
            section = _category_to_section(category)

            # Check 1: evidence must be present
            if not fact.evidence or len(fact.evidence.strip()) < _MIN_EVIDENCE_LENGTH:
                finding = SafetyFinding(
                    validator=self.name,
                    severity=SafetySeverity.CRITICAL,
                    description=f"Clinical fact '{fact.value[:60]}' has no source evidence",
                    affected_section=section,
                    affected_items=[fact.value],
                    source_documents=[fact.source_document],
                )
                findings.append(finding)
                flags.append(ReviewFlag(
                    category=ReviewFlagCategory.UNSUPPORTED_CLAIM,
                    severity=SafetySeverity.CRITICAL,
                    description=f"Fact '{fact.value[:60]}' in {section.value} lacks evidence",
                    affected_section=section,
                    recommendation="Verify this claim manually before approving the summary",
                    source_documents=[fact.source_document],
                ))
                worst = SafetySeverity.CRITICAL

            # Check 2: source document must be present
            elif not fact.source_document:
                finding = SafetyFinding(
                    validator=self.name,
                    severity=SafetySeverity.HIGH,
                    description=f"Fact '{fact.value[:60]}' has no source document reference",
                    affected_section=section,
                    affected_items=[fact.value],
                )
                findings.append(finding)
                if worst not in (SafetySeverity.CRITICAL,):
                    worst = SafetySeverity.HIGH

            # Check 3: low confidence
            elif fact.confidence < _LOW_CONFIDENCE_THRESHOLD:
                finding = SafetyFinding(
                    validator=self.name,
                    severity=SafetySeverity.MEDIUM,
                    description=(
                        f"Low-confidence fact ({fact.confidence:.0%}): "
                        f"'{fact.value[:60]}' in {section.value}"
                    ),
                    affected_section=section,
                    affected_items=[fact.value],
                    evidence=fact.short_evidence(),
                    source_documents=[fact.source_document],
                )
                findings.append(finding)
                flags.append(ReviewFlag(
                    category=ReviewFlagCategory.LOW_CONFIDENCE,
                    severity=SafetySeverity.MEDIUM,
                    description=f"Low confidence ({fact.confidence:.0%}) for: {fact.value[:80]}",
                    affected_section=section,
                    recommendation="Verify this value in the source document",
                    source_documents=[fact.source_document],
                    requires_acknowledgment=False,
                ))
                if worst == SafetySeverity.INFO:
                    worst = SafetySeverity.MEDIUM

            # Check 4: invalid page number
            elif fact.page_number < 1:
                finding = SafetyFinding(
                    validator=self.name,
                    severity=SafetySeverity.MEDIUM,
                    description=f"Invalid page number ({fact.page_number}) for '{fact.value[:60]}'",
                    affected_section=section,
                    affected_items=[fact.value],
                    source_documents=[fact.source_document],
                )
                findings.append(finding)

        passed = not any(f.severity == SafetySeverity.CRITICAL for f in findings)

        return ValidationResult(
            validator_name=self.name,
            passed=passed,
            severity=worst,
            findings=findings,
            review_flags=flags,
        )


def _category_to_section(category: str) -> SectionName:
    mapping = {
        "demographics": SectionName.DEMOGRAPHICS,
        "hospital_info": SectionName.HOSPITAL_INFO,
        "diagnosis": SectionName.PRINCIPAL_DIAGNOSIS,
        "medication": SectionName.DISCHARGE_MEDICATIONS,
        "allergy": SectionName.ALLERGIES,
        "procedure": SectionName.PROCEDURES,
        "lab": SectionName.LAB_RESULTS,
        "followup": SectionName.FOLLOW_UP,
        "pending_result": SectionName.PENDING_RESULTS,
        "hospital_course": SectionName.HOSPITAL_COURSE,
        "discharge_condition": SectionName.DISCHARGE_CONDITION,
    }
    for prefix, section in mapping.items():
        if category.startswith(prefix):
            return section
    return SectionName.GLOBAL
