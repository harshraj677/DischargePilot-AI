from __future__ import annotations

from typing import List

from app.knowledge.repository import KnowledgeRepository
from app.models.enums import SafetySeverity
from app.safety.models import (
    ReviewFlag, ReviewFlagCategory, SafetyFinding, SectionName, ValidationResult
)
from app.safety.validators.base import BaseValidator


class PendingResultValidator(BaseValidator):
    """
    Validates pending investigation handling:

    1. Pending results MUST be documented in the summary (never omitted)
    2. Each pending result should have a responsible follow-up instruction
    3. Critical lab values that are still pending require escalation
    """

    name = "pending_result_validator"

    # Keywords that imply critical significance
    _CRITICAL_KEYWORDS = {
        "culture", "biopsy", "pathology", "malignancy", "cancer",
        "hiv", "hepatitis", "mrsa", "blood culture", "csf",
        "sensitivity", "resistance",
    }

    def validate(self, kb: KnowledgeRepository) -> ValidationResult:
        findings: List[SafetyFinding] = []
        flags: List[ReviewFlag] = []
        worst = SafetySeverity.INFO

        pending = kb.kb.pending_results

        if not pending:
            return ValidationResult(
                validator_name=self.name,
                passed=True,
                severity=SafetySeverity.INFO,
                findings=[],
                review_flags=[],
            )

        # Check each pending result
        for pr in pending:
            desc_lower = pr.description.value.lower()
            is_critical = any(kw in desc_lower for kw in self._CRITICAL_KEYWORDS)

            sev = SafetySeverity.HIGH if is_critical else SafetySeverity.MEDIUM

            finding = SafetyFinding(
                validator=self.name,
                severity=sev,
                description=f"Pending result not resolved: {pr.description.value[:100]}",
                affected_section=SectionName.PENDING_RESULTS,
                affected_items=[pr.description.value],
                source_documents=[pr.description.source_document],
            )
            findings.append(finding)

            flags.append(ReviewFlag(
                category=ReviewFlagCategory.PENDING_RESULT,
                severity=sev,
                description=f"Pending at discharge: {pr.description.value[:120]}",
                affected_section=SectionName.PENDING_RESULTS,
                recommendation=(
                    (
                        "Critical pending result — ensure follow-up plan is explicitly documented "
                        "and patient has been counselled on what to do if result is abnormal."
                    ) if is_critical else (
                        "Ensure this pending result is included in the follow-up instructions "
                        "and the patient or primary care provider will receive results."
                    )
                ),
                requires_acknowledgment=is_critical,
                source_documents=[pr.description.source_document],
            ))

            if sev == SafetySeverity.HIGH and worst != SafetySeverity.CRITICAL:
                worst = SafetySeverity.HIGH
            elif sev == SafetySeverity.MEDIUM and worst == SafetySeverity.INFO:
                worst = SafetySeverity.MEDIUM

        # Also flag critical lab results
        critical_labs = [l for l in kb.kb.lab_results if l.is_critical]
        for lab in critical_labs:
            finding = SafetyFinding(
                validator=self.name,
                severity=SafetySeverity.HIGH,
                description=(
                    f"Critical lab value: {lab.test_name.value} = {lab.value.value}"
                    + (f" {lab.unit}" if lab.unit else "")
                ),
                affected_section=SectionName.LAB_RESULTS,
                affected_items=[lab.test_name.value],
                source_documents=[lab.test_name.source_document],
            )
            findings.append(finding)
            flags.append(ReviewFlag(
                category=ReviewFlagCategory.SAFETY_CONCERN,
                severity=SafetySeverity.HIGH,
                description=f"Critical lab at discharge: {lab.test_name.value} = {lab.value.value}",
                affected_section=SectionName.LAB_RESULTS,
                recommendation=(
                    "Verify patient was informed of critical lab result. "
                    "Ensure appropriate action was taken."
                ),
                requires_acknowledgment=True,
            ))
            if worst != SafetySeverity.CRITICAL:
                worst = SafetySeverity.HIGH

        passed = worst == SafetySeverity.INFO

        return ValidationResult(
            validator_name=self.name,
            passed=passed,
            severity=worst,
            findings=findings,
            review_flags=flags,
        )
