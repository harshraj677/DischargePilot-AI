from __future__ import annotations

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.dependencies import get_mongo_database
from app.main import app
from app.models.mongo.finding import FindingMongo
from app.models.mongo.summary import SummaryMongo
from app.repositories.finding_repository import FindingRepository
from app.repositories.summary_repository import SummaryRepository


@pytest.fixture()
def mongo_db():
    client = AsyncMongoMockClient()
    return client["test_dischargepilot"]


@pytest.fixture()
def analytics_client(db, mongo_db):
    from app.dependencies import get_db

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_mongo_database] = lambda: mongo_db

    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


class TestAnalyticsDashboardAPI:
    def test_dashboard_with_no_data_returns_zeroed_metrics(self, analytics_client):
        response = analytics_client.get("/api/v1/analytics/dashboard")
        assert response.status_code == 200
        body = response.json()
        assert body["total_summaries"] == 0
        assert body["average_safety_score"] == 0.0
        assert body["severity_distribution"] == {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        assert body["top_conflicts"] == []

    @pytest.mark.asyncio
    async def test_dashboard_reflects_seeded_data(self, analytics_client, mongo_db):
        await SummaryRepository(mongo_db).create(SummaryMongo(
            id="s1", patient_id="p1", summary_text="t", status="PENDING_REVIEW",
            overall_safety_score=0.85, completeness_score=0.9, high_findings_count=1,
        ))
        await FindingRepository(mongo_db).create_many([
            FindingMongo(id="f1", summary_id="s1", severity="HIGH", category="missing_data",
                         title="Allergy status is not documented", explanation="x", recommendation="y"),
        ])

        response = analytics_client.get("/api/v1/analytics/dashboard")
        assert response.status_code == 200
        body = response.json()
        assert body["total_summaries"] == 1
        assert body["total_findings"] == 1
        assert body["average_safety_score"] == 0.85
        assert body["high_risk_findings"] == 1


class TestReviewActionAPI:
    def test_record_review_action_then_appears_in_history(self, analytics_client):
        record_response = analytics_client.post(
            "/api/v1/analytics/findings/f1/review-actions",
            json={"reviewer": "dr.chen", "action": "APPROVED", "comments": "looks fine"},
        )
        assert record_response.status_code == 200
        body = record_response.json()
        assert body["finding_id"] == "f1"
        assert body["action"] == "APPROVED"

        history_response = analytics_client.get("/api/v1/analytics/review-history")
        assert history_response.status_code == 200
        history = history_response.json()
        assert history["total"] == 1
        assert history["items"][0]["finding_id"] == "f1"

    def test_review_history_filters_by_action(self, analytics_client):
        analytics_client.post(
            "/api/v1/analytics/findings/f1/review-actions",
            json={"reviewer": "a", "action": "APPROVED"},
        )
        analytics_client.post(
            "/api/v1/analytics/findings/f2/review-actions",
            json={"reviewer": "b", "action": "REJECTED"},
        )

        response = analytics_client.get("/api/v1/analytics/review-history", params={"action": "REJECTED"})
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["finding_id"] == "f2"
