from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.repositories.search_repository import SearchRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SearchResultItem(BaseModel):
    patient_id: str
    patient_name: str
    mrn: Optional[str] = None

    summary_id: Optional[str] = None
    status: Optional[str] = None
    safety_score: Optional[float] = None
    completeness_score: Optional[float] = None
    created_at: Optional[datetime] = None


class SearchService:
    """Global search across patients, MRNs, summary ids, and document ids."""

    def __init__(self, db: Optional[AsyncIOMotorDatabase]):
        self._repo = SearchRepository(db)

    async def search(
        self,
        patient_name: Optional[str] = None,
        mrn: Optional[str] = None,
        summary_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> List[SearchResultItem]:
        if summary_id:
            return await self._by_summary_id(summary_id)
        if document_id:
            return await self._by_document_id(document_id)
        if patient_name or mrn:
            return await self._by_patient(patient_name, mrn)
        return []

    async def _by_summary_id(self, summary_id: str) -> List[SearchResultItem]:
        summary = await self._repo.find_summary_by_id(summary_id)
        if not summary:
            return []
        patient = await self._repo.find_patient_by_id(summary["patient_id"])
        if not patient:
            return []
        return [self._build_result(patient, summary)]

    async def _by_document_id(self, document_id: str) -> List[SearchResultItem]:
        document = await self._repo.find_document_by_id(document_id)
        if not document:
            return []
        patient = await self._repo.find_patient_by_id(document["patient_id"])
        if not patient:
            return []
        summaries = await self._repo.find_summaries_for_patient(patient["_id"])
        if not summaries:
            return [self._build_result(patient, None)]
        return [self._build_result(patient, s) for s in summaries]

    async def _by_patient(self, name: Optional[str], mrn: Optional[str]) -> List[SearchResultItem]:
        patients = await self._repo.find_patients(name=name, mrn=mrn)
        results: List[SearchResultItem] = []
        for patient in patients:
            summaries = await self._repo.find_summaries_for_patient(patient["_id"])
            if not summaries:
                results.append(self._build_result(patient, None))
            else:
                results.extend(self._build_result(patient, s) for s in summaries)
        return results

    @staticmethod
    def _build_result(patient: Dict[str, Any], summary: Optional[Dict[str, Any]]) -> SearchResultItem:
        return SearchResultItem(
            patient_id=patient["_id"],
            patient_name=patient.get("name", ""),
            mrn=patient.get("mrn"),
            summary_id=summary.get("_id") if summary else None,
            status=summary.get("status") if summary else None,
            safety_score=summary.get("overall_safety_score") if summary else None,
            completeness_score=summary.get("completeness_score") if summary else None,
            created_at=summary.get("created_at") if summary else None,
        )
