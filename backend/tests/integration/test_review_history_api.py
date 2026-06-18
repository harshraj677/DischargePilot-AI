from __future__ import annotations

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.dependencies import get_mongo_database
from app.main import app
from app.models.mongo.finding import FindingMongo
from app.models.mongo.patient import PatientMongo
from app.models.mongo.review_action import ReviewAction, ReviewActionMongo
from app.models.mongo.summary import SummaryMongo
from app.repositories.finding_repository import FindingRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.review_repository import ReviewRepository
from app.repositories.summary_repository import SummaryRepository


@pytest.fixture()
def mongo_db():
    client = AsyncMongoMockClient()
    return client["test_dischargepilot"]


@pytest.fixture()
def review_client(db, mongo_db):
    from app.dependencies import get_db
    from fastapi.testclient import TestClient

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_mongo_database] = lambda: mongo_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


class TestReviewHistoryAPI:
    @pytest.mark.asyncio
    async def test_history_endpoint_returns_joined_data(self, review_client, mongo_db):
        await PatientRepository(mongo_db).upsert(PatientMongo(id="p1", patient_id="p1", name="Jane Roe"))
        await SummaryRepository(mongo_db).create(SummaryMongo(
            id="s1", patient_id="p1", summary_text="t", status="PENDING_REVIEW",
        ))
        await FindingRepository(mongo_db).create_many([
            FindingMongo(id="f1", summary_id="s1", severity="HIGH", category="missing_data",
                         title="Allergy status missing", explanation="x", recommendation="y"),
        ])
        await ReviewRepository(mongo_db).create(
            ReviewActionMongo(finding_id="f1", reviewer="dr.chen", action=ReviewAction.APPROVED)
        )

        response = review_client.get("/api/v1/review/history")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["patient_name"] == "Jane Roe"
        assert body["items"][0]["severity"] == "HIGH"

    def test_history_endpoint_empty_is_safe(self, review_client):
        response = review_client.get("/api/v1/review/history")
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}

    def test_history_endpoint_filters_by_severity_query_param(self, review_client):
        response = review_client.get("/api/v1/review/history", params={"severity": "high"})
        assert response.status_code == 200
