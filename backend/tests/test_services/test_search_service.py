import pytest
from mongomock_motor import AsyncMongoMockClient

from app.models.mongo.document import DocumentMongo
from app.models.mongo.patient import PatientMongo
from app.models.mongo.summary import SummaryMongo
from app.repositories.document_repository import DocumentRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.summary_repository import SummaryRepository
from app.services.search_service import SearchService


@pytest.fixture()
def mongo_db():
    client = AsyncMongoMockClient()
    return client["test_dischargepilot"]


async def _seed(mongo_db):
    await PatientRepository(mongo_db).upsert(PatientMongo(id="p1", patient_id="p1", name="John Doe", mrn="MRN-001"))
    await PatientRepository(mongo_db).upsert(PatientMongo(id="p2", patient_id="p2", name="Jane Roe", mrn="MRN-002"))
    await DocumentRepository(mongo_db).upsert(DocumentMongo(id="d1", patient_id="p1", document_type="admission_note"))
    await SummaryRepository(mongo_db).create(SummaryMongo(
        id="s1", patient_id="p1", summary_text="t", status="PENDING_REVIEW",
        overall_safety_score=0.9, completeness_score=0.8,
    ))


class TestSearchService:
    @pytest.mark.asyncio
    async def test_search_by_patient_name_partial_case_insensitive(self, mongo_db):
        await _seed(mongo_db)
        results = await SearchService(mongo_db).search(patient_name="john")
        assert len(results) == 1
        assert results[0].patient_id == "p1"
        assert results[0].summary_id == "s1"
        assert results[0].safety_score == 0.9

    @pytest.mark.asyncio
    async def test_search_by_mrn(self, mongo_db):
        await _seed(mongo_db)
        results = await SearchService(mongo_db).search(mrn="MRN-002")
        assert len(results) == 1
        assert results[0].patient_id == "p2"
        assert results[0].summary_id is None  # no summary for this patient

    @pytest.mark.asyncio
    async def test_search_by_summary_id(self, mongo_db):
        await _seed(mongo_db)
        results = await SearchService(mongo_db).search(summary_id="s1")
        assert len(results) == 1
        assert results[0].patient_name == "John Doe"

    @pytest.mark.asyncio
    async def test_search_by_document_id(self, mongo_db):
        await _seed(mongo_db)
        results = await SearchService(mongo_db).search(document_id="d1")
        assert len(results) == 1
        assert results[0].patient_id == "p1"
        assert results[0].summary_id == "s1"

    @pytest.mark.asyncio
    async def test_search_with_no_criteria_returns_empty(self, mongo_db):
        await _seed(mongo_db)
        assert await SearchService(mongo_db).search() == []

    @pytest.mark.asyncio
    async def test_search_with_unknown_summary_id_returns_empty(self, mongo_db):
        await _seed(mongo_db)
        assert await SearchService(mongo_db).search(summary_id="does-not-exist") == []

    @pytest.mark.asyncio
    async def test_safe_when_mongo_unavailable(self):
        results = await SearchService(None).search(patient_name="john")
        assert results == []
