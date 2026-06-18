from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ReviewAction(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class ReviewActionMongo(BaseModel):
    """A clinician decision on a finding, stored in the `review_actions` collection."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id", default_factory=lambda: str(uuid.uuid4()))
    finding_id: str
    reviewer: str
    action: ReviewAction
    comments: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
