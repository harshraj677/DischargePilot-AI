# DischargePilot AI — Pydantic Data Models

---

## Design Principles

1. Every model has explicit field types — no `Any`
2. All fields that can be absent have `Optional[T]` with `None` defaults
3. Enums replace raw strings for all status and type fields
4. Evidence references are embedded in every extracted entity
5. Confidence and uncertainty fields are present in all LLM-generated outputs
6. Models are split by concern: internal agent models vs. API request/response models

---

## Enums

```python
from enum import Enum

class DocumentType(str, Enum):
    ADMISSION_NOTE = "admission_note"
    PROGRESS_NOTE = "progress_note"
    LAB_REPORT = "lab_report"
    MEDICATION_RECORD = "medication_record"

class DocumentStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"

class AgentStatus(str, Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    RE_PLANNING = "RE_PLANNING"
    SAFETY_VALIDATING = "SAFETY_VALIDATING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"
    INCOMPLETE = "INCOMPLETE"

class SummaryStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    ESCALATED = "ESCALATED"
    INCOMPLETE = "INCOMPLETE"

class SafetySeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    INFO = "INFO"

class SafetyCategory(str, Enum):
    MEDICATION_CONFLICT = "MEDICATION_CONFLICT"
    ALLERGY_CONFLICT = "ALLERGY_CONFLICT"
    DIAGNOSIS_CONFLICT = "DIAGNOSIS_CONFLICT"
    MISSING_FIELD = "MISSING_FIELD"
    PENDING_RESULT = "PENDING_RESULT"
    DOSE_DISCREPANCY = "DOSE_DISCREPANCY"
    POLYPHARMACY = "POLYPHARMACY"
    UNVERIFIED_STATEMENT = "UNVERIFIED_STATEMENT"

class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    NEEDS_REVIEW = "NEEDS_REVIEW"

class FeedbackIssueType(str, Enum):
    INCORRECT = "INCORRECT"
    INCOMPLETE = "INCOMPLETE"
    HALLUCINATED = "HALLUCINATED"
    POOR_LANGUAGE = "POOR_LANGUAGE"
    MISSING_INFO = "MISSING_INFO"
    GOOD = "GOOD"

class DischargeCondition(str, Enum):
    STABLE = "STABLE"
    IMPROVED = "IMPROVED"
    UNCHANGED = "UNCHANGED"
    DETERIORATED = "DETERIORATED"
    CRITICAL = "CRITICAL"
    DECEASED = "DECEASED"
    UNKNOWN = "UNKNOWN"
```

---

## Core Domain Models

### Patient

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime

class PatientBase(BaseModel):
    mrn: str = Field(..., description="Medical Record Number", example="MRN-2025-00123")
    first_name: str
    last_name: str
    date_of_birth: date
    gender: Optional[str] = None
    admission_date: Optional[datetime] = None
    discharge_date: Optional[datetime] = None
    attending_md: Optional[str] = None
    ward: Optional[str] = None

class PatientCreate(PatientBase):
    pass

class PatientResponse(PatientBase):
    id: str
    document_count: int = 0
    summary_status: Optional[SummaryStatus] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

---

### Document

```python
class DocumentBase(BaseModel):
    patient_id: str
    document_type: DocumentType
    file_name: str

class DocumentCreate(DocumentBase):
    file_path: str
    file_size_bytes: Optional[int] = None

class DocumentResponse(DocumentBase):
    id: str
    file_size_bytes: Optional[int] = None
    page_count: Optional[int] = None
    status: DocumentStatus
    processing_error: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ProcessedDocument(BaseModel):
    id: str
    document_type: DocumentType
    file_name: str
    page_count: int
    page_chunks: List["PageChunk"]

class PageChunk(BaseModel):
    page: int
    text: str
    char_count: int
```

---

### Evidence Reference

The foundational model for grounding every clinical statement.

```python
class EvidenceRef(BaseModel):
    doc_id: str
    document_type: DocumentType
    file_name: str
    page: int
    excerpt: str = Field(..., description="Exact text excerpt from source document")
    char_start: Optional[int] = None
    char_end: Optional[int] = None
```

---

### Diagnosis

```python
class Diagnosis(BaseModel):
    name: str = Field(..., description="Diagnosis name as written in source")
    icd_hint: Optional[str] = Field(None, description="Possible ICD-10 code if identifiable from context")
    is_primary: bool = False
    admission_diagnosis: bool = False
    discharge_diagnosis: bool = False
    onset_date: Optional[str] = None
    status: Optional[str] = None  # active, resolved, chronic
    confidence: Confidence = Confidence.HIGH
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    notes: Optional[str] = None
    needs_review: bool = False

class DiagnosisList(BaseModel):
    principal_diagnosis: Optional[Diagnosis] = None
    secondary_diagnoses: List[Diagnosis] = Field(default_factory=list)
    extraction_notes: Optional[str] = None
    missing_info: Optional[str] = None
```

---

### Medication

```python
class Medication(BaseModel):
    name: str = Field(..., description="Medication name exactly as written in source")
    generic_name: Optional[str] = None
    dose: Optional[str] = None
    route: Optional[str] = None   # PO, IV, SQ, topical, etc.
    frequency: Optional[str] = None  # BID, TID, QD, PRN, etc.
    indication: Optional[str] = None
    start_date: Optional[str] = None
    stop_date: Optional[str] = None
    prescribing_source: DocumentType  # Which document this came from
    is_new_at_discharge: Optional[bool] = None
    is_changed_at_discharge: Optional[bool] = None
    is_discontinued: Optional[bool] = None
    confidence: Confidence = Confidence.HIGH
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    notes: Optional[str] = None
    needs_review: bool = False

class MedicationChange(BaseModel):
    medication_name: str
    change_type: str  # NEW | DOSE_CHANGED | DISCONTINUED | CONTINUED
    previous_dose: Optional[str] = None
    new_dose: Optional[str] = None
    reason: Optional[str] = None
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)

class MedicationReconciliation(BaseModel):
    admission_medications: List[Medication] = Field(default_factory=list)
    discharge_medications: List[Medication] = Field(default_factory=list)
    changes: List[MedicationChange] = Field(default_factory=list)
    discrepancies: List["MedicationDiscrepancy"] = Field(default_factory=list)
    total_reconciled: int = 0
    has_conflicts: bool = False
    reconciliation_notes: Optional[str] = None

class MedicationDiscrepancy(BaseModel):
    medication_name: str
    description: str
    doc_1: EvidenceRef
    doc_2: EvidenceRef
    severity: SafetySeverity
```

---

### Procedure

```python
class Procedure(BaseModel):
    name: str
    date_performed: Optional[str] = None
    performing_provider: Optional[str] = None
    laterality: Optional[str] = None  # left, right, bilateral
    outcome: Optional[str] = None
    confidence: Confidence = Confidence.HIGH
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    needs_review: bool = False
```

---

### Lab Result

```python
class LabResult(BaseModel):
    test_name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    interpretation: Optional[str] = None  # normal, high, low, critical
    collection_date: Optional[str] = None
    status: str = "FINAL"  # FINAL | PENDING | PRELIMINARY | CORRECTED
    is_pending: bool = False
    is_critical: bool = False
    confidence: Confidence = Confidence.HIGH
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)

class LabPanel(BaseModel):
    panel_name: str
    collection_date: Optional[str] = None
    results: List[LabResult] = Field(default_factory=list)
    has_pending: bool = False
    has_critical: bool = False
```

---

### Conflict

```python
class Conflict(BaseModel):
    id: str
    conflict_type: str  # DIAGNOSIS | MEDICATION | ALLERGY | LAB_VALUE | DATE | OTHER
    description: str = Field(..., description="Human-readable description of the conflict")
    source_1: EvidenceRef
    source_2: EvidenceRef
    severity: SafetySeverity
    resolution_attempted: bool = False
    resolution: Optional[str] = None  # If agent was able to determine likely resolution
    requires_clinician: bool = True
    detected_at_step: Optional[str] = None
```

---

### Safety Flag

```python
class SafetyFlag(BaseModel):
    id: str
    summary_id: Optional[str] = None
    run_id: str
    severity: SafetySeverity
    category: SafetyCategory
    title: str
    description: str
    source_doc_ids: List[str] = Field(default_factory=list)
    conflicting_text: Optional[dict] = None
    recommendation: Optional[str] = None
    resolved: bool = False
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

class EscalationRecord(BaseModel):
    run_id: str
    triggered_at: datetime
    reason: str
    severity: SafetySeverity
    flags: List[SafetyFlag]
    requires_action: str
```

---

### Discharge Summary

```python
class SummarySection(BaseModel):
    content: str
    confidence: Confidence
    needs_review: bool = False
    missing_info: Optional[str] = None
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    last_edited_by: Optional[str] = None
    last_edited_at: Optional[datetime] = None

class DischargeSummary(BaseModel):
    id: str
    patient_id: str
    agent_run_id: str
    status: SummaryStatus
    version: int = 1

    # All required discharge summary sections
    sections: "DischargeSummarySections"

    # Metadata
    conflicts_found: int = 0
    missing_fields: int = 0
    medications_reconciled: int = 0

    # Review metadata
    reviewed_by: Optional[str] = None
    review_started_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime

class DischargeSummarySections(BaseModel):
    patient_demographics: Optional[SummarySection] = None
    admission_date: Optional[SummarySection] = None
    discharge_date: Optional[SummarySection] = None
    principal_diagnosis: Optional[SummarySection] = None
    secondary_diagnoses: Optional[SummarySection] = None
    hospital_course: Optional[SummarySection] = None
    procedures: Optional[SummarySection] = None
    allergies: Optional[SummarySection] = None
    discharge_medications: Optional[SummarySection] = None
    medication_changes: Optional[SummarySection] = None
    follow_up_instructions: Optional[SummarySection] = None
    pending_results: Optional[SummarySection] = None
    discharge_condition: Optional[SummarySection] = None
    safety_flags_summary: Optional[SummarySection] = None
```

---

### Agent Run & Trace

```python
class AgentRunCreate(BaseModel):
    patient_id: str
    config: Optional[dict] = None

class AgentRunStatus(BaseModel):
    run_id: str
    patient_id: str
    status: AgentStatus
    current_step: Optional[dict] = None
    progress: dict  # steps_completed, steps_total, percent
    iteration_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    summary_id: Optional[str] = None
    error_message: Optional[str] = None

class AgentTrace(BaseModel):
    id: str
    run_id: str
    step_number: int
    step_id: str
    tool_name: str
    tool_input: Optional[dict] = None
    tool_output: Optional[dict] = None
    success: bool
    latency_ms: Optional[float] = None
    error_message: Optional[str] = None
    claude_tokens_in: Optional[int] = None
    claude_tokens_out: Optional[int] = None
    reasoning: Optional[str] = None
    timestamp: datetime

class FullAgentTrace(BaseModel):
    run_id: str
    patient_id: str
    status: AgentStatus
    plan: Optional[list] = None
    trace: List[AgentTrace] = Field(default_factory=list)
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_latency_ms: Optional[float] = None
```

---

### Learning Feedback

```python
class LearningFeedbackCreate(BaseModel):
    summary_id: str
    section_name: str
    rating: Optional[int] = Field(None, ge=1, le=5)
    issue_type: Optional[FeedbackIssueType] = None
    comment: Optional[str] = None
    original_content: Optional[str] = None
    corrected_content: Optional[str] = None
    submitted_by: str

class LearningFeedbackResponse(LearningFeedbackCreate):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True
```
