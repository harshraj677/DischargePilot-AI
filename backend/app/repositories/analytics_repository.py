from __future__ import annotations

from typing import Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.finding_repository import FindingRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.review_repository import ReviewRepository
from app.repositories.summary_repository import SummaryRepository


class AnalyticsRepository:
    """Read-only aggregation layer over the patients/documents/summaries/findings/review_actions collections."""

    def __init__(self, db: Optional[AsyncIOMotorDatabase]):
        self._patients = PatientRepository(db)
        self._documents = DocumentRepository(db)
        self._summaries = SummaryRepository(db)
        self._findings = FindingRepository(db)
        self._reviews = ReviewRepository(db)

    async def total_patients(self) -> int:
        return await self._patients.count()

    async def total_documents(self) -> int:
        return await self._documents.count()

    async def total_summaries(self) -> int:
        return await self._summaries.count()

    async def total_findings(self) -> int:
        return await self._findings.count()

    async def average_safety_score(self) -> float:
        return await self._summaries.average_safety_score()

    async def average_completeness_score(self) -> float:
        return await self._summaries.average_completeness_score()

    async def high_risk_findings(self) -> int:
        return await self._findings.count_high_risk()

    async def approved_count(self) -> int:
        return await self._reviews.count_by_action("APPROVED")

    async def rejected_count(self) -> int:
        return await self._reviews.count_by_action("REJECTED")

    async def acknowledged_count(self) -> int:
        return await self._reviews.count_by_action("ACKNOWLEDGED")

    async def total_review_actions(self) -> int:
        return await self._reviews.count()

    async def severity_distribution(self) -> Dict[str, int]:
        return await self._findings.severity_distribution()

    async def top_missing_fields(self) -> List[Dict[str, object]]:
        return await self._findings.top_missing_fields()

    async def top_conflicts(self) -> List[Dict[str, object]]:
        return await self._findings.top_conflicts()
