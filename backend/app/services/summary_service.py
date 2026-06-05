from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from anthropic import AsyncAnthropic
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import DischargeReport
from app.knowledge.repository import KnowledgeRepository
from app.safety.models import SafetyReport
from app.summary.generator import DischargeSummaryGenerator
from app.summary.models import DischargeSummary, DischargeSummaryStatus
from app.utils.logging import AuditLogger, get_logger

logger = get_logger(__name__)
audit = AuditLogger(module="summary_service")


class SummaryService:
    """
    Service layer for discharge summary generation and persistence.

    Wraps DischargeSummaryGenerator, persisting the result in DischargeReport.
    """

    def __init__(self, db: Session, client: AsyncAnthropic, settings: Settings) -> None:
        self._db = db
        self._generator = DischargeSummaryGenerator(client, settings)

    async def generate_and_persist(
        self,
        patient_id: str,
        run_id: str,
        kb: KnowledgeRepository,
        safety_report: SafetyReport,
    ) -> DischargeSummary:
        """Generate discharge summary and save it to DischargeReport table."""

        if not safety_report.can_generate_summary:
            raise ValueError(
                f"Safety gate blocked summary generation for run {run_id}. "
                f"Issues: {safety_report.blocking_issues}"
            )

        logger.info("Generating discharge summary", patient_id=patient_id, run_id=run_id)
        summary = await self._generator.generate(kb, safety_report, run_id)

        self._persist(patient_id, run_id, summary, safety_report)

        audit.log(
            "summary_generated_and_persisted",
            patient_id=patient_id,
            run_id=run_id,
            summary_id=summary.summary_id,
            safety_score=round(summary.safety_score, 3),
            completeness=round(summary.completeness_score, 3),
            flags=len(summary.review_flags),
        )
        return summary

    def get_report(self, run_id: str) -> Optional[DischargeReport]:
        return (
            self._db.query(DischargeReport)
            .filter(DischargeReport.agent_run_id == run_id)
            .order_by(DischargeReport.created_at.desc())
            .first()
        )

    def get_summary_for_run(self, run_id: str) -> Optional[DischargeSummary]:
        report = self.get_report(run_id)
        if not report or not report.summary_json:
            return None
        data = json.loads(report.summary_json)
        return DischargeSummary.model_validate(data)

    def approve_summary(self, run_id: str, approved_by: str) -> bool:
        report = self.get_report(run_id)
        if not report:
            return False
        report.status = DischargeSummaryStatus.APPROVED.value
        report.approved_by = approved_by
        report.approved_at = datetime.utcnow()
        self._db.commit()
        audit.log("summary_approved", run_id=run_id, approved_by=approved_by)
        return True

    def reject_summary(self, run_id: str, reason: str) -> bool:
        report = self.get_report(run_id)
        if not report:
            return False
        report.status = DischargeSummaryStatus.REJECTED.value
        report.rejection_reason = reason
        self._db.commit()
        audit.log("summary_rejected", run_id=run_id, reason=reason[:200])
        return True

    # ── Private ────────────────────────────────────────────────────────────────

    def _persist(
        self,
        patient_id: str,
        run_id: str,
        summary: DischargeSummary,
        safety_report: SafetyReport,
    ) -> None:
        report = DischargeReport(
            patient_id=patient_id,
            agent_run_id=run_id,
            status=summary.status.value,
            summary_json=json.dumps(summary.model_dump()),
            safety_report_json=json.dumps(safety_report.model_dump()),
            completeness_score=summary.completeness_score,
            safety_score=summary.safety_score,
        )
        self._db.add(report)
        self._db.commit()
        self._db.refresh(report)
        logger.info("DischargeReport persisted", report_id=report.id, run_id=run_id)
