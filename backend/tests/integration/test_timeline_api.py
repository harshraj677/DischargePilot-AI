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
def timeline_client(db, mongo_db):
    from app.dependencies import get_db
    from fastapi.testclient import TestClient

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_mongo_database] = lambda: mongo_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


class TestTimelineAPI:
    @pytest.mark.asyncio
    async def test_returns_timeline_for_known_patient(self, timeline_client, mongo_db):
        await PatientRepository(mongo_db).upsert(PatientMongo(id="p1", patient_id="p1", name="John Doe"))

        response = timeline_client.get("/api/v1/patients/p1/timeline")
        assert response.status_code == 200
        body = response.json()
        assert body["patient"]["name"] == "John Doe"
        assert body["events"][0]["type"] == "patient_created"

    def test_returns_404_for_unknown_patient(self, timeline_client):
        response = timeline_client.get("/api/v1/patients/does-not-exist/timeline")
        assert response.status_code == 404
