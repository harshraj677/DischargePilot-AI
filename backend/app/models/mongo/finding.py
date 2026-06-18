from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class FindingMongo(BaseModel):
    """Permanent safety/review finding record in the `findings` collection."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    summary_id: str

    severity: str
    category: str
    title: str
    explanation: str
    recommendation: str
    confidence: str = "Moderate"
    requires_acknowledgment: bool = True
    evidence: List[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)
