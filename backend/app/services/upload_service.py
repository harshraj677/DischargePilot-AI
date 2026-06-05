"""
Upload Service — Module 1 (Document Upload Manager)
Handles file validation, storage, session creation, and upload audit logging.
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.db.repositories.document_repo import DocumentRepository
from app.db.repositories.patient_repo import PatientRepository
from app.db.models import Document
from app.models.document import DocumentCreate, DocumentResponse
from app.models.enums import DocumentType
from app.utils.exceptions import (
    PatientNotFoundException,
    InvalidFileTypeException,
    FileTooLargeException,
)
from app.utils.file_utils import validate_pdf_upload, save_upload_file
from app.utils.logging import get_logger, AuditLogger

logger = get_logger(__name__)
audit = AuditLogger(__name__)


async def handle_upload(
    patient_id: str,
    filename: str,
    file_bytes: bytes,
    declared_type: Optional[DocumentType],
    db: Session,
) -> Document:
    """
    Validates file, stores it on disk, creates the DB record, and returns the document.
    Does NOT start processing — caller triggers the background task.
    """
    # Ensure patient exists
    patient_repo = PatientRepository(db)
    patient = patient_repo.get_by_id(patient_id)
    if not patient:
        raise PatientNotFoundException(patient_id)

    file_size = len(file_bytes)
    validate_pdf_upload(filename, file_size)

    # Store file
    file_path, actual_size = await save_upload_file(file_bytes, patient_id, filename)

    # Create DB record
    doc_repo = DocumentRepository(db)
    doc = doc_repo.create(
        DocumentCreate(
            patient_id=patient_id,
            document_type=declared_type or DocumentType.UNKNOWN,
            file_name=filename,
            file_path=file_path,
            file_size_bytes=actual_size,
            declared_type=declared_type,
        )
    )

    audit.log_upload(patient_id, filename, (declared_type or DocumentType.UNKNOWN).value, actual_size)
    logger.info(
        "File uploaded and record created",
        document_id=doc.id,
        patient_id=patient_id,
        filename=filename,
        size_bytes=actual_size,
    )

    return doc
