from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SummaryMongo(BaseModel):
    """Permanent discharge summary record in the `summaries` collection."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    patient_id: str
    summary_text: str
    status: str

    overall_safety_score: float = 0.0
    completeness_score: float = 0.0

    high_findings_count: int = 0
    medium_findings_count: int = 0
    low_findings_count: int = 0
    info_findings_count: int = 0

    created_at: datetime = Field(default_factory=datetime.utcnow)
