from __future__ import annotations

from typing import List, Optional, Tuple

from app.models.mongo.summary import SummaryMongo
from app.repositories.base import MongoRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SummaryRepository(MongoRepository):
    collection_name = "summaries"

    async def create(self, summary: SummaryMongo) -> None:
        if self.collection is None:
            return
        # No mode="json" — see comment in document_repository.py:upsert.
        await self.collection.replace_one(
            {"_id": summary.id}, summary.model_dump(by_alias=True), upsert=True
        )
        logger.info("Summary saved to MongoDB", summary_id=summary.id, patient_id=summary.patient_id)

    async def get_by_id(self, summary_id: str) -> Optional[SummaryMongo]:
        if self.collection is None:
            return None
        doc = await self.collection.find_one({"_id": summary_id})
        return SummaryMongo.model_validate(doc) if doc else None

    async def list_for_patient(self, patient_id: str, limit: int = 50) -> List[SummaryMongo]:
        if self.collection is None:
            return []
        cursor = self.collection.find({"patient_id": patient_id}).sort("created_at", -1).limit(limit)
        return [SummaryMongo.model_validate(doc) async for doc in cursor]

    async def list_all(self, page: int = 1, page_size: int = 20) -> Tuple[List[SummaryMongo], int]:
        if self.collection is None:
            return [], 0
        total = await self.collection.count_documents({})
        cursor = (
            self.collection.find()
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        items = [SummaryMongo.model_validate(doc) async for doc in cursor]
        return items, total

    async def count(self) -> int:
        if self.collection is None:
            return 0
        return await self.collection.count_documents({})

    async def average_safety_score(self) -> float:
        return await self._average("overall_safety_score")

    async def average_completeness_score(self) -> float:
        return await self._average("completeness_score")

    async def _average(self, field: str) -> float:
        if self.collection is None:
            return 0.0
        pipeline = [{"$group": {"_id": None, "avg": {"$avg": f"${field}"}}}]
        result = await self.collection.aggregate(pipeline).to_list(length=1)
        return round(result[0]["avg"], 3) if result and result[0]["avg"] is not None else 0.0
