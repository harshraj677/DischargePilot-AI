import pytest

from app.models.mongo.review_action import ReviewAction, ReviewActionMongo
from app.repositories.review_repository import ReviewRepository


class TestReviewRepository:
    @pytest.mark.asyncio
    async def test_create_and_list_by_finding(self, mongo_db):
        repo = ReviewRepository(mongo_db)
        await repo.create(ReviewActionMongo(finding_id="f1", reviewer="dr.chen", action=ReviewAction.APPROVED))

        actions = await repo.list_by_finding("f1")
        assert len(actions) == 1
        assert actions[0].reviewer == "dr.chen"

    @pytest.mark.asyncio
    async def test_count_by_action(self, mongo_db):
        repo = ReviewRepository(mongo_db)
        await repo.create(ReviewActionMongo(finding_id="f1", reviewer="a", action=ReviewAction.APPROVED))
        await repo.create(ReviewActionMongo(finding_id="f2", reviewer="b", action=ReviewAction.REJECTED))
        await repo.create(ReviewActionMongo(finding_id="f3", reviewer="c", action=ReviewAction.APPROVED))

        assert await repo.count_by_action("APPROVED") == 2
        assert await repo.count_by_action("REJECTED") == 1
        assert await repo.count() == 3

    @pytest.mark.asyncio
    async def test_list_all_filters_by_action_and_paginates(self, mongo_db):
        repo = ReviewRepository(mongo_db)
        for i in range(3):
            await repo.create(ReviewActionMongo(finding_id=f"f{i}", reviewer="a", action=ReviewAction.APPROVED))
        await repo.create(ReviewActionMongo(finding_id="f9", reviewer="a", action=ReviewAction.REJECTED))

        items, total = await repo.list_all(page=1, page_size=2, action="APPROVED")
        assert total == 3
        assert len(items) == 2
        assert all(item.action == ReviewAction.APPROVED for item in items)

    @pytest.mark.asyncio
    async def test_methods_are_safe_when_mongo_unavailable(self):
        repo = ReviewRepository(None)
        await repo.create(ReviewActionMongo(finding_id="f1", reviewer="a", action=ReviewAction.APPROVED))
        assert await repo.list_by_finding("f1") == []
        assert await repo.list_all() == ([], 0)
        assert await repo.count_by_action("APPROVED") == 0
        assert await repo.count() == 0
