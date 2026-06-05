from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidencedFact(BaseModel):
    """A clinical fact with mandatory source provenance and confidence score."""

    fact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_document: str
    source_document_id: str
    page_number: int
    evidence: str = Field(description="Verbatim excerpt from source — max 500 chars")
    extracted_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def confidence_level(self) -> ConfidenceLevel:
        if self.confidence >= 0.85:
            return ConfidenceLevel.HIGH
        elif self.confidence >= 0.60:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    def short_evidence(self, max_len: int = 120) -> str:
        return self.evidence[:max_len] + "…" if len(self.evidence) > max_len else self.evidence


class PatientDemographics(BaseModel):
    name: Optional[EvidencedFact] = None
    age: Optional[EvidencedFact] = None
    date_of_birth: Optional[EvidencedFact] = None
    gender: Optional[EvidencedFact] = None
    mrn: Optional[EvidencedFact] = None


class HospitalInfo(BaseModel):
    facility: Optional[EvidencedFact] = None
    admission_date: Optional[EvidencedFact] = None
    discharge_date: Optional[EvidencedFact] = None
    attending_physician: Optional[EvidencedFact] = None
    ward: Optional[EvidencedFact] = None


class Diagnosis(BaseModel):
    diagnosis_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: EvidencedFact
    icd_code: Optional[str] = None
    is_principal: bool = False
    description: Optional[EvidencedFact] = None


class Medication(BaseModel):
    medication_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: EvidencedFact
    dose: Optional[EvidencedFact] = None
    route: Optional[EvidencedFact] = None
    frequency: Optional[EvidencedFact] = None
    indication: Optional[str] = None
    is_admission: bool = True
    is_changed_at_discharge: bool = False
    change_reason: Optional[str] = None
    is_discontinued: bool = False


class Allergy(BaseModel):
    allergy_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    allergen: EvidencedFact
    reaction: Optional[EvidencedFact] = None
    severity: Optional[str] = None  # mild | moderate | severe | life-threatening


class Procedure(BaseModel):
    procedure_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: EvidencedFact
    date: Optional[EvidencedFact] = None
    outcome: Optional[EvidencedFact] = None


class LabResult(BaseModel):
    lab_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    test_name: EvidencedFact
    value: EvidencedFact
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    collection_date: Optional[EvidencedFact] = None
    is_abnormal: bool = False
    is_critical: bool = False


class FollowUp(BaseModel):
    followup_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    instruction: EvidencedFact
    specialist: Optional[str] = None
    timeframe: Optional[str] = None
    contact: Optional[str] = None


class PendingResult(BaseModel):
    pending_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: EvidencedFact
    expected_by: Optional[str] = None
    action_if_abnormal: Optional[str] = None


class ClinicalConflict(BaseModel):
    conflict_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conflict_type: str  # medication_conflict | allergy_conflict | diagnosis_conflict | drug_interaction
    description: str
    severity: str  # warning | critical
    involved_items: List[str] = Field(default_factory=list)
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolution: Optional[str] = None


class PatientKnowledgeBase(BaseModel):
    """Complete structured clinical knowledge for one patient, ready for discharge summary generation."""

    knowledge_base_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    patient_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    demographics: PatientDemographics = Field(default_factory=PatientDemographics)
    hospital_info: HospitalInfo = Field(default_factory=HospitalInfo)

    diagnoses: List[Diagnosis] = Field(default_factory=list)
    medications_admission: List[Medication] = Field(default_factory=list)
    medications_discharge: List[Medication] = Field(default_factory=list)
    allergies: List[Allergy] = Field(default_factory=list)
    procedures: List[Procedure] = Field(default_factory=list)
    lab_results: List[LabResult] = Field(default_factory=list)
    follow_ups: List[FollowUp] = Field(default_factory=list)
    pending_results: List[PendingResult] = Field(default_factory=list)

    hospital_course: Optional[EvidencedFact] = None
    discharge_condition: Optional[EvidencedFact] = None

    conflicts: List[ClinicalConflict] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)

    source_document_ids: List[str] = Field(default_factory=list)
    extraction_metadata: Dict[str, Any] = Field(default_factory=dict)
