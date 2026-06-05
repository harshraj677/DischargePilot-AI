from __future__ import annotations

from typing import List, Optional

from app.agent.models import AgentRunResult
from app.knowledge.repository import KnowledgeRepository
from app.models.enums import SafetySeverity
from app.safety.models import (
    ReviewFlag,
    SafetyFinding,
    SafetyReport,
    SafetyStatus,
    ValidationResult,
)
from app.safety.review_flags import ReviewFlagGenerator
from app.safety.validators.completeness import CompletenessValidator
from app.safety.validators.conflict import ConflictValidator
from app.safety.validators.evidence import EvidenceValidator
from app.safety.validators.medication import MedicationValidator
from app.safety.validators.pending import PendingResultValidator
from app.utils.logging import AuditLogger, get_logger

logger = get_logger(__name__)
audit = AuditLogger(module="safety_engine")

# Safety score formula:
#   safety_score = max(0.0, 1.0 - (critical_count × 0.3) - (high_count × 0.1))
_CRITICAL_WEIGHT = 0.30
_HIGH_WEIGHT = 0.10


class SafetyValidationEngine:
    """
    Orchestrates all safety validators and produces a SafetyReport.

    The SafetyReport is the gate that determines whether discharge summary
    generation can proceed. BLOCKED → cannot generate. REVIEW_REQUIRED → can
    generate but clinician must acknowledge all flags.
    """

    def __init__(self) -> None:
        self._validators = [
            EvidenceValidator(),
            ConflictValidator(),
            MedicationValidator(),
            CompletenessValidator(),
            PendingResultValidator(),
        ]
        self._flag_generator = ReviewFlagGenerator()

    def validate(
        self,
        kb: KnowledgeRepository,
        agent_result: Optional[AgentRunResult] = None,
    ) -> SafetyReport:
        patient_id = kb.kb.patient_id
        run_id = agent_result.run_id if agent_result else "no-run"

        logger.info("Safety validation started", patient_id=patient_id, run_id=run_id)

        # Run all validators
        validation_results: List[ValidationResult] = []
        for validator in self._validators:
            result = validator.run(kb)
            validation_results.append(result)

        # Aggregate all findings and flags
        all_findings: List[SafetyFinding] = []
        all_flags: List[ReviewFlag] = []
        for vr in validation_results:
            all_findings.extend(vr.findings)
            all_flags.extend(vr.review_flags)

        # Generate cross-cutting flags
        extra_flags = self._flag_generator.generate(kb)
        all_flags.extend(extra_flags)

        # Compute safety score
        critical_count = sum(1 for f in all_findings if f.severity == SafetySeverity.CRITICAL)
        high_count = sum(1 for f in all_findings if f.severity == SafetySeverity.HIGH)
        safety_score = max(
            0.0,
            1.0 - (critical_count * _CRITICAL_WEIGHT) - (high_count * _HIGH_WEIGHT),
        )

        # Determine overall status
        if critical_count > 0:
            overall_status = SafetyStatus.BLOCKED
            can_generate = False
        elif high_count > 0 or len(all_flags) > 0:
            overall_status = SafetyStatus.REVIEW_REQUIRED
            can_generate = True
        else:
            overall_status = SafetyStatus.APPROVED
            can_generate = True

        # Collect blocking issues and warnings
        blocking_issues = [
            f.description for f in all_findings if f.severity == SafetySeverity.CRITICAL
        ]
        warnings = [
            f.description for f in all_findings if f.severity == SafetySeverity.HIGH
        ]

        report = SafetyReport(
            patient_id=patient_id,
            run_id=run_id,
            overall_status=overall_status,
            validation_results=validation_results,
            review_flags=all_flags,
            safety_findings=all_findings,
            can_generate_summary=can_generate,
            blocking_issues=blocking_issues,
            warnings=warnings,
            completeness_score=kb.completeness_score(),
            safety_score=safety_score,
        )

        audit.log(
            "safety_validation_completed",
            patient_id=patient_id,
            run_id=run_id,
            status=overall_status.value,
            safety_score=round(safety_score, 3),
            critical_count=critical_count,
            high_count=high_count,
            total_flags=len(all_flags),
            can_generate=can_generate,
        )

        logger.info(
            "Safety validation complete",
            patient_id=patient_id,
            status=overall_status.value,
            safety_score=f"{safety_score:.0%}",
            blocking=len(blocking_issues),
            flags=len(all_flags),
        )

        return report
