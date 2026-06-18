from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.base import MongoRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ReviewHistoryRepository(MongoRepository):
    """
    Read-only, denormalized view over `review_actions`, joined with the
    `findings` -> `summaries` -> `patients` chain it references.

    review_actions only stores finding_id/reviewer/action/comments/timestamp
    (see app/models/mongo/review_action.py) — the severity/patient/summary
    context clinicians need for a history view has to be joined in via
    $lookup rather than denormalized onto the write path, so this stays a
    pure additive read model with no MongoDB schema changes.
    """

    collection_name = "review_actions"

    async def search(
        self,
        page: int = 1,
        page_size: int = 20,
        severity: Optional[str] = None,
        action: Optional[str] = None,
        reviewer: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        if self.collection is None:
            return [], 0

        match: Dict[str, Any] = {}
        if action:
            match["action"] = action
        if reviewer:
            match["reviewer"] = {"$regex": reviewer, "$options": "i"}
        timestamp_range: Dict[str, Any] = {}
        if date_from:
            timestamp_range["$gte"] = date_from
        if date_to:
            timestamp_range["$lte"] = date_to
        if timestamp_range:
            match["timestamp"] = timestamp_range

        pipeline: List[Dict[str, Any]] = [{"$match": match}] if match else []
        pipeline += [
            {"$lookup": {"from": "findings", "localField": "finding_id", "foreignField": "_id", "as": "finding"}},
            {"$unwind": {"path": "$finding", "preserveNullAndEmptyArrays": True}},
        ]
        if severity:
            pipeline.append({"$match": {"finding.severity": severity}})
        pipeline += [
            {"$lookup": {"from": "summaries", "localField": "finding.summary_id", "foreignField": "_id", "as": "summary"}},
            {"$unwind": {"path": "$summary", "preserveNullAndEmptyArrays": True}},
            {"$lookup": {"from": "patients", "localField": "summary.patient_id", "foreignField": "_id", "as": "patient"}},
            {"$unwind": {"path": "$patient", "preserveNullAndEmptyArrays": True}},
            {"$sort": {"timestamp": -1}},
            {
                "$facet": {
                    "items": [{"$skip": (page - 1) * page_size}, {"$limit": page_size}],
                    "total": [{"$count": "count"}],
                }
            },
        ]

        result = await self.collection.aggregate(pipeline).to_list(length=1)
        if not result:
            return [], 0
        items = result[0]["items"]
        total = result[0]["total"][0]["count"] if result[0]["total"] else 0
        return items, total
