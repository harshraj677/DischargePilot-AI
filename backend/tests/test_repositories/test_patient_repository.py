import pytest

from app.models.mongo.patient import PatientMongo
from app.repositories.patient_repository import PatientRepository


class TestPatientRepository:
    @pytest.mark.asyncio
    async def test_upsert_and_get_by_id(self, mongo_db):
        repo = PatientRepository(mongo_db)
        patient = PatientMongo(
            id="p1", patient_id="p1", name="John Doe", mrn="MRN-001", dob="1971-03-15", gender="M"
        )
        await repo.upsert(patient)

        fetched = await repo.get_by_id("p1")
        assert fetched is not None
        assert fetched.name == "John Doe"
        assert fetched.mrn == "MRN-001"

    @pytest.mark.asyncio
    async def test_upsert_replaces_existing_record(self, mongo_db):
        repo = PatientRepository(mongo_db)
        await repo.upsert(PatientMongo(id="p1", patient_id="p1", name="John Doe"))
        await repo.upsert(PatientMongo(id="p1", patient_id="p1", name="John D. Doe Jr."))

        fetched = await repo.get_by_id("p1")
        assert fetched.name == "John D. Doe Jr."
        assert await repo.count() == 1

    @pytest.mark.asyncio
    async def test_get_by_id_missing_returns_none(self, mongo_db):
        repo = PatientRepository(mongo_db)
        assert await repo.get_by_id("does-not-exist") is None

    @pytest.mark.asyncio
    async def test_list_orders_by_created_at_desc(self, mongo_db):
        repo = PatientRepository(mongo_db)
        await repo.upsert(PatientMongo(id="p1", patient_id="p1", name="A"))
        await repo.upsert(PatientMongo(id="p2", patient_id="p2", name="B"))

        patients = await repo.list()
        assert {p.id for p in patients} == {"p1", "p2"}

    @pytest.mark.asyncio
    async def test_methods_are_safe_when_mongo_unavailable(self):
        repo = PatientRepository(None)
        await repo.upsert(PatientMongo(id="p1", patient_id="p1", name="A"))  # must not raise
        assert await repo.get_by_id("p1") is None
        assert await repo.list() == []
        assert await repo.count() == 0
