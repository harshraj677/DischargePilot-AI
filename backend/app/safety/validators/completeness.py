from __future__ import annotations

from typing import List, Tuple

from app.knowledge.repository import KnowledgeRepository
from app.models.enums import SafetySeverity
from app.safety.models import (
    ReviewFlag, ReviewFlagCategory, SafetyFinding, SectionName, ValidationResult
)
from app.safety.validators.base import BaseValidator

# (field_description, section, severity_if_missing, requires_ack)
_REQUIRED_FIELDS: List[Tuple[str, SectionName, SafetySeverity, bool]] = [
    ("Patient name",             SectionName.DEMOGRAPHICS,         SafetySeverity.HIGH,     True),
    ("Patient MRN",              SectionName.DEMOGRAPHICS,         SafetySeverity.HIGH,     True),
    ("Admission date",           SectionName.HOSPITAL_INFO,        SafetySeverity.HIGH,     True),
    ("Principal diagnosis",      SectionName.PRINCIPAL_DIAGNOSIS,  SafetySeverity.HIGH,     True),
    ("Discharge medications",    SectionName.DISCHARGE_MEDICATIONS,SafetySeverity.HIGH,     True),
    ("Allergy status",           SectionName.ALLERGIES,            SafetySeverity.HIGH,     True),
    ("Hospital course",          SectionName.HOSPITAL_COURSE,      SafetySeverity.MEDIUM,   True),
    ("Discharge condition",      SectionName.DISCHARGE_CONDITION,  SafetySeverity.MEDIUM,   True),
    ("Follow-up instructions",   SectionName.FOLLOW_UP,            SafetySeverity.MEDIUM,   False),
]


class CompletenessValidator(BaseValidator):
    """
    Checks that all critical fields required for a discharge summary exist in the KB.

    Missing critical fields (HIGH severity) block summary approval.
    Missing preferred fields (MEDIUM severity) generate review flags.
    """

    name = "completeness_validator"

    def validate(self, kb: KnowledgeRepository) -> ValidationResult:
        findings: List[SafetyFinding] = []
        flags: List[ReviewFlag] = []
        worst = SafetySeverity.INFO

        present_map = {
            "Patient name":           kb.kb.demographics.name is not None,
            "Patient MRN":            kb.kb.demographics.mrn is not None,
            "Admission date":         kb.kb.hospital_info.admission_date is not None,
            "Principal diagnosis":    any(d.is_principal for d in kb.kb.diagnoses),
            "Discharge medications":  len(kb.kb.medications_discharge) > 0,
            "Allergy status":         len(kb.kb.allergies) > 0,
            "Hospital course":        kb.kb.hospital_course is not None,
            "Discharge condition":    kb.kb.discharge_condition is not None,
            "Follow-up instructions": len(kb.kb.follow_ups) > 0,
        }

        for field_name, section, severity, requires_ack in _REQUIRED_FIELDS:
            if present_map.get(field_name, False):
                continue

            finding = SafetyFinding(
                validator=self.name,
                severity=severity,
                description=f"Required field missing: {field_name}",
                affected_section=section,
                affected_items=[field_name],
            )
            findings.append(finding)

            flags.append(ReviewFlag(
                category=ReviewFlagCategory.MISSING_DATA,
                severity=severity,
                description=f"{field_name} is not documented in the source records",
                affected_section=section,
                recommendation=(
                    f"Locate and document {field_name} from source records, "
                    "or explicitly mark as 'Not documented'"
                ),
                requires_acknowledgment=requires_ack,
            ))

            if severity == SafetySeverity.HIGH:
                if worst != SafetySeverity.CRITICAL:
                    worst = SafetySeverity.HIGH
            elif severity == SafetySeverity.MEDIUM and worst == SafetySeverity.INFO:
                worst = SafetySeverity.MEDIUM

        passed = worst not in (SafetySeverity.CRITICAL, SafetySeverity.HIGH)

        return ValidationResult(
            validator_name=self.name,
            passed=passed,
            severity=worst,
            findings=findings,
            review_flags=flags,
        )
