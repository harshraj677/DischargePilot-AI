from __future__ import annotations

from typing import Dict, List

from app.models.mongo.finding import FindingMongo
from app.repositories.base import MongoRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Canonical missing-field keys tracked on the analytics dashboard, mapped to the
# substrings that appear in CompletenessValidator / medication validator
# descriptions (see app/safety/validators/completeness.py and medication.py).
_TRACKED_MISSING_FIELDS: Dict[str, List[str]] = {
    "allergy_status": ["allergy"],
    "admission_date": ["admission date"],
    "hospital_course": ["hospital course"],
    "discharge_condition": ["discharge condition"],
    "medication_dose": ["dose"],
}

_CONFLICT_CATEGORIES = ["conflict", "medication_discrepancy", "medication"]


class FindingRepository(MongoRepository):
    collection_name = "findings"

    async def create_many(self, findings: List[FindingMongo]) -> None:
        if self.collection is None or not findings:
            return
        # No mode="json" — see comment in document_repository.py:upsert.
        await self.collection.insert_many(
            [f.model_dump(by_alias=True) for f in findings]
        )
        logger.info("Findings saved to MongoDB", count=len(findings))

    async def get_by_summary_id(self, summary_id: str) -> List[FindingMongo]:
        if self.collection is None:
            return []
        cursor = self.collection.find({"summary_id": summary_id})
        return [FindingMongo.model_validate(doc) async for doc in cursor]

    async def count(self) -> int:
        if self.collection is None:
            return 0
        return await self.collection.count_documents({})

    async def count_high_risk(self) -> int:
        """HIGH (and CRITICAL, if ever stored) severity findings."""
        if self.collection is None:
            return 0
        return await self.collection.count_documents(
            {"severity": {"$in": ["CRITICAL", "HIGH"]}}
        )

    async def severity_distribution(self) -> Dict[str, int]:
        distribution = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        if self.collection is None:
            return distribution
        pipeline = [{"$group": {"_id": "$severity", "count": {"$sum": 1}}}]
        async for row in self.collection.aggregate(pipeline):
            severity = row["_id"]
            if severity == "CRITICAL":
                distribution["HIGH"] += row["count"]
            elif severity in distribution:
                distribution[severity] += row["count"]
        return distribution

    async def top_missing_fields(self) -> List[Dict[str, object]]:
        if self.collection is None:
            return [{"field": field, "count": 0} for field in _TRACKED_MISSING_FIELDS]

        counts = {field: 0 for field in _TRACKED_MISSING_FIELDS}
        cursor = self.collection.find(
            {"category": "missing_data"}, {"title": 1, "explanation": 1}
        )
        async for doc in cursor:
            text = f"{doc.get('title', '')} {doc.get('explanation', '')}".lower()
            for field, keywords in _TRACKED_MISSING_FIELDS.items():
                if any(keyword in text for keyword in keywords):
                    counts[field] += 1

        return sorted(
            ({"field": field, "count": count} for field, count in counts.items()),
            key=lambda item: item["count"],
            reverse=True,
        )

    async def top_conflicts(self, limit: int = 5) -> List[Dict[str, object]]:
        if self.collection is None:
            return []
        pipeline = [
            {"$match": {"category": {"$in": _CONFLICT_CATEGORIES}}},
            {"$group": {"_id": "$title", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
        return [
            {"title": row["_id"], "count": row["count"]}
            async for row in self.collection.aggregate(pipeline)
        ]
