"""
Patient Service — business logic for patient lifecycle management.
"""
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session

from app.db.repositories.patient_repo import PatientRepository
from app.db.repositories.document_repo import DocumentRepository
from app.db.models import Patient
from app.models.patient import PatientCreate, PatientUpdate, PatientListItem, PatientResponse
from app.models.enums import DocumentStatus
from app.utils.exceptions import PatientNotFoundException, MRNAlreadyExistsException
from app.utils.logging import get_logger, AuditLogger

logger = get_logger(__name__)
audit = AuditLogger(__name__)


def create_patient(data: PatientCreate, db: Session) -> Patient:
    repo = PatientRepository(db)
    if repo.mrn_exists(data.mrn):
        raise MRNAlreadyExistsException(data.mrn)
    patient = repo.create(data)
    audit.log_patient_created(patient.id, patient.mrn)
    return patient


def get_patient_or_404(patient_id: str, db: Session) -> Patient:
    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_id)
    if not patient:
        raise PatientNotFoundException(patient_id)
    return patient


def list_patients(
    page: int,
    page_size: int,
    search: Optional[str],
    ward: Optional[str],
    db: Session,
) -> Tuple[List[Patient], int]:
    repo = PatientRepository(db)
    return repo.list(page=page, page_size=page_size, search=search, ward=ward)


def update_patient(patient_id: str, data: PatientUpdate, db: Session) -> Patient:
    repo = PatientRepository(db)
    patient = repo.update(patient_id, data)
    if not patient:
        raise PatientNotFoundException(patient_id)
    return patient


def get_processing_status(patient_id: str, db: Session) -> dict:
    patient_repo = PatientRepository(db)
    doc_repo = DocumentRepository(db)

    patient = patient_repo.get_by_id(patient_id)
    if not patient:
        raise PatientNotFoundException(patient_id)

    documents = doc_repo.list_for_patient(patient_id)
    counts = doc_repo.count_by_status(patient_id)

    all_ready = (
        len(documents) > 0
        and counts.get(DocumentStatus.UPLOADED.value, 0) == 0
        and counts.get(DocumentStatus.PROCESSING.value, 0) == 0
        and counts.get(DocumentStatus.FAILED.value, 0) == 0
    )

    return {
        "patient_id": patient_id,
        "total_documents": len(documents),
        "processed": counts.get(DocumentStatus.PROCESSED.value, 0),
        "processing": counts.get(DocumentStatus.PROCESSING.value, 0),
        "failed": counts.get(DocumentStatus.FAILED.value, 0),
        "uploaded": counts.get(DocumentStatus.UPLOADED.value, 0),
        "all_ready": all_ready,
        "documents": documents,
    }
