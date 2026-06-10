import json
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.db.repositories.document_repo import DocumentRepository
from app.models.document import DocumentDetailResponse, DocumentResponse, PageChunk, ProcessingLog
from app.models.enums import DocumentType, DocumentStatus, ClassificationMethod
from app.services.document_service import process_document
from app.utils.exceptions import DocumentNotFoundException
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(document_id: str, db: Session = Depends(get_db)):
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(document_id)
    if not doc:
        raise DocumentNotFoundException(document_id)

    page_chunks = doc_repo.get_page_chunks(document_id)
    processing_logs = doc_repo.get_processing_logs(document_id)
    metadata = doc_repo.get_clinical_metadata(document_id)

    return DocumentDetailResponse(
        id=doc.id,
        patient_id=doc.patient_id,
        document_type=DocumentType(doc.document_type),
        file_name=doc.file_name,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        status=DocumentStatus(doc.status),
        classification_confidence=doc.classification_confidence,
        classification_method=ClassificationMethod(doc.classification_method) if doc.classification_method else None,
        processing_error=doc.processing_error,
        metadata=metadata,
        page_chunks=page_chunks,
        processing_logs=processing_logs,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: str, db: Session = Depends(get_db)):
    from app.utils.file_utils import delete_file
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(document_id)
    if not doc:
        raise DocumentNotFoundException(document_id)

    if doc.status in (DocumentStatus.PROCESSING.value,):
        from app.utils.exceptions import DischargePilotException
        raise DischargePilotException(
            error="Cannot delete",
            detail="Document is currently being processed. Wait for completion.",
            code="DOCUMENT_PROCESSING",
            status_code=409,
        )

    delete_file(doc.file_path)
    db.delete(doc)
    db.commit()
    logger.info("Document deleted", document_id=document_id)


@router.post("/{document_id}/retry", response_model=DocumentResponse, status_code=202)
async def retry_processing(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(document_id)
    if not doc:
        raise DocumentNotFoundException(document_id)

    if doc.status not in (
        DocumentStatus.FAILED.value,
        DocumentStatus.EMPTY.value,
        DocumentStatus.REVIEW_REQUIRED.value,
    ):
        from app.utils.exceptions import DischargePilotException
        raise DischargePilotException(
            error="Retry not applicable",
            detail=f"Document status is '{doc.status}'. Only FAILED, EMPTY, or REVIEW_REQUIRED documents can be retried.",
            code="RETRY_NOT_APPLICABLE",
            status_code=409,
        )

    doc_repo.set_status(document_id, DocumentStatus.UPLOADED)
    background_tasks.add_task(process_document, document_id, db)

    return DocumentResponse(
        id=doc.id,
        patient_id=doc.patient_id,
        document_type=DocumentType(doc.document_type),
        file_name=doc.file_name,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        status=DocumentStatus.UPLOADED,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get("/{document_id}/pages")
async def get_document_pages(document_id: str, db: Session = Depends(get_db)):
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(document_id)
    if not doc:
        raise DocumentNotFoundException(document_id)

    chunks = doc_repo.get_page_chunks(document_id)
    return {
        "document_id": document_id,
        "document_name": doc.file_name,
        "page_count": len(chunks),
        "pages": [
            {
                "page_number": c.page_number,
                "char_count": c.char_count,
                "word_count": c.word_count,
                "is_empty": c.is_empty,
                "text_preview": c.text[:300] if c.text else "",
            }
            for c in chunks
        ],
    }


@router.get("/{document_id}/logs")
async def get_processing_logs(document_id: str, db: Session = Depends(get_db)):
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(document_id)
    if not doc:
        raise DocumentNotFoundException(document_id)

    logs = doc_repo.get_processing_logs(document_id)
    return {
        "document_id": document_id,
        "filename": doc.file_name,
        "status": doc.status,
        "retry_count": doc.retry_count,
        "logs": [l.model_dump() for l in logs],
    }
