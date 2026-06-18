import pytest
from mongomock_motor import AsyncMongoMockClient

from app.models.mongo.document import DocumentMongo
from app.models.mongo.finding import FindingMongo
from app.models.mongo.patient import PatientMongo
from app.models.mongo.review_action import ReviewAction, ReviewActionMongo
from app.models.mongo.summary import SummaryMongo
from app.repositories.document_repository import DocumentRepository
from app.repositories.finding_repository import FindingRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.review_repository import ReviewRepository
from app.repositories.summary_repository import SummaryRepository
from app.services.timeline_service import TimelineService


@pytest.fixture()
def mongo_db():
    client = AsyncMongoMockClient()
    return client["test_dischargepilot"]


async def _seed(mongo_db):
    await PatientRepository(mongo_db).upsert(PatientMongo(
        id="p1", patient_id="p1", name="John Doe", mrn="MRN-1", dob="1971-03-15", gender="M",
    ))
    await DocumentRepository(mongo_db).upsert(DocumentMongo(id="d1", patient_id="p1", document_type="admission_note"))
    await SummaryRepository(mongo_db).create(SummaryMongo(
        id="s1", patient_id="p1", summary_text="t", status="PENDING_REVIEW",
        overall_safety_score=0.85, completeness_score=0.9,
    ))
    await FindingRepository(mongo_db).create_many([
        FindingMongo(id="f1", summary_id="s1", severity="HIGH", category="missing_data",
                     title="Allergy status missing", explanation="x", recommendation="y"),
    ])
    await ReviewRepository(mongo_db).create(ReviewActionMongo(
        finding_id="f1", reviewer="dr.chen", action=ReviewAction.APPROVED,
    ))


class TestTimelineService:
    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_patient(self, mongo_db):
        result = await TimelineService(mongo_db).get_patient_timeline("does-not-exist")
        assert result is None

    @pytest.mark.asyncio
    async def test_builds_full_chronological_timeline(self, mongo_db):
        await _seed(mongo_db)
        timeline = await TimelineService(mongo_db).get_patient_timeline("p1")

        assert timeline is not None
        assert timeline.patient.name == "John Doe"
        assert timeline.latest_safety_score == 0.85
        assert timeline.latest_completeness_score == 0.9

        event_types = [e.type for e in timeline.events]
        assert event_types == [
            "patient_created", "document_uploaded", "summary_generated",
            "finding_created", "finding_approved",
        ]
        # Sorted chronologically.
        assert all(timeline.events[i].timestamp <= timeline.events[i + 1].timestamp
                    for i in range(len(timeline.events) - 1))

    @pytest.mark.asyncio
    async def test_safe_when_mongo_unavailable(self):
        result = await TimelineService(None).get_patient_timeline("p1")
        assert result is None
