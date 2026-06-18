import pytest

from app.models.mongo.finding import FindingMongo
from app.models.mongo.patient import PatientMongo
from app.models.mongo.review_action import ReviewAction, ReviewActionMongo
from app.models.mongo.summary import SummaryMongo
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.finding_repository import FindingRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.review_repository import ReviewRepository
from app.repositories.summary_repository import SummaryRepository


class TestAnalyticsRepository:
    @pytest.mark.asyncio
    async def test_aggregates_across_collections(self, mongo_db):
        await PatientRepository(mongo_db).upsert(PatientMongo(id="p1", patient_id="p1", name="John"))
        await SummaryRepository(mongo_db).create(SummaryMongo(
            id="s1", patient_id="p1", summary_text="t", status="PENDING_REVIEW",
            overall_safety_score=0.9, completeness_score=0.8,
        ))
        await FindingRepository(mongo_db).create_many([
            FindingMongo(id="f1", summary_id="s1", severity="HIGH", category="missing_data",
                         title="Allergy status is not documented", explanation="x", recommendation="y"),
        ])
        await ReviewRepository(mongo_db).create(
            ReviewActionMongo(finding_id="f1", reviewer="dr.chen", action=ReviewAction.APPROVED)
        )

        repo = AnalyticsRepository(mongo_db)
        assert await repo.total_patients() == 1
        assert await repo.total_summaries() == 1
        assert await repo.total_findings() == 1
        assert await repo.average_safety_score() == 0.9
        assert await repo.high_risk_findings() == 1
        assert await repo.approved_count() == 1
        assert await repo.rejected_count() == 0
        assert (await repo.severity_distribution())["HIGH"] == 1
        missing = {row["field"]: row["count"] for row in await repo.top_missing_fields()}
        assert missing["allergy_status"] == 1

    @pytest.mark.asyncio
    async def test_safe_when_mongo_unavailable(self):
        repo = AnalyticsRepository(None)
        assert await repo.total_patients() == 0
        assert await repo.average_safety_score() == 0.0
        assert await repo.top_conflicts() == []
