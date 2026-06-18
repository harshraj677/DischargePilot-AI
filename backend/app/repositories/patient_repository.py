from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from app.models.mongo.patient import PatientMongo
from app.repositories.base import MongoRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class PatientRepository(MongoRepository):
    collection_name = "patients"

    async def upsert(self, patient: PatientMongo) -> None:
        if self.collection is None:
            return
        patient.updated_at = datetime.utcnow()
        # No mode="json" — see comment in document_repository.py:upsert.
        await self.collection.replace_one(
            {"_id": patient.id}, patient.model_dump(by_alias=True), upsert=True
        )
        logger.info("Patient saved to MongoDB", patient_id=patient.patient_id)

    async def get_by_id(self, patient_id: str) -> Optional[PatientMongo]:
        if self.collection is None:
            return None
        doc = await self.collection.find_one({"_id": patient_id})
        return PatientMongo.model_validate(doc) if doc else None

    async def list(self, limit: int = 100) -> List[PatientMongo]:
        if self.collection is None:
            return []
        cursor = self.collection.find().sort("created_at", -1).limit(limit)
        return [PatientMongo.model_validate(doc) async for doc in cursor]

    async def count(self) -> int:
        if self.collection is None:
            return 0
        return await self.collection.count_documents({})
