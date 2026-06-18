from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional

from app.groq_provider.agent_client import GroqAgentClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.mongodb import mongodb_manager
from app.db.models import DischargeReport, Document, Patient
from app.knowledge.repository import KnowledgeRepository
from app.models.mongo.document import DocumentMongo
from app.models.mongo.finding import FindingMongo
from app.models.mongo.patient import PatientMongo
from app.models.mongo.summary import SummaryMongo
from app.repositories.document_repository import DocumentRepository
from app.repositories.finding_repository import FindingRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.summary_repository import SummaryRepository
from app.safety.models import ReviewFlag, SafetyFinding, SafetyReport
from app.summary.formatter import format_as_text
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

    def __init__(self, db: Session, client: GroqAgentClient, settings: Settings) -> None:
        self._db = db
        self._generator = DischargeSummaryGenerator(client, settings)

    async def generate_and_persist(
        self,
        patient_id: str,
        run_id: str,
        kb: KnowledgeRepository,
        safety_report: SafetyReport,
    ) -> DischargeSummary:
        """
        Generate discharge summary and save it to DischargeReport table.

        Escalation must never bypass SummaryGenerator — this no longer
        refuses to generate when the safety gate is BLOCKED (critical
        findings still ride along as review_flags on the persisted summary).
        """
        print("SUMMARY_GENERATOR_STARTED", flush=True)
        logger.info("SUMMARY_GENERATOR_STARTED", patient_id=patient_id, run_id=run_id)

        summary = await self._generator.generate(kb, safety_report, run_id)

        print("SUMMARY_GENERATOR_COMPLETED", flush=True)
        logger.info(
            "SUMMARY_GENERATOR_COMPLETED",
            patient_id=patient_id,
            run_id=run_id,
            summary_id=summary.summary_id,
        )

        self._persist(patient_id, run_id, summary, safety_report)
        await self._persist_to_mongo(patient_id, run_id, summary, safety_report)

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
        # NOTE: model_dump() (no mode="json") leaves datetime fields
        # (generated_at, etc.) as raw Python datetime objects, which
        # json.dumps() cannot serialize — this raised TypeError and aborted
        # before db.commit() ever ran, so no DischargeReport was ever saved.
        # mode="json" recursively converts datetimes (and other non-JSON
        # types) to JSON-safe values first.
        report = DischargeReport(
            patient_id=patient_id,
            agent_run_id=run_id,
            status=summary.status.value,
            summary_json=json.dumps(summary.model_dump(mode="json")),
            safety_report_json=json.dumps(safety_report.model_dump(mode="json")),
            completeness_score=summary.completeness_score,
            safety_score=summary.safety_score,
        )
        self._db.add(report)
        self._db.commit()
        self._db.refresh(report)
        print(f"SUMMARY SAVED FOR PATIENT {patient_id}", flush=True)
        logger.info(
            f"SUMMARY SAVED FOR PATIENT {patient_id}",
            patient_id=patient_id,
            run_id=run_id,
            report_id=report.id,
            summary_id=summary.summary_id,
        )
        logger.info("DischargeReport persisted", report_id=report.id, run_id=run_id)

    async def _persist_to_mongo(
        self,
        patient_id: str,
        run_id: str,
        summary: DischargeSummary,
        safety_report: SafetyReport,
    ) -> None:
        """
        Permanent-storage mirror of the SQLite DischargeReport (Phase 1).

        Best-effort and additive: MongoDB being unavailable must never break
        the SQLite-backed generation flow above, which has already committed
        by the time this runs.
        """
        db = mongodb_manager.get_database()
        if db is None:
            return

        try:
            patient_row = self._db.get(Patient, patient_id)
            if patient_row is not None:
                await PatientRepository(db).upsert(PatientMongo(
                    id=patient_row.id,
                    patient_id=patient_row.id,
                    name=f"{patient_row.first_name} {patient_row.last_name}".strip(),
                    mrn=patient_row.mrn,
                    dob=patient_row.date_of_birth,
                    gender=patient_row.gender,
                ))

            document_rows = list(
                self._db.execute(select(Document).where(Document.patient_id == patient_id)).scalars()
            )
            document_repo = DocumentRepository(db)
            for doc_row in document_rows:
                await document_repo.upsert(DocumentMongo(
                    id=doc_row.id,
                    patient_id=doc_row.patient_id,
                    document_type=doc_row.document_type,
                    content=doc_row.extracted_text,
                ))

            severity_counts = self._count_findings_by_severity(safety_report.review_flags)
            await SummaryRepository(db).create(SummaryMongo(
                id=summary.summary_id,
                patient_id=patient_id,
                summary_text=format_as_text(summary),
                status=summary.status.value,
                overall_safety_score=summary.safety_score,
                completeness_score=summary.completeness_score,
                high_findings_count=severity_counts["HIGH"],
                medium_findings_count=severity_counts["MEDIUM"],
                low_findings_count=severity_counts["LOW"],
                info_findings_count=severity_counts["INFO"],
            ))

            findings = self._findings_from_review_flags(
                summary.summary_id, safety_report.review_flags, safety_report.safety_findings
            )
            await FindingRepository(db).create_many(findings)

            logger.info(
                "Mongo persistence completed",
                patient_id=patient_id,
                run_id=run_id,
                summary_id=summary.summary_id,
                findings_saved=len(findings),
            )
        except Exception as exc:
            logger.error(
                "Mongo persistence failed",
                error=str(exc),
                patient_id=patient_id,
                run_id=run_id,
            )

    @staticmethod
    def _count_findings_by_severity(flags: List[ReviewFlag]) -> Dict[str, int]:
        counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        for flag in flags:
            severity = flag.severity.value
            # No dedicated "critical" bucket in the dashboard summary schema —
            # critical findings are the most severe, so they roll into "high".
            if severity == "CRITICAL":
                counts["HIGH"] += 1
            elif severity in counts:
                counts[severity] += 1
        return counts

    @staticmethod
    def _findings_from_review_flags(
        summary_id: str,
        flags: List[ReviewFlag],
        safety_findings: List[SafetyFinding],
    ) -> List[FindingMongo]:
        # ReviewFlag (clinician-facing, has requires_acknowledgment) and
        # SafetyFinding (validator-facing, has confidence/evidence) describe
        # the same underlying issues but aren't linked by a shared id — match
        # them best-effort on description text to recover confidence/evidence.
        findings_by_description = {f.description: f for f in safety_findings}

        results: List[FindingMongo] = []
        for flag in flags:
            matched = findings_by_description.get(flag.description)
            results.append(FindingMongo(
                id=flag.flag_id,
                summary_id=summary_id,
                severity=flag.severity.value,
                category=flag.category.value,
                title=flag.description[:120],
                explanation=flag.description,
                recommendation=flag.recommendation,
                confidence=matched.confidence if matched else "Moderate",
                requires_acknowledgment=flag.requires_acknowledgment,
                evidence=matched.evidence if matched else [],
            ))
        return results
