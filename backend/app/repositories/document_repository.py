from __future__ import annotations

from typing import List, Optional

from app.models.mongo.document import DocumentMongo
from app.repositories.base import MongoRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class DocumentRepository(MongoRepository):
    collection_name = "documents"

    async def upsert(self, document: DocumentMongo) -> None:
        if self.collection is None:
            return
        # No mode="json": Motor/pymongo encode native datetimes as BSON dates
        # directly, which date-range queries (review history, timeline) need —
        # mode="json" would flatten created_at to an ISO string and break them.
        await self.collection.replace_one(
            {"_id": document.id}, document.model_dump(by_alias=True), upsert=True
        )
        logger.info("Document saved to MongoDB", document_id=document.id, patient_id=document.patient_id)

    async def get_by_id(self, document_id: str) -> Optional[DocumentMongo]:
        if self.collection is None:
            return None
        doc = await self.collection.find_one({"_id": document_id})
        return DocumentMongo.model_validate(doc) if doc else None

    async def list_for_patient(self, patient_id: str) -> List[DocumentMongo]:
        if self.collection is None:
            return []
        cursor = self.collection.find({"patient_id": patient_id}).sort("created_at", -1)
        return [DocumentMongo.model_validate(doc) async for doc in cursor]

    async def count(self) -> int:
        if self.collection is None:
            return 0
        return await self.collection.count_documents({})
