from datetime import datetime

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.models.mongo.finding import FindingMongo
from app.models.mongo.patient import PatientMongo
from app.models.mongo.review_action import ReviewAction, ReviewActionMongo
from app.models.mongo.summary import SummaryMongo
from app.repositories.finding_repository import FindingRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.review_repository import ReviewRepository
from app.repositories.summary_repository import SummaryRepository
from app.services.review_history_service import ReviewHistoryService


@pytest.fixture()
def mongo_db():
    client = AsyncMongoMockClient()
    return client["test_dischargepilot"]


async def _seed(mongo_db):
    await PatientRepository(mongo_db).upsert(PatientMongo(id="p1", patient_id="p1", name="Jane Roe", mrn="MRN-9"))
    await SummaryRepository(mongo_db).create(SummaryMongo(
        id="s1", patient_id="p1", summary_text="t", status="PENDING_REVIEW",
    ))
    await FindingRepository(mongo_db).create_many([
        FindingMongo(id="f1", summary_id="s1", severity="HIGH", category="missing_data",
                     title="Allergy status missing", explanation="x", recommendation="y"),
    ])
    await ReviewRepository(mongo_db).create(ReviewActionMongo(
        finding_id="f1", reviewer="dr.chen", action=ReviewAction.APPROVED,
        comments="reviewed", timestamp=datetime(2026, 1, 1),
    ))


class TestReviewHistoryService:
    @pytest.mark.asyncio
    async def test_get_history_returns_enriched_entries(self, mongo_db):
        await _seed(mongo_db)
        service = ReviewHistoryService(mongo_db)

        entries, total = await service.get_history()
        assert total == 1
        entry = entries[0]
        assert entry.finding_id == "f1"
        assert entry.severity == "HIGH"
        assert entry.patient_name == "Jane Roe"
        assert entry.summary_id == "s1"
        assert entry.action == "APPROVED"

    @pytest.mark.asyncio
    async def test_safe_when_mongo_unavailable(self):
        service = ReviewHistoryService(None)
        entries, total = await service.get_history()
        assert entries == []
        assert total == 0
