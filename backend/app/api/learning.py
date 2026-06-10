"""
Learning API — Phase 8 endpoints for doctor review cycle and learning metrics.

Routes:
    POST /api/v1/learning/runs/{run_id}/review  — start a review cycle
    GET  /api/v1/learning/reviews/{review_id}   — get a specific review
    GET  /api/v1/learning/reviews               — list recent reviews
    GET  /api/v1/learning/metrics               — overall learning metrics
    GET  /api/v1/learning/strategies            — prompt strategies with stats
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.claude.agent_client import ClaudeAgentClient, get_claude_agent_client
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.learning.models import DoctorReview, LearningMetrics, PromptStrategy, RewardScore
from app.services.learning_service import LearningService
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/learning", tags=["Learning"])

_claude_client: Optional[ClaudeAgentClient] = None


def _get_client() -> ClaudeAgentClient:
    global _claude_client
    if _claude_client is None:
        _claude_client = get_claude_agent_client()
    return _claude_client


# ── Response Models ───────────────────────────────────────────────────────────

class RewardScoreResponse(BaseModel):
    total: float
    edit_distance_score: float
    section_accuracy_score: float
    review_burden_score: float
    breakdown: Dict[str, Any] = {}


class DoctorReviewResponse(BaseModel):
    review_id: str
    run_id: str
    draft_summary_id: Optional[str] = None
    edited_sections: Dict[str, str] = {}
    review_notes: str = ""
    reward_score: Optional[RewardScoreResponse] = None
    strategy_used: Optional[str] = None
    created_at: str


class LearningMetricsDateEntry(BaseModel):
    date: str
    avg_reward: float
    count: int


class LearningMetricsResponse(BaseModel):
    total_reviews: int
    avg_reward: float
    avg_edit_distance: float
    improvement_rate: float
    best_strategy: Optional[str] = None
    sessions_by_date: List[LearningMetricsDateEntry] = []


class PromptStrategyResponse(BaseModel):
    strategy_id: str
    name: str
    prompt_template: str
    variant: str
    total_uses: int
    avg_reward: float
    description: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/runs/{run_id}/review",
    response_model=DoctorReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Start a doctor review cycle for a completed agent run",
)
async def start_review(
    run_id: str,
    db: Session = Depends(get_db),
) -> DoctorReviewResponse:
    """
    Triggers the AI doctor reviewer on a completed agent run.

    1. Loads the discharge summary from DB.
    2. Selects a prompt strategy (epsilon-greedy).
    3. Runs the DoctorReviewerAgent.
    4. Computes reward scores.
    5. Updates strategy performance and stores corrections.
    6. Persists a LearningRun record.

    Returns the DoctorReview with edited sections and reward scores.
    """
    service = LearningService(db, _get_client())
    try:
        review = await service.run_review_cycle(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Review cycle failed", run_id=run_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Review cycle failed: {exc}",
        )
    return _review_to_response(review)


@router.get(
    "/reviews/{review_id}",
    response_model=DoctorReviewResponse,
    summary="Get a specific doctor review by ID",
)
def get_review(
    review_id: str,
    db: Session = Depends(get_db),
) -> DoctorReviewResponse:
    """Retrieve a specific learning review record by its ID."""
    service = LearningService(db, _get_client())
    reviews = service.list_reviews(limit=200)
    match = next((r for r in reviews if r["review_id"] == review_id), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Review {review_id} not found")
    return DoctorReviewResponse(**_dict_to_response_data(match))


@router.get(
    "/reviews",
    response_model=List[DoctorReviewResponse],
    summary="List recent doctor reviews (last 50)",
)
def list_reviews(
    db: Session = Depends(get_db),
) -> List[DoctorReviewResponse]:
    """Return the most recent 50 doctor review records."""
    service = LearningService(db, _get_client())
    reviews = service.list_reviews(limit=50)
    return [DoctorReviewResponse(**_dict_to_response_data(r)) for r in reviews]


@router.get(
    "/metrics",
    response_model=LearningMetricsResponse,
    summary="Get overall learning system metrics",
)
def get_metrics(
    db: Session = Depends(get_db),
) -> LearningMetricsResponse:
    """Return aggregated metrics: avg reward, edit distance, improvement rate, best strategy."""
    service = LearningService(db, _get_client())
    metrics = service.get_metrics()
    return LearningMetricsResponse(
        total_reviews=metrics.total_reviews,
        avg_reward=metrics.avg_reward,
        avg_edit_distance=metrics.avg_edit_distance,
        improvement_rate=metrics.improvement_rate,
        best_strategy=metrics.best_strategy,
        sessions_by_date=[
            LearningMetricsDateEntry(
                date=s.date,
                avg_reward=s.avg_reward,
                count=s.count,
            )
            for s in metrics.sessions_by_date
        ],
    )


@router.get(
    "/strategies",
    response_model=List[PromptStrategyResponse],
    summary="List prompt strategies with performance statistics",
)
def list_strategies(
    db: Session = Depends(get_db),
) -> List[PromptStrategyResponse]:
    """Return all prompt strategies with their reward statistics."""
    service = LearningService(db, _get_client())
    strategies = service.get_strategies()
    return [
        PromptStrategyResponse(
            strategy_id=s.strategy_id,
            name=s.name,
            prompt_template=s.prompt_template,
            variant=s.variant,
            total_uses=s.total_uses,
            avg_reward=s.avg_reward,
            description=s.description,
        )
        for s in strategies
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _review_to_response(review: DoctorReview) -> DoctorReviewResponse:
    reward_resp: Optional[RewardScoreResponse] = None
    if review.reward_score:
        reward_resp = RewardScoreResponse(
            total=review.reward_score.total,
            edit_distance_score=review.reward_score.edit_distance_score,
            section_accuracy_score=review.reward_score.section_accuracy_score,
            review_burden_score=review.reward_score.review_burden_score,
            breakdown=review.reward_score.breakdown,
        )
    return DoctorReviewResponse(
        review_id=review.review_id,
        run_id=review.run_id,
        draft_summary_id=review.draft_summary_id,
        edited_sections=review.edited_sections,
        review_notes=review.review_notes,
        reward_score=reward_resp,
        strategy_used=review.strategy_used,
        created_at=review.created_at.isoformat(),
    )


def _dict_to_response_data(d: dict) -> dict:
    reward = d.get("reward_score")
    return {
        "review_id": d["review_id"],
        "run_id": d["run_id"],
        "draft_summary_id": d.get("draft_summary_id"),
        "edited_sections": d.get("edited_sections", {}),
        "review_notes": d.get("review_notes", ""),
        "reward_score": RewardScoreResponse(**reward) if reward else None,
        "strategy_used": d.get("strategy_used"),
        "created_at": d["created_at"],
    }
