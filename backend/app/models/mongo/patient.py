from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PatientMongo(BaseModel):
    """Permanent patient record in the `patients` collection. `_id` mirrors the SQL patient id."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    patient_id: str
    name: str
    mrn: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
