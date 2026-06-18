"""
Phase 6 Safety Engine models.

Every clinical claim in DischargePilot must pass through the safety gate before
reaching the discharge summary. These models represent safety findings, review flags,
and the overall safety report that gates summary generation.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.enums import SafetySeverity


# ── Safety-specific enums ─────────────────────────────────────────────────────

class SafetyStatus(str, Enum):
    """
    Overall outcome of the safety validation pass.

    Values are uppercase to match every other enum exposed to the frontend
    (SafetySeverity, AgentRunStatus, etc.) and the frontend's SafetyStatus
    literal type ("APPROVED" | "REVIEW_REQUIRED" | "BLOCKED"). This used to
    serialize lowercase, which crashed the Safety Review page —
    statusConfig[report.overall_status] looked up "blocked" against
    uppercase-only keys and returned undefined, then `statusCfg!.bg` threw.
    """
    APPROVED = "APPROVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class ReviewFlagCategory(str, Enum):
    MISSING_DATA = "missing_data"
    CONFLICT = "conflict"
    MEDICATION_DISCREPANCY = "medication_discrepancy"
    LOW_CONFIDENCE = "low_confidence"
    PENDING_RESULT = "pending_result"
    SAFETY_CONCERN = "safety_concern"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    # Added for LLMClinicalSafetyReviewer's category vocabulary
    # (conflict|missing_data|pending_result|medication|lab|guideline|other) —
    # kept distinct from the deterministic-validator categories above
    # rather than reusing them, since e.g. "medication" (the LLM's generic
    # medication-related bucket) is broader than MEDICATION_DISCREPANCY.
    MEDICATION = "medication"
    LAB = "lab"
    GUIDELINE = "guideline"
    OTHER = "other"


class SectionName(str, Enum):
    """Discharge summary sections for flag targeting."""
    DEMOGRAPHICS = "patient_demographics"
    HOSPITAL_INFO = "hospital_info"
    PRINCIPAL_DIAGNOSIS = "principal_diagnosis"
    SECONDARY_DIAGNOSES = "secondary_diagnoses"
    HOSPITAL_COURSE = "hospital_course"
    PROCEDURES = "procedures"
    ALLERGIES = "allergies"
    ADMISSION_MEDICATIONS = "admission_medications"
    DISCHARGE_MEDICATIONS = "discharge_medications"
    MEDICATION_CHANGES = "medication_changes"
    LAB_RESULTS = "lab_results"
    PENDING_RESULTS = "pending_results"
    FOLLOW_UP = "follow_up_instructions"
    DISCHARGE_CONDITION = "discharge_condition"
    GLOBAL = "global"


# ── Core safety models ────────────────────────────────────────────────────────

class SafetyFinding(BaseModel):
    """A single atomic safety concern identified by a validator."""

    finding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    validator: str
    severity: SafetySeverity
    description: str
    affected_section: SectionName = SectionName.GLOBAL
    affected_items: List[str] = Field(default_factory=list)
    # List of evidence strings (source record excerpt, guideline citation,
    # etc.) — required by LLMClinicalSafetyReviewer's spec: "Never generate
    # findings without evidence." Deterministic validators leave this empty
    # (their evidence is implicit in `description`/`affected_items`).
    evidence: List[str] = Field(default_factory=list)
    source_documents: List[str] = Field(default_factory=list)
    # "High" | "Moderate" | "Low" — set by LLM-driven validators (e.g.
    # LLMClinicalSafetyReviewer); deterministic validators leave the
    # default since they don't have a notion of confidence.
    confidence: str = "Moderate"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewFlag(BaseModel):
    """
    A flag surfaced to the clinician for review or acknowledgment.

    Flags with requires_acknowledgment=True MUST be explicitly addressed
    by the clinician before the summary can be marked approved.
    """

    flag_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: ReviewFlagCategory
    severity: SafetySeverity
    description: str
    affected_section: SectionName
    recommendation: str
    source_documents: List[str] = Field(default_factory=list)
    requires_acknowledgment: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def display_label(self) -> str:
        emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "INFO": "🔵"}.get(
            self.severity.value, "⚪"
        )
        return f"{emoji} [{self.severity.value}] {self.category.value.upper()}"


class ValidationResult(BaseModel):
    """Output of one validator run."""

    validator_name: str
    passed: bool
    severity: SafetySeverity
    findings: List[SafetyFinding] = Field(default_factory=list)
    review_flags: List[ReviewFlag] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    error: Optional[str] = None

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == SafetySeverity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == SafetySeverity.HIGH)


class SafetyReport(BaseModel):
    """
    Aggregated safety report produced by SafetyValidationEngine.
    This is the gate that controls whether summary generation can proceed.
    """

    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    patient_id: str
    run_id: str
    overall_status: SafetyStatus
    validation_results: List[ValidationResult] = Field(default_factory=list)
    review_flags: List[ReviewFlag] = Field(default_factory=list)
    safety_findings: List[SafetyFinding] = Field(default_factory=list)

    can_generate_summary: bool
    blocking_issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    completeness_score: float = 0.0
    safety_score: float = Field(default=1.0, description="1.0 = fully safe, 0.0 = critical issues")

    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def critical_flags(self) -> List[ReviewFlag]:
        return [f for f in self.review_flags if f.severity == SafetySeverity.CRITICAL]

    @property
    def requires_acknowledgment_count(self) -> int:
        return sum(1 for f in self.review_flags if f.requires_acknowledgment)

    def flags_for_section(self, section: SectionName) -> List[ReviewFlag]:
        return [f for f in self.review_flags if f.affected_section == section]

    def summary_line(self) -> str:
        return (
            f"Safety: {self.overall_status.value} | "
            f"Score: {self.safety_score:.0%} | "
            f"Flags: {len(self.review_flags)} | "
            f"Blocking: {len(self.blocking_issues)} | "
            f"Can generate: {self.can_generate_summary}"
        )


# ── Tool framework models (Phase 5) ──────────────────────────────────────────

class ToolStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    RETRYING = "retrying"
    SKIPPED = "skipped"


class ToolError(BaseModel):
    error_code: str
    message: str
    tool_name: str
    attempt: int
    is_retryable: bool = True
    context: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=datetime.utcnow)


class ToolExecutionRecord(BaseModel):
    """Complete audit record for one tool execution including all attempts."""

    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str
    task_id: str
    status: ToolStatus
    attempts: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    tokens_used: int = 0
    facts_extracted: int = 0
    findings: Dict[str, Any] = Field(default_factory=dict)
    errors: List[ToolError] = Field(default_factory=list)
    trace_notes: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status == ToolStatus.SUCCEEDED
