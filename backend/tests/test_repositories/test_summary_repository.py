import pytest

from app.models.mongo.summary import SummaryMongo
from app.repositories.summary_repository import SummaryRepository


def _summary(id_, patient_id="p1", safety=1.0, completeness=1.0):
    return SummaryMongo(
        id=id_,
        patient_id=patient_id,
        summary_text="text",
        status="PENDING_REVIEW",
        overall_safety_score=safety,
        completeness_score=completeness,
    )


class TestSummaryRepository:
    @pytest.mark.asyncio
    async def test_create_and_get_by_id(self, mongo_db):
        repo = SummaryRepository(mongo_db)
        await repo.create(_summary("s1"))

        fetched = await repo.get_by_id("s1")
        assert fetched is not None
        assert fetched.patient_id == "p1"

    @pytest.mark.asyncio
    async def test_list_for_patient(self, mongo_db):
        repo = SummaryRepository(mongo_db)
        await repo.create(_summary("s1", patient_id="p1"))
        await repo.create(_summary("s2", patient_id="p2"))

        summaries = await repo.list_for_patient("p1")
        assert len(summaries) == 1
        assert summaries[0].id == "s1"

    @pytest.mark.asyncio
    async def test_list_all_paginates(self, mongo_db):
        repo = SummaryRepository(mongo_db)
        for i in range(5):
            await repo.create(_summary(f"s{i}"))

        page1, total = await repo.list_all(page=1, page_size=2)
        assert total == 5
        assert len(page1) == 2

    @pytest.mark.asyncio
    async def test_average_safety_and_completeness_scores(self, mongo_db):
        repo = SummaryRepository(mongo_db)
        await repo.create(_summary("s1", safety=1.0, completeness=0.8))
        await repo.create(_summary("s2", safety=0.5, completeness=0.6))

        assert await repo.average_safety_score() == 0.75
        assert await repo.average_completeness_score() == 0.7

    @pytest.mark.asyncio
    async def test_average_with_no_data_returns_zero(self, mongo_db):
        repo = SummaryRepository(mongo_db)
        assert await repo.average_safety_score() == 0.0

    @pytest.mark.asyncio
    async def test_methods_are_safe_when_mongo_unavailable(self):
        repo = SummaryRepository(None)
        await repo.create(_summary("s1"))
        assert await repo.get_by_id("s1") is None
        assert await repo.list_for_patient("p1") == []
        assert await repo.list_all() == ([], 0)
        assert await repo.count() == 0
        assert await repo.average_safety_score() == 0.0
