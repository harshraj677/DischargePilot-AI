import pytest
from mongomock_motor import AsyncMongoMockClient

from app.models.mongo.finding import FindingMongo
from app.models.mongo.review_action import ReviewAction, ReviewActionMongo
from app.models.mongo.summary import SummaryMongo
from app.repositories.finding_repository import FindingRepository
from app.repositories.review_repository import ReviewRepository
from app.repositories.summary_repository import SummaryRepository
from app.services.analytics_service import AnalyticsService


@pytest.fixture()
def mongo_db():
    client = AsyncMongoMockClient()
    return client["test_dischargepilot"]


async def _seed(mongo_db):
    await SummaryRepository(mongo_db).create(SummaryMongo(
        id="s1", patient_id="p1", summary_text="t", status="PENDING_REVIEW",
        overall_safety_score=0.9, completeness_score=0.8,
        high_findings_count=1, medium_findings_count=1,
    ))
    await FindingRepository(mongo_db).create_many([
        FindingMongo(id="f1", summary_id="s1", severity="HIGH", category="missing_data",
                     title="Allergy status is not documented", explanation="x", recommendation="y"),
        FindingMongo(id="f2", summary_id="s1", severity="MEDIUM", category="conflict",
                     title="Dose mismatch", explanation="x", recommendation="y"),
    ])
    await ReviewRepository(mongo_db).create(
        ReviewActionMongo(finding_id="f1", reviewer="dr.chen", action=ReviewAction.APPROVED)
    )
    await ReviewRepository(mongo_db).create(
        ReviewActionMongo(finding_id="f2", reviewer="dr.chen", action=ReviewAction.REJECTED)
    )


class TestAnalyticsService:
    @pytest.mark.asyncio
    async def test_get_dashboard_metrics_shape_and_values(self, mongo_db):
        await _seed(mongo_db)
        service = AnalyticsService(mongo_db)
        metrics = await service.get_dashboard_metrics()

        assert metrics["total_patients"] == 0  # no patient record seeded in this test
        assert metrics["total_summaries"] == 1
        assert metrics["total_findings"] == 2
        assert metrics["average_safety_score"] == 0.9
        assert metrics["average_completeness_score"] == 0.8
        assert metrics["high_risk_findings"] == 1
        assert metrics["approval_rate"] == 0.5
        assert metrics["rejection_rate"] == 0.5
        assert metrics["severity_distribution"]["HIGH"] == 1
        assert metrics["severity_distribution"]["MEDIUM"] == 1
        assert any(row["field"] == "allergy_status" and row["count"] == 1 for row in metrics["top_missing_fields"])
        assert metrics["top_conflicts"][0]["title"] == "Dose mismatch"

    @pytest.mark.asyncio
    async def test_rates_are_zero_with_no_review_actions(self, mongo_db):
        service = AnalyticsService(mongo_db)
        assert await service.get_approval_rate() == 0.0
        assert await service.get_rejection_rate() == 0.0

    @pytest.mark.asyncio
    async def test_dashboard_metrics_safe_when_mongo_unavailable(self):
        service = AnalyticsService(None)
        metrics = await service.get_dashboard_metrics()
        assert metrics["total_patients"] == 0
        assert metrics["average_safety_score"] == 0.0
        assert metrics["top_conflicts"] == []
