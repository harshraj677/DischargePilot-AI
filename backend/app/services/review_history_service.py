from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.repositories.review_history_repository import ReviewHistoryRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ReviewHistoryEntry(BaseModel):
    id: str
    finding_id: str
    reviewer: str
    action: str
    comments: Optional[str] = None
    timestamp: datetime

    severity: Optional[str] = None
    category: Optional[str] = None
    finding_title: Optional[str] = None

    summary_id: Optional[str] = None
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None


class ReviewHistoryService:
    """Tracks approved/rejected/acknowledged findings for the clinician-facing review history view."""

    def __init__(self, db: Optional[AsyncIOMotorDatabase]):
        self._repo = ReviewHistoryRepository(db)

    async def get_history(
        self,
        page: int = 1,
        page_size: int = 20,
        severity: Optional[str] = None,
        action: Optional[str] = None,
        reviewer: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Tuple[List[ReviewHistoryEntry], int]:
        raw_items, total = await self._repo.search(
            page=page,
            page_size=page_size,
            severity=severity,
            action=action,
            reviewer=reviewer,
            date_from=date_from,
            date_to=date_to,
        )
        entries = [self._to_entry(item) for item in raw_items]
        return entries, total

    @staticmethod
    def _to_entry(doc: Dict[str, Any]) -> ReviewHistoryEntry:
        finding = doc.get("finding") or {}
        summary = doc.get("summary") or {}
        patient = doc.get("patient") or {}
        return ReviewHistoryEntry(
            id=doc["_id"],
            finding_id=doc["finding_id"],
            reviewer=doc["reviewer"],
            action=doc["action"],
            comments=doc.get("comments"),
            timestamp=doc["timestamp"],
            severity=finding.get("severity"),
            category=finding.get("category"),
            finding_title=finding.get("title"),
            summary_id=summary.get("_id"),
            patient_id=patient.get("_id") or patient.get("patient_id"),
            patient_name=patient.get("name"),
        )
