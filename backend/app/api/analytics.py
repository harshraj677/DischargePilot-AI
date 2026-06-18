from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.dependencies import get_mongo_database
from app.models.mongo.review_action import ReviewAction, ReviewActionMongo
from app.repositories.review_repository import ReviewRepository
from app.services.analytics_service import AnalyticsService
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


class DashboardMetricsResponse(BaseModel):
    total_patients: int
    total_documents: int
    total_summaries: int
    total_findings: int
    average_safety_score: float
    average_completeness_score: float
    high_risk_findings: int
    approval_rate: float
    rejection_rate: float
    acknowledgment_rate: float
    severity_distribution: Dict[str, int]
    top_missing_fields: List[Dict[str, Any]]
    top_conflicts: List[Dict[str, Any]]


class RecordReviewActionRequest(BaseModel):
    reviewer: str
    action: ReviewAction
    comments: Optional[str] = None


class ReviewActionResponse(BaseModel):
    id: str
    finding_id: str
    reviewer: str
    action: str
    comments: Optional[str] = None
    timestamp: str


@router.get("/dashboard", response_model=DashboardMetricsResponse)
async def get_dashboard(
    db: Optional[AsyncIOMotorDatabase] = Depends(get_mongo_database),
) -> DashboardMetricsResponse:
    """Aggregated metrics for the analytics dashboard."""
    metrics = await AnalyticsService(db).get_dashboard_metrics()
    return DashboardMetricsResponse(**metrics)


@router.post("/findings/{finding_id}/review-actions", response_model=ReviewActionResponse)
async def record_review_action(
    finding_id: str,
    body: RecordReviewActionRequest,
    db: Optional[AsyncIOMotorDatabase] = Depends(get_mongo_database),
) -> ReviewActionResponse:
    """Record a clinician decision (approve/reject/acknowledge) on a finding."""
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable")

    action = ReviewActionMongo(
        finding_id=finding_id,
        reviewer=body.reviewer,
        action=body.action,
        comments=body.comments,
    )
    await ReviewRepository(db).create(action)
    return ReviewActionResponse(
        id=action.id,
        finding_id=action.finding_id,
        reviewer=action.reviewer,
        action=action.action.value,
        comments=action.comments,
        timestamp=action.timestamp.isoformat(),
    )


@router.get("/review-history")
async def get_review_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: Optional[ReviewAction] = None,
    db: Optional[AsyncIOMotorDatabase] = Depends(get_mongo_database),
) -> Dict[str, Any]:
    """Paginated review action history, optionally filtered by action type."""
    items, total = await ReviewRepository(db).list_all(
        page=page, page_size=page_size, action=action.value if action else None
    )
    return {
        "items": [
            ReviewActionResponse(
                id=item.id,
                finding_id=item.finding_id,
                reviewer=item.reviewer,
                action=item.action.value,
                comments=item.comments,
                timestamp=item.timestamp.isoformat(),
            )
            for item in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
