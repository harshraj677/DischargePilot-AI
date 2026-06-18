from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.repositories.base import MongoRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

_RESULT_LIMIT = 25


class SearchRepository(MongoRepository):
    """Cross-collection lookup backing the global search bar. Read-only, no schema changes."""

    collection_name = "patients"

    async def find_patients(self, name: Optional[str] = None, mrn: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.collection is None or not (name or mrn):
            return []
        query: Dict[str, Any] = {}
        if name:
            query["name"] = {"$regex": name, "$options": "i"}
        if mrn:
            query["mrn"] = {"$regex": mrn, "$options": "i"}
        cursor = self.collection.find(query).limit(_RESULT_LIMIT)
        return [doc async for doc in cursor]

    async def find_patient_by_id(self, patient_id: str) -> Optional[Dict[str, Any]]:
        if self.collection is None:
            return None
        return await self.collection.find_one({"_id": patient_id})

    async def find_summary_by_id(self, summary_id: str) -> Optional[Dict[str, Any]]:
        if self._db is None:
            return None
        return await self._db.summaries.find_one({"_id": summary_id})

    async def find_summaries_for_patient(self, patient_id: str) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        cursor = self._db.summaries.find({"patient_id": patient_id}).sort("created_at", -1)
        return [doc async for doc in cursor]

    async def find_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        if self._db is None:
            return None
        return await self._db.documents.find_one({"_id": document_id})
