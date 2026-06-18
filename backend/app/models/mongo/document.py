from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentMongo(BaseModel):
    """Permanent copy of an uploaded source record in the `documents` collection."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    patient_id: str
    document_type: str
    content: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
