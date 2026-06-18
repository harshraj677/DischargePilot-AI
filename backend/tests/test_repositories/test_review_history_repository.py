from datetime import datetime, timedelta

import pytest

from app.models.mongo.finding import FindingMongo
from app.models.mongo.patient import PatientMongo
from app.models.mongo.review_action import ReviewAction, ReviewActionMongo
from app.models.mongo.summary import SummaryMongo
from app.repositories.finding_repository import FindingRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.review_history_repository import ReviewHistoryRepository
from app.repositories.review_repository import ReviewRepository
from app.repositories.summary_repository import SummaryRepository


async def _seed(mongo_db):
    await PatientRepository(mongo_db).upsert(PatientMongo(id="p1", patient_id="p1", name="John Doe", mrn="MRN-1"))
    await SummaryRepository(mongo_db).create(SummaryMongo(
        id="s1", patient_id="p1", summary_text="t", status="PENDING_REVIEW",
        overall_safety_score=0.9, completeness_score=0.8,
    ))
    await FindingRepository(mongo_db).create_many([
        FindingMongo(id="f1", summary_id="s1", severity="HIGH", category="missing_data",
                     title="Allergy status missing", explanation="x", recommendation="y"),
        FindingMongo(id="f2", summary_id="s1", severity="LOW", category="other",
                     title="Minor note", explanation="x", recommendation="y"),
    ])
    await ReviewRepository(mongo_db).create(ReviewActionMongo(
        finding_id="f1", reviewer="dr.chen", action=ReviewAction.APPROVED, comments="ok",
        timestamp=datetime(2026, 1, 1),
    ))
    await ReviewRepository(mongo_db).create(ReviewActionMongo(
        finding_id="f2", reviewer="dr.lee", action=ReviewAction.REJECTED,
        timestamp=datetime(2026, 1, 2),
    ))


class TestReviewHistoryRepository:
    @pytest.mark.asyncio
    async def test_search_joins_finding_summary_patient(self, mongo_db):
        await _seed(mongo_db)
        repo = ReviewHistoryRepository(mongo_db)

        items, total = await repo.search()
        assert total == 2
        # Most recent first.
        assert items[0]["finding_id"] == "f2"
        assert items[0]["finding"]["severity"] == "LOW"
        assert items[0]["patient"]["name"] == "John Doe"
        assert items[1]["finding_id"] == "f1"

    @pytest.mark.asyncio
    async def test_filter_by_severity(self, mongo_db):
        await _seed(mongo_db)
        repo = ReviewHistoryRepository(mongo_db)

        items, total = await repo.search(severity="HIGH")
        assert total == 1
        assert items[0]["finding_id"] == "f1"

    @pytest.mark.asyncio
    async def test_filter_by_action(self, mongo_db):
        await _seed(mongo_db)
        repo = ReviewHistoryRepository(mongo_db)

        items, total = await repo.search(action="REJECTED")
        assert total == 1
        assert items[0]["action"] == "REJECTED"

    @pytest.mark.asyncio
    async def test_filter_by_reviewer_case_insensitive(self, mongo_db):
        await _seed(mongo_db)
        repo = ReviewHistoryRepository(mongo_db)

        items, total = await repo.search(reviewer="CHEN")
        assert total == 1
        assert items[0]["reviewer"] == "dr.chen"

    @pytest.mark.asyncio
    async def test_filter_by_date_range(self, mongo_db):
        await _seed(mongo_db)
        repo = ReviewHistoryRepository(mongo_db)

        items, total = await repo.search(date_from=datetime(2026, 1, 2), date_to=datetime(2026, 1, 3))
        assert total == 1
        assert items[0]["finding_id"] == "f2"

    @pytest.mark.asyncio
    async def test_pagination(self, mongo_db):
        await _seed(mongo_db)
        repo = ReviewHistoryRepository(mongo_db)

        items, total = await repo.search(page=1, page_size=1)
        assert total == 2
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_safe_when_mongo_unavailable(self):
        repo = ReviewHistoryRepository(None)
        assert await repo.search() == ([], 0)
