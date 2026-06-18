from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies import get_mongo_database
from app.models.mongo.review_action import ReviewAction
from app.services.review_history_service import ReviewHistoryService

router = APIRouter(prefix="/review", tags=["Review History"])


@router.get("/history")
async def get_review_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    severity: Optional[str] = None,
    action: Optional[ReviewAction] = None,
    reviewer: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Optional[AsyncIOMotorDatabase] = Depends(get_mongo_database),
) -> Dict[str, Any]:
    """Paginated, filterable history of approve/reject/acknowledge decisions on findings."""
    service = ReviewHistoryService(db)
    entries, total = await service.get_history(
        page=page,
        page_size=page_size,
        severity=severity.upper() if severity else None,
        action=action.value if action else None,
        reviewer=reviewer,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "items": [entry.model_dump(mode="json") for entry in entries],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
