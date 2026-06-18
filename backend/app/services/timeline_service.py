from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.repositories.document_repository import DocumentRepository
from app.repositories.finding_repository import FindingRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.review_repository import ReviewRepository
from app.repositories.summary_repository import SummaryRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class TimelineEvent(BaseModel):
    type: str
    timestamp: datetime
    title: str
    description: Optional[str] = None
    severity: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PatientTimelineInfo(BaseModel):
    id: str
    name: str
    mrn: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    created_at: datetime


class PatientTimelineResponse(BaseModel):
    patient: PatientTimelineInfo
    latest_safety_score: Optional[float] = None
    latest_completeness_score: Optional[float] = None
    events: List[TimelineEvent]


class TimelineService:
    """Assembles a patient's full clinical-review timeline from the Phase 1 Mongo collections."""

    def __init__(self, db: Optional[AsyncIOMotorDatabase]):
        self._patients = PatientRepository(db)
        self._documents = DocumentRepository(db)
        self._summaries = SummaryRepository(db)
        self._findings = FindingRepository(db)
        self._reviews = ReviewRepository(db)

    async def get_patient_timeline(self, patient_id: str) -> Optional[PatientTimelineResponse]:
        patient = await self._patients.get_by_id(patient_id)
        if patient is None:
            return None

        events: List[TimelineEvent] = [TimelineEvent(
            type="patient_created",
            timestamp=patient.created_at,
            title="Patient record created",
            description=patient.name,
        )]

        for doc in await self._documents.list_for_patient(patient_id):
            events.append(TimelineEvent(
                type="document_uploaded",
                timestamp=doc.created_at,
                title=f"Document uploaded: {doc.document_type}",
                metadata={"document_id": doc.id},
            ))

        summaries = await self._summaries.list_for_patient(patient_id)
        for summary in summaries:
            events.append(TimelineEvent(
                type="summary_generated",
                timestamp=summary.created_at,
                title="Discharge summary generated",
                description=summary.status,
                metadata={
                    "summary_id": summary.id,
                    "safety_score": summary.overall_safety_score,
                    "completeness_score": summary.completeness_score,
                },
            ))

            for finding in await self._findings.get_by_summary_id(summary.id):
                events.append(TimelineEvent(
                    type="finding_created",
                    timestamp=finding.created_at,
                    title=finding.title,
                    description=finding.explanation,
                    severity=finding.severity,
                    metadata={"finding_id": finding.id, "category": finding.category},
                ))

                for action in await self._reviews.list_by_finding(finding.id):
                    events.append(TimelineEvent(
                        type=f"finding_{action.action.value.lower()}",
                        timestamp=action.timestamp,
                        title=f"{action.action.value.title()} by {action.reviewer}",
                        description=action.comments,
                        severity=finding.severity,
                        metadata={"finding_id": finding.id},
                    ))

        events.sort(key=lambda e: e.timestamp)

        latest_summary = summaries[0] if summaries else None  # already sorted desc by created_at

        return PatientTimelineResponse(
            patient=PatientTimelineInfo(
                id=patient.id,
                name=patient.name,
                mrn=patient.mrn,
                dob=patient.dob,
                gender=patient.gender,
                created_at=patient.created_at,
            ),
            latest_safety_score=latest_summary.overall_safety_score if latest_summary else None,
            latest_completeness_score=latest_summary.completeness_score if latest_summary else None,
            events=events,
        )
