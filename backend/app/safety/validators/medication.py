from __future__ import annotations

from typing import List, Set

from app.knowledge.repository import KnowledgeRepository
from app.models.enums import SafetySeverity
from app.safety.models import (
    ReviewFlag, ReviewFlagCategory, SafetyFinding, SectionName, ValidationResult
)
from app.safety.validators.base import BaseValidator


class MedicationValidator(BaseValidator):
    """
    Clinical medication safety checks:

    1. Allergy-medication cross-check (CRITICAL)
    2. Discharge medication list existence (HIGH if missing)
    3. Medications with missing dose/route/frequency (MEDIUM)
    4. High-risk medications requiring special documentation
    """

    name = "medication_validator"

    # Medications that always require dose documentation
    _HIGH_RISK_MEDS = {
        "warfarin", "heparin", "insulin", "digoxin", "lithium",
        "methotrexate", "amiodarone", "vancomycin", "gentamicin",
        "phenytoin", "carbamazepine", "cyclosporine", "tacrolimus",
    }

    def validate(self, kb: KnowledgeRepository) -> ValidationResult:
        findings: List[SafetyFinding] = []
        flags: List[ReviewFlag] = []
        worst = SafetySeverity.INFO

        allergen_names: Set[str] = {
            a.allergen.value.lower() for a in kb.kb.allergies
            if a.allergen.value.upper() != "NKDA"
        }
        discharge_meds = kb.kb.medications_discharge

        # 1. Check for missing discharge medication list
        if not discharge_meds:
            finding = SafetyFinding(
                validator=self.name,
                severity=SafetySeverity.HIGH,
                description="No discharge medications documented in the knowledge base",
                affected_section=SectionName.DISCHARGE_MEDICATIONS,
            )
            findings.append(finding)
            flags.append(ReviewFlag(
                category=ReviewFlagCategory.MISSING_DATA,
                severity=SafetySeverity.HIGH,
                description="Discharge medication list is empty",
                affected_section=SectionName.DISCHARGE_MEDICATIONS,
                recommendation="Review source documents for discharge prescription information",
                requires_acknowledgment=True,
            ))
            worst = SafetySeverity.HIGH

        for med in discharge_meds:
            med_name_lower = med.name.value.lower()

            # 2. Allergy-medication cross-check
            for allergen in allergen_names:
                if allergen in med_name_lower or med_name_lower in allergen:
                    finding = SafetyFinding(
                        validator=self.name,
                        severity=SafetySeverity.CRITICAL,
                        description=(
                            f"ALLERGY CONFLICT: '{med.name.value}' is prescribed "
                            f"but patient has documented allergy to '{allergen}'"
                        ),
                        affected_section=SectionName.DISCHARGE_MEDICATIONS,
                        affected_items=[med.name.value, allergen],
                        source_documents=[med.name.source_document],
                    )
                    findings.append(finding)
                    flags.append(ReviewFlag(
                        category=ReviewFlagCategory.SAFETY_CONCERN,
                        severity=SafetySeverity.CRITICAL,
                        description=(
                            f"⚠ ALLERGY CONFLICT: {med.name.value} prescribed "
                            f"— patient allergic to {allergen}"
                        ),
                        affected_section=SectionName.DISCHARGE_MEDICATIONS,
                        recommendation=(
                            "IMMEDIATE REVIEW REQUIRED: Verify allergy status and "
                            "confirm prescription intent with prescribing physician"
                        ),
                        requires_acknowledgment=True,
                    ))
                    worst = SafetySeverity.CRITICAL

            # 3. High-risk med without dose
            for hr_med in self._HIGH_RISK_MEDS:
                if hr_med in med_name_lower and not med.dose:
                    finding = SafetyFinding(
                        validator=self.name,
                        severity=SafetySeverity.HIGH,
                        description=(
                            f"High-risk medication '{med.name.value}' has no documented dose"
                        ),
                        affected_section=SectionName.DISCHARGE_MEDICATIONS,
                        affected_items=[med.name.value],
                    )
                    findings.append(finding)
                    flags.append(ReviewFlag(
                        category=ReviewFlagCategory.MEDICATION_DISCREPANCY,
                        severity=SafetySeverity.HIGH,
                        description=f"High-risk med '{med.name.value}' missing dose documentation",
                        affected_section=SectionName.DISCHARGE_MEDICATIONS,
                        recommendation="Document exact dose before approving discharge summary",
                        requires_acknowledgment=True,
                    ))
                    if worst == SafetySeverity.INFO:
                        worst = SafetySeverity.HIGH
                    break

            # 4. Any med without dose/route (MEDIUM)
            if not med.dose and not med.is_discontinued:
                finding = SafetyFinding(
                    validator=self.name,
                    severity=SafetySeverity.MEDIUM,
                    description=f"Medication '{med.name.value}' has no documented dose",
                    affected_section=SectionName.DISCHARGE_MEDICATIONS,
                    affected_items=[med.name.value],
                )
                findings.append(finding)
                if worst == SafetySeverity.INFO:
                    worst = SafetySeverity.MEDIUM

        passed = worst not in (SafetySeverity.CRITICAL,)

        return ValidationResult(
            validator_name=self.name,
            passed=passed,
            severity=worst,
            findings=findings,
            review_flags=flags,
        )
