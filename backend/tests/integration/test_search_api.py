from __future__ import annotations

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.dependencies import get_mongo_database
from app.main import app
from app.models.mongo.patient import PatientMongo
from app.repositories.patient_repository import PatientRepository


@pytest.fixture()
def mongo_db():
    client = AsyncMongoMockClient()
    return client["test_dischargepilot"]


@pytest.fixture()
def search_client(db, mongo_db):
    from app.dependencies import get_db
    from fastapi.testclient import TestClient

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_mongo_database] = lambda: mongo_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


class TestSearchAPI:
    @pytest.mark.asyncio
    async def test_search_by_patient_name(self, search_client, mongo_db):
        await PatientRepository(mongo_db).upsert(PatientMongo(id="p1", patient_id="p1", name="John Doe", mrn="MRN-1"))

        response = search_client.get("/api/v1/search", params={"patient_name": "john"})
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["patient_id"] == "p1"

    def test_search_with_no_params_returns_empty(self, search_client):
        response = search_client.get("/api/v1/search")
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}
