from __future__ import annotations

from typing import List, Optional, Tuple

from app.models.mongo.review_action import ReviewActionMongo
from app.repositories.base import MongoRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ReviewRepository(MongoRepository):
    collection_name = "review_actions"

    async def create(self, action: ReviewActionMongo) -> None:
        if self.collection is None:
            return
        # No mode="json" — see comment in document_repository.py:upsert.
        await self.collection.insert_one(action.model_dump(by_alias=True))
        logger.info(
            "Review action saved to MongoDB",
            finding_id=action.finding_id,
            action=action.action.value,
            reviewer=action.reviewer,
        )

    async def list_by_finding(self, finding_id: str) -> List[ReviewActionMongo]:
        if self.collection is None:
            return []
        cursor = self.collection.find({"finding_id": finding_id}).sort("timestamp", -1)
        return [ReviewActionMongo.model_validate(doc) async for doc in cursor]

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 20,
        action: Optional[str] = None,
    ) -> Tuple[List[ReviewActionMongo], int]:
        if self.collection is None:
            return [], 0
        query = {"action": action} if action else {}
        total = await self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort("timestamp", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        items = [ReviewActionMongo.model_validate(doc) async for doc in cursor]
        return items, total

    async def count_by_action(self, action: str) -> int:
        if self.collection is None:
            return 0
        return await self.collection.count_documents({"action": action})

    async def count(self) -> int:
        if self.collection is None:
            return 0
        return await self.collection.count_documents({})
