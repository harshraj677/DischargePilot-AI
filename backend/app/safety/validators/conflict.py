from __future__ import annotations

from typing import List

from app.knowledge.repository import KnowledgeRepository
from app.models.enums import SafetySeverity
from app.safety.models import (
    ReviewFlag, ReviewFlagCategory, SafetyFinding, SectionName, ValidationResult
)
from app.safety.validators.base import BaseValidator


class ConflictValidator(BaseValidator):
    """
    Validates that no unresolved clinical conflicts exist in the knowledge base.

    Checks:
    1. Unresolved critical conflicts from ConflictDetectionTool
    2. Duplicate diagnoses with conflicting ICD codes
    3. Duplicate medications with conflicting doses
    """

    name = "conflict_validator"

    def validate(self, kb: KnowledgeRepository) -> ValidationResult:
        findings: List[SafetyFinding] = []
        flags: List[ReviewFlag] = []
        worst = SafetySeverity.INFO

        # 1. Check unresolved KB conflicts from agent run
        for conflict in kb.kb.conflicts:
            if conflict.resolved:
                continue

            sev = (
                SafetySeverity.CRITICAL
                if conflict.severity == "critical"
                else SafetySeverity.HIGH
            )
            finding = SafetyFinding(
                validator=self.name,
                severity=sev,
                description=f"Unresolved {conflict.conflict_type}: {conflict.description}",
                affected_section=_conflict_to_section(conflict.conflict_type),
                affected_items=conflict.involved_items,
            )
            findings.append(finding)
            flags.append(ReviewFlag(
                category=ReviewFlagCategory.CONFLICT,
                severity=sev,
                description=f"Unresolved conflict: {conflict.description[:120]}",
                affected_section=_conflict_to_section(conflict.conflict_type),
                recommendation=(
                    "This conflict requires clinician review. "
                    "Do not approve the summary until this is addressed."
                ),
                requires_acknowledgment=True,
            ))
            if sev == SafetySeverity.CRITICAL:
                worst = SafetySeverity.CRITICAL
            elif worst != SafetySeverity.CRITICAL:
                worst = SafetySeverity.HIGH

        # 2. Duplicate diagnoses check (same name, different ICD codes)
        dx_names: dict = {}
        for dx in kb.kb.diagnoses:
            name_lower = dx.name.value.lower()
            if name_lower in dx_names:
                prev = dx_names[name_lower]
                if dx.icd_code and prev.icd_code and dx.icd_code != prev.icd_code:
                    finding = SafetyFinding(
                        validator=self.name,
                        severity=SafetySeverity.MEDIUM,
                        description=(
                            f"Diagnosis '{dx.name.value}' has conflicting ICD codes: "
                            f"{prev.icd_code} vs {dx.icd_code}"
                        ),
                        affected_section=SectionName.PRINCIPAL_DIAGNOSIS,
                        affected_items=[dx.name.value],
                    )
                    findings.append(finding)
                    if worst == SafetySeverity.INFO:
                        worst = SafetySeverity.MEDIUM
            else:
                dx_names[name_lower] = dx

        # 3. Duplicate discharge medications with conflicting doses
        med_names: dict = {}
        for med in kb.kb.medications_discharge:
            name_lower = med.name.value.lower()
            if name_lower in med_names:
                prev = med_names[name_lower]
                prev_dose = prev.dose.value if prev.dose else None
                curr_dose = med.dose.value if med.dose else None
                if prev_dose and curr_dose and prev_dose != curr_dose:
                    finding = SafetyFinding(
                        validator=self.name,
                        severity=SafetySeverity.HIGH,
                        description=(
                            f"Medication '{med.name.value}' appears with conflicting doses: "
                            f"'{prev_dose}' vs '{curr_dose}'"
                        ),
                        affected_section=SectionName.DISCHARGE_MEDICATIONS,
                        affected_items=[med.name.value],
                    )
                    findings.append(finding)
                    flags.append(ReviewFlag(
                        category=ReviewFlagCategory.MEDICATION_DISCREPANCY,
                        severity=SafetySeverity.HIGH,
                        description=f"Conflicting doses for {med.name.value}: {prev_dose} / {curr_dose}",
                        affected_section=SectionName.DISCHARGE_MEDICATIONS,
                        recommendation="Verify correct discharge dose with the prescribing physician",
                        requires_acknowledgment=True,
                    ))
                    if worst == SafetySeverity.INFO:
                        worst = SafetySeverity.HIGH
            else:
                med_names[name_lower] = med

        passed = worst not in (SafetySeverity.CRITICAL, SafetySeverity.HIGH)

        return ValidationResult(
            validator_name=self.name,
            passed=passed,
            severity=worst,
            findings=findings,
            review_flags=flags,
        )


def _conflict_to_section(conflict_type: str) -> SectionName:
    mapping = {
        "medication_allergy": SectionName.DISCHARGE_MEDICATIONS,
        "drug_interaction": SectionName.DISCHARGE_MEDICATIONS,
        "contraindication": SectionName.DISCHARGE_MEDICATIONS,
        "missing_medication": SectionName.DISCHARGE_MEDICATIONS,
        "critical_lab": SectionName.LAB_RESULTS,
        "diagnosis_conflict": SectionName.PRINCIPAL_DIAGNOSIS,
    }
    return mapping.get(conflict_type, SectionName.GLOBAL)
