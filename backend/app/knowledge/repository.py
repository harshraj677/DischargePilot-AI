from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple

from app.knowledge.models import (
    Allergy,
    ClinicalConflict,
    Diagnosis,
    EvidencedFact,
    FollowUp,
    LabResult,
    Medication,
    PatientKnowledgeBase,
    PendingResult,
    Procedure,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _iter_all_facts(kb: PatientKnowledgeBase) -> Iterator[Tuple[str, EvidencedFact]]:
    """Iterate (category_path, fact) for every EvidencedFact in the knowledge base."""
    demo = kb.demographics
    for field in ("name", "age", "date_of_birth", "gender", "mrn"):
        fact = getattr(demo, field)
        if isinstance(fact, EvidencedFact):
            yield f"demographics.{field}", fact

    info = kb.hospital_info
    for field in ("facility", "admission_date", "discharge_date", "attending_physician", "ward"):
        fact = getattr(info, field)
        if isinstance(fact, EvidencedFact):
            yield f"hospital_info.{field}", fact

    for dx in kb.diagnoses:
        yield "diagnosis.name", dx.name
        if dx.description:
            yield "diagnosis.description", dx.description

    for med in kb.medications_admission + kb.medications_discharge:
        yield "medication.name", med.name
        for sub in ("dose", "route", "frequency"):
            f = getattr(med, sub)
            if isinstance(f, EvidencedFact):
                yield f"medication.{sub}", f

    for a in kb.allergies:
        yield "allergy.allergen", a.allergen
        if a.reaction:
            yield "allergy.reaction", a.reaction

    for proc in kb.procedures:
        yield "procedure.name", proc.name
        if proc.date:
            yield "procedure.date", proc.date

    for lab in kb.lab_results:
        yield "lab.test_name", lab.test_name
        yield "lab.value", lab.value

    for fu in kb.follow_ups:
        yield "followup.instruction", fu.instruction

    for pr in kb.pending_results:
        yield "pending_result.description", pr.description

    if kb.hospital_course:
        yield "hospital_course", kb.hospital_course
    if kb.discharge_condition:
        yield "discharge_condition", kb.discharge_condition


class KnowledgeRepository:
    """
    In-memory typed repository wrapping PatientKnowledgeBase.

    The agent loop reads and writes through this interface.
    Every mutation timestamps the knowledge base (updated_at).
    """

    def __init__(self, patient_id: str) -> None:
        self._kb = PatientKnowledgeBase(patient_id=patient_id)

    # ── Internal helpers ────────────────────────────────────────────────────────

    def _touch(self) -> None:
        self._kb.updated_at = datetime.utcnow()

    # ── Read access ─────────────────────────────────────────────────────────────

    @property
    def kb(self) -> PatientKnowledgeBase:
        return self._kb

    def get_all_facts(self) -> Dict[str, Any]:
        return self._kb.model_dump()

    def get_fact(self, category: str) -> Optional[Any]:
        """
        Fetch by dot-path, e.g. 'demographics.name', 'diagnoses', 'hospital_course'.
        Returns EvidencedFact, list, or None.
        """
        parts = category.split(".", 1)
        top = parts[0]
        sub = parts[1] if len(parts) > 1 else None

        mapping: Dict[str, Any] = {
            "demographics": self._kb.demographics,
            "hospital_info": self._kb.hospital_info,
            "diagnoses": self._kb.diagnoses,
            "medications_admission": self._kb.medications_admission,
            "medications_discharge": self._kb.medications_discharge,
            "allergies": self._kb.allergies,
            "procedures": self._kb.procedures,
            "lab_results": self._kb.lab_results,
            "follow_ups": self._kb.follow_ups,
            "pending_results": self._kb.pending_results,
            "hospital_course": self._kb.hospital_course,
            "discharge_condition": self._kb.discharge_condition,
            "conflicts": self._kb.conflicts,
        }

        obj = mapping.get(top)
        if obj is None:
            return None
        if sub is not None:
            return getattr(obj, sub, None)
        return obj

    def get_evidence(self, fact_id: str) -> Optional[str]:
        for _, fact in _iter_all_facts(self._kb):
            if fact.fact_id == fact_id:
                return fact.evidence
        return None

    def search_by_source(self, source_document: str) -> List[EvidencedFact]:
        return [f for _, f in _iter_all_facts(self._kb) if f.source_document == source_document]

    def search_by_page(self, page_number: int) -> List[EvidencedFact]:
        return [f for _, f in _iter_all_facts(self._kb) if f.page_number == page_number]

    # ── Write access ─────────────────────────────────────────────────────────────

    def add_fact(self, category: str, value: Any) -> None:
        """Route a typed value to the correct knowledge-base field."""
        self._touch()

        scalar_map: Dict[str, str] = {
            "demographics.name": "demographics.name",
            "demographics.age": "demographics.age",
            "demographics.date_of_birth": "demographics.date_of_birth",
            "demographics.gender": "demographics.gender",
            "demographics.mrn": "demographics.mrn",
            "hospital_info.admission_date": "hospital_info.admission_date",
            "hospital_info.discharge_date": "hospital_info.discharge_date",
            "hospital_info.attending_physician": "hospital_info.attending_physician",
            "hospital_info.facility": "hospital_info.facility",
            "hospital_info.ward": "hospital_info.ward",
        }

        list_map: Dict[str, str] = {
            "diagnosis": "diagnoses",
            "medication_admission": "medications_admission",
            "medication_discharge": "medications_discharge",
            "allergy": "allergies",
            "procedure": "procedures",
            "lab_result": "lab_results",
            "follow_up": "follow_ups",
            "pending_result": "pending_results",
            "conflict": "conflicts",
        }

        if category in scalar_map:
            parts = category.split(".")
            obj = getattr(self._kb, parts[0])
            setattr(obj, parts[1], value)
        elif category in list_map:
            getattr(self._kb, list_map[category]).append(value)
        elif category == "hospital_course":
            self._kb.hospital_course = value
        elif category == "discharge_condition":
            self._kb.discharge_condition = value
        elif category == "missing_information":
            if value not in self._kb.missing_information:
                self._kb.missing_information.append(value)
        else:
            logger.warning("Unknown knowledge category", category=category)

    def add_source_document(self, document_id: str) -> None:
        if document_id not in self._kb.source_document_ids:
            self._kb.source_document_ids.append(document_id)

    def mark_missing(self, info: str) -> None:
        self.add_fact("missing_information", info)

    def add_conflict(self, conflict: ClinicalConflict) -> None:
        self.add_fact("conflict", conflict)

    # ── Analysis helpers ─────────────────────────────────────────────────────────

    def completeness_score(self) -> float:
        """Return 0.0-1.0 representing how complete the knowledge base is."""
        checks = [
            self._kb.demographics.name is not None,
            self._kb.demographics.mrn is not None,
            self._kb.hospital_info.admission_date is not None,
            len(self._kb.diagnoses) > 0,
            len(self._kb.medications_discharge) > 0,
            len(self._kb.allergies) > 0,
            self._kb.hospital_course is not None,
            self._kb.discharge_condition is not None,
            len(self._kb.follow_ups) > 0,
        ]
        return sum(1 for c in checks if c) / len(checks)

    def get_missing_critical_fields(self) -> List[str]:
        missing = []
        if not self._kb.demographics.name:
            missing.append("patient_name")
        if not self._kb.demographics.mrn:
            missing.append("patient_mrn")
        if not self._kb.hospital_info.admission_date:
            missing.append("admission_date")
        if not self._kb.diagnoses:
            missing.append("diagnoses")
        if not self._kb.medications_discharge:
            missing.append("discharge_medications")
        if not self._kb.hospital_course:
            missing.append("hospital_course")
        if not self._kb.discharge_condition:
            missing.append("discharge_condition")
        if not self._kb.follow_ups:
            missing.append("follow_up_instructions")
        return missing

    def has_critical_conflicts(self) -> bool:
        return any(c.severity == "critical" and not c.resolved for c in self._kb.conflicts)

    def to_agent_context(self) -> str:
        """Compact text summary for agent prompt context."""
        kb = self._kb
        principal = next((d.name.value for d in kb.diagnoses if d.is_principal), "None")
        lines = [
            f"Patient: {kb.demographics.name.value if kb.demographics.name else 'Unknown'}",
            f"MRN: {kb.demographics.mrn.value if kb.demographics.mrn else 'Unknown'}",
            f"Admission: {kb.hospital_info.admission_date.value if kb.hospital_info.admission_date else 'Unknown'}",
            f"Principal Dx: {principal}",
            f"All Diagnoses ({len(kb.diagnoses)}): {', '.join(d.name.value for d in kb.diagnoses[:5])}",
            f"Admission Meds ({len(kb.medications_admission)})",
            f"Discharge Meds ({len(kb.medications_discharge)})",
            f"Allergies ({len(kb.allergies)}): {', '.join(a.allergen.value for a in kb.allergies[:5])}",
            f"Lab Results ({len(kb.lab_results)})",
            f"Procedures ({len(kb.procedures)})",
            f"Follow-Ups ({len(kb.follow_ups)})",
            f"Pending Results ({len(kb.pending_results)})",
            f"Conflicts ({len(kb.conflicts)}): {', '.join(c.conflict_type for c in kb.conflicts[:3])}",
            f"Hospital Course: {'Present' if kb.hospital_course else 'Missing'}",
            f"Discharge Condition: {'Present' if kb.discharge_condition else 'Missing'}",
            f"Completeness: {self.completeness_score():.0%}",
        ]
        return "\n".join(lines)
