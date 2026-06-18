from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies import get_mongo_database
from app.services.timeline_service import PatientTimelineResponse, TimelineService

router = APIRouter(prefix="/patients", tags=["Timeline"])


@router.get("/{patient_id}/timeline", response_model=PatientTimelineResponse)
async def get_patient_timeline(
    patient_id: str,
    db: Optional[AsyncIOMotorDatabase] = Depends(get_mongo_database),
) -> PatientTimelineResponse:
    """Full chronological timeline: patient creation, document uploads, summaries, findings, and clinician actions."""
    timeline = await TimelineService(db).get_patient_timeline(patient_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail=f"No MongoDB record found for patient {patient_id}")
    return timeline
