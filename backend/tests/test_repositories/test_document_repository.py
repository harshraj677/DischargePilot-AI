import pytest

from app.models.mongo.document import DocumentMongo
from app.repositories.document_repository import DocumentRepository


class TestDocumentRepository:
    @pytest.mark.asyncio
    async def test_upsert_and_get_by_id(self, mongo_db):
        repo = DocumentRepository(mongo_db)
        doc = DocumentMongo(id="d1", patient_id="p1", document_type="admission_note", content="text")
        await repo.upsert(doc)

        fetched = await repo.get_by_id("d1")
        assert fetched is not None
        assert fetched.document_type == "admission_note"

    @pytest.mark.asyncio
    async def test_list_for_patient_filters_correctly(self, mongo_db):
        repo = DocumentRepository(mongo_db)
        await repo.upsert(DocumentMongo(id="d1", patient_id="p1", document_type="lab_report"))
        await repo.upsert(DocumentMongo(id="d2", patient_id="p2", document_type="lab_report"))

        docs = await repo.list_for_patient("p1")
        assert len(docs) == 1
        assert docs[0].id == "d1"

    @pytest.mark.asyncio
    async def test_count(self, mongo_db):
        repo = DocumentRepository(mongo_db)
        await repo.upsert(DocumentMongo(id="d1", patient_id="p1", document_type="lab_report"))
        await repo.upsert(DocumentMongo(id="d2", patient_id="p1", document_type="lab_report"))
        assert await repo.count() == 2

    @pytest.mark.asyncio
    async def test_methods_are_safe_when_mongo_unavailable(self):
        repo = DocumentRepository(None)
        await repo.upsert(DocumentMongo(id="d1", patient_id="p1", document_type="lab_report"))
        assert await repo.get_by_id("d1") is None
        assert await repo.list_for_patient("p1") == []
        assert await repo.count() == 0
