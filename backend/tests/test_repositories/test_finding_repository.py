import pytest

from app.models.mongo.finding import FindingMongo
from app.repositories.finding_repository import FindingRepository


def _finding(id_, severity, category, title="title", explanation="", summary_id="s1"):
    return FindingMongo(
        id=id_,
        summary_id=summary_id,
        severity=severity,
        category=category,
        title=title,
        explanation=explanation or title,
        recommendation="Review",
    )


class TestFindingRepository:
    @pytest.mark.asyncio
    async def test_create_many_and_get_by_summary_id(self, mongo_db):
        repo = FindingRepository(mongo_db)
        await repo.create_many([
            _finding("f1", "HIGH", "missing_data"),
            _finding("f2", "LOW", "conflict"),
        ])

        findings = await repo.get_by_summary_id("s1")
        assert len(findings) == 2
        assert await repo.count() == 2

    @pytest.mark.asyncio
    async def test_create_many_with_empty_list_is_noop(self, mongo_db):
        repo = FindingRepository(mongo_db)
        await repo.create_many([])
        assert await repo.count() == 0

    @pytest.mark.asyncio
    async def test_count_high_risk_includes_critical_and_high(self, mongo_db):
        repo = FindingRepository(mongo_db)
        await repo.create_many([
            _finding("f1", "CRITICAL", "conflict"),
            _finding("f2", "HIGH", "missing_data"),
            _finding("f3", "MEDIUM", "lab"),
            _finding("f4", "LOW", "other"),
        ])
        assert await repo.count_high_risk() == 2

    @pytest.mark.asyncio
    async def test_severity_distribution_rolls_critical_into_high(self, mongo_db):
        repo = FindingRepository(mongo_db)
        await repo.create_many([
            _finding("f1", "CRITICAL", "conflict"),
            _finding("f2", "HIGH", "missing_data"),
            _finding("f3", "MEDIUM", "lab"),
            _finding("f4", "LOW", "other"),
            _finding("f5", "INFO", "other"),
        ])
        distribution = await repo.severity_distribution()
        assert distribution == {"HIGH": 2, "MEDIUM": 1, "LOW": 1, "INFO": 1}

    @pytest.mark.asyncio
    async def test_top_missing_fields_counts_keyword_matches(self, mongo_db):
        repo = FindingRepository(mongo_db)
        await repo.create_many([
            _finding("f1", "HIGH", "missing_data", title="Allergy status is not documented"),
            _finding("f2", "HIGH", "missing_data", title="Allergy status is not documented"),
            _finding("f3", "HIGH", "missing_data", title="Admission date is not documented"),
            _finding("f4", "HIGH", "conflict", title="Allergy status mentioned but not a missing-data finding"),
        ])
        results = {row["field"]: row["count"] for row in await repo.top_missing_fields()}
        assert results["allergy_status"] == 2
        assert results["admission_date"] == 1
        assert results["hospital_course"] == 0

    @pytest.mark.asyncio
    async def test_top_conflicts_groups_by_title(self, mongo_db):
        repo = FindingRepository(mongo_db)
        await repo.create_many([
            _finding("f1", "CRITICAL", "conflict", title="ALLERGY CONFLICT: Penicillin"),
            _finding("f2", "CRITICAL", "conflict", title="ALLERGY CONFLICT: Penicillin"),
            _finding("f3", "MEDIUM", "medication_discrepancy", title="Dose mismatch"),
        ])
        results = await repo.top_conflicts()
        assert results[0] == {"title": "ALLERGY CONFLICT: Penicillin", "count": 2}

    @pytest.mark.asyncio
    async def test_methods_are_safe_when_mongo_unavailable(self):
        repo = FindingRepository(None)
        await repo.create_many([_finding("f1", "HIGH", "missing_data")])
        assert await repo.get_by_summary_id("s1") == []
        assert await repo.count() == 0
        assert await repo.count_high_risk() == 0
        assert await repo.severity_distribution() == {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        assert await repo.top_conflicts() == []
