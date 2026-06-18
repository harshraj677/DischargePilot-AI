from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies import get_mongo_database
from app.services.search_service import SearchService

router = APIRouter(tags=["Search"])


@router.get("/search")
async def search(
    patient_name: Optional[str] = None,
    mrn: Optional[str] = None,
    summary_id: Optional[str] = None,
    document_id: Optional[str] = None,
    db: Optional[AsyncIOMotorDatabase] = Depends(get_mongo_database),
) -> Dict[str, Any]:
    """Global search by patient name, MRN, summary id, or document id."""
    results = await SearchService(db).search(
        patient_name=patient_name, mrn=mrn, summary_id=summary_id, document_id=document_id
    )
    return {"items": [r.model_dump(mode="json") for r in results], "total": len(results)}
