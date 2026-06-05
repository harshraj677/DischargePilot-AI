from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.safety.models import ReviewFlag, SafetyReport


class SummaryStatus(str, Enum):
    """Status of an individual summary section."""
    POPULATED = "populated"
    MISSING = "missing"
    REVIEW_REQUIRED = "review_required"
    PARTIAL = "partial"


class DischargeSummaryStatus(str, Enum):
    """Lifecycle state of the full discharge summary document."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class SummarySection(BaseModel):
    """One named section of the discharge summary."""

    name: str
    content: str = ""
    status: SummaryStatus = SummaryStatus.MISSING
    section_flags: List[ReviewFlag] = Field(default_factory=list)
    generated_by: str = "template"  # "template" | "claude" | "hybrid"
    source_facts_count: int = 0

    @property
    def has_flags(self) -> bool:
        return len(self.section_flags) > 0

    @property
    def needs_review(self) -> bool:
        return self.status == SummaryStatus.REVIEW_REQUIRED or self.has_flags


class DischargeSummary(BaseModel):
    """
    Complete AI-generated discharge summary for one patient / agent run.

    Always starts as PENDING_REVIEW — a clinician must approve before it
    is treated as the final document.
    """

    summary_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    patient_id: str
    agent_run_id: str

    # Core sections (populated by DischargeSummaryGenerator)
    patient_info: SummarySection = Field(default_factory=lambda: SummarySection(name="patient_info"))
    hospital_info: SummarySection = Field(default_factory=lambda: SummarySection(name="hospital_info"))
    principal_diagnosis: SummarySection = Field(default_factory=lambda: SummarySection(name="principal_diagnosis"))
    secondary_diagnoses: SummarySection = Field(default_factory=lambda: SummarySection(name="secondary_diagnoses"))
    hospital_course: SummarySection = Field(default_factory=lambda: SummarySection(name="hospital_course"))
    procedures: SummarySection = Field(default_factory=lambda: SummarySection(name="procedures"))
    allergies: SummarySection = Field(default_factory=lambda: SummarySection(name="allergies"))
    admission_medications: SummarySection = Field(default_factory=lambda: SummarySection(name="admission_medications"))
    discharge_medications: SummarySection = Field(default_factory=lambda: SummarySection(name="discharge_medications"))
    medication_changes: SummarySection = Field(default_factory=lambda: SummarySection(name="medication_changes"))
    lab_results: SummarySection = Field(default_factory=lambda: SummarySection(name="lab_results"))
    pending_results: SummarySection = Field(default_factory=lambda: SummarySection(name="pending_results"))
    follow_up: SummarySection = Field(default_factory=lambda: SummarySection(name="follow_up"))
    discharge_condition: SummarySection = Field(default_factory=lambda: SummarySection(name="discharge_condition"))

    # Meta
    status: DischargeSummaryStatus = DischargeSummaryStatus.PENDING_REVIEW
    safety_report: Optional[SafetyReport] = None
    completeness_score: float = 0.0
    safety_score: float = 0.0
    review_flags: List[ReviewFlag] = Field(default_factory=list)

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    @property
    def sections(self) -> List[SummarySection]:
        return [
            self.patient_info, self.hospital_info, self.principal_diagnosis,
            self.secondary_diagnoses, self.hospital_course, self.procedures,
            self.allergies, self.admission_medications, self.discharge_medications,
            self.medication_changes, self.lab_results, self.pending_results,
            self.follow_up, self.discharge_condition,
        ]

    @property
    def populated_section_count(self) -> int:
        return sum(1 for s in self.sections if s.status != SummaryStatus.MISSING)

    @property
    def flags_requiring_acknowledgment(self) -> List[ReviewFlag]:
        return [f for f in self.review_flags if f.requires_acknowledgment]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary_id": self.summary_id,
            "patient_id": self.patient_id,
            "agent_run_id": self.agent_run_id,
            "status": self.status.value,
            "generated_at": self.generated_at.isoformat(),
            "completeness_score": round(self.completeness_score, 3),
            "safety_score": round(self.safety_score, 3),
            "sections": {s.name: {"content": s.content, "status": s.status.value} for s in self.sections},
            "review_flags": [
                {
                    "flag_id": f.flag_id,
                    "category": f.category.value,
                    "severity": f.severity.value,
                    "description": f.description,
                    "section": f.affected_section.value,
                    "recommendation": f.recommendation,
                    "requires_acknowledgment": f.requires_acknowledgment,
                }
                for f in self.review_flags
            ],
        }
