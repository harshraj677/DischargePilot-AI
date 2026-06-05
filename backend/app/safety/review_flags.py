from __future__ import annotations

from typing import List

from app.knowledge.repository import KnowledgeRepository
from app.models.enums import SafetySeverity
from app.safety.models import ReviewFlag, ReviewFlagCategory, SectionName


class ReviewFlagGenerator:
    """
    Generates additional review flags from the knowledge base that are not
    covered by individual validators (cross-cutting concerns, summary-level flags).

    These flags supplement (not replace) validator flags.
    """

    def generate(self, kb: KnowledgeRepository) -> List[ReviewFlag]:
        flags: List[ReviewFlag] = []
        flags.extend(self._medication_change_flags(kb))
        flags.extend(self._multiple_conflicts_flag(kb))
        flags.extend(self._critical_condition_flag(kb))
        return flags

    def _medication_change_flags(self, kb: KnowledgeRepository) -> List[ReviewFlag]:
        """Flag each medication that was changed at discharge — these need explicit reconciliation."""
        flags = []
        for med in kb.kb.medications_discharge:
            if med.is_changed_at_discharge:
                reason_text = f" (Reason: {med.change_reason})" if med.change_reason else ""
                flags.append(ReviewFlag(
                    category=ReviewFlagCategory.MEDICATION_DISCREPANCY,
                    severity=SafetySeverity.MEDIUM,
                    description=(
                        f"Medication '{med.name.value}' was changed at discharge{reason_text}"
                    ),
                    affected_section=SectionName.MEDICATION_CHANGES,
                    recommendation=(
                        "Verify this change is documented in the medication changes section "
                        "and the reason is clear to the receiving provider"
                    ),
                    requires_acknowledgment=False,
                ))
        for med in kb.kb.medications_discharge:
            if med.is_discontinued:
                flags.append(ReviewFlag(
                    category=ReviewFlagCategory.MEDICATION_DISCREPANCY,
                    severity=SafetySeverity.MEDIUM,
                    description=f"Medication '{med.name.value}' was discontinued at discharge",
                    affected_section=SectionName.MEDICATION_CHANGES,
                    recommendation=(
                        "Confirm discontinuation reason is documented and appropriate"
                    ),
                    requires_acknowledgment=False,
                ))
        return flags

    def _multiple_conflicts_flag(self, kb: KnowledgeRepository) -> List[ReviewFlag]:
        """When 3+ conflicts are unresolved, add a global summary flag."""
        unresolved = [c for c in kb.kb.conflicts if not c.resolved]
        if len(unresolved) >= 3:
            return [ReviewFlag(
                category=ReviewFlagCategory.CONFLICT,
                severity=SafetySeverity.HIGH,
                description=f"{len(unresolved)} unresolved clinical conflicts detected",
                affected_section=SectionName.GLOBAL,
                recommendation=(
                    "Review all flagged conflicts before approving this summary. "
                    "A high conflict count suggests significant clinical complexity."
                ),
                requires_acknowledgment=True,
            )]
        return []

    def _critical_condition_flag(self, kb: KnowledgeRepository) -> List[ReviewFlag]:
        """If discharge condition is critical/poor, add a summary-level warning."""
        condition = kb.kb.discharge_condition
        if not condition:
            return []
        condition_lower = condition.value.lower()
        if any(w in condition_lower for w in ("critical", "poor", "guarded", "unstable")):
            return [ReviewFlag(
                category=ReviewFlagCategory.SAFETY_CONCERN,
                severity=SafetySeverity.HIGH,
                description=(
                    f"Patient discharged in '{condition.value}' condition — "
                    "ensure safety of discharge decision is documented"
                ),
                affected_section=SectionName.DISCHARGE_CONDITION,
                recommendation=(
                    "Verify that the discharge plan adequately addresses the patient's condition "
                    "and that appropriate follow-up is in place"
                ),
                requires_acknowledgment=True,
            )]
        return []
