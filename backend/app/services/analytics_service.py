from __future__ import annotations

from typing import Any, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.analytics_repository import AnalyticsRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AnalyticsService:
    """Computes dashboard metrics from the MongoDB analytics repositories."""

    def __init__(self, db: Optional[AsyncIOMotorDatabase]):
        self._repo = AnalyticsRepository(db)

    async def get_total_patients(self) -> int:
        return await self._repo.total_patients()

    async def get_total_documents(self) -> int:
        return await self._repo.total_documents()

    async def get_total_summaries(self) -> int:
        return await self._repo.total_summaries()

    async def get_total_findings(self) -> int:
        return await self._repo.total_findings()

    async def get_average_safety_score(self) -> float:
        return await self._repo.average_safety_score()

    async def get_average_completeness_score(self) -> float:
        return await self._repo.average_completeness_score()

    async def get_high_risk_findings(self) -> int:
        return await self._repo.high_risk_findings()

    async def get_approval_rate(self) -> float:
        return await self._rate(await self._repo.approved_count())

    async def get_rejection_rate(self) -> float:
        return await self._rate(await self._repo.rejected_count())

    async def get_acknowledgment_rate(self) -> float:
        return await self._rate(await self._repo.acknowledged_count())

    async def get_top_missing_fields(self):
        return await self._repo.top_missing_fields()

    async def get_top_conflicts(self):
        return await self._repo.top_conflicts()

    async def get_severity_distribution(self) -> Dict[str, int]:
        return await self._repo.severity_distribution()

    async def _rate(self, numerator: int) -> float:
        total = await self._repo.total_review_actions()
        if total == 0:
            return 0.0
        return round(numerator / total, 3)

    async def get_dashboard_metrics(self) -> Dict[str, Any]:
        metrics = {
            "total_patients": await self.get_total_patients(),
            "total_documents": await self.get_total_documents(),
            "total_summaries": await self.get_total_summaries(),
            "total_findings": await self.get_total_findings(),
            "average_safety_score": await self.get_average_safety_score(),
            "average_completeness_score": await self.get_average_completeness_score(),
            "high_risk_findings": await self.get_high_risk_findings(),
            "approval_rate": await self.get_approval_rate(),
            "rejection_rate": await self.get_rejection_rate(),
            "acknowledgment_rate": await self.get_acknowledgment_rate(),
            "severity_distribution": await self.get_severity_distribution(),
            "top_missing_fields": await self.get_top_missing_fields(),
            "top_conflicts": await self.get_top_conflicts(),
        }
        logger.info("Analytics computed", **{k: v for k, v in metrics.items() if not isinstance(v, (list, dict))})
        return metrics
