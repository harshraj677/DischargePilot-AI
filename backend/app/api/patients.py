from fastapi import APIRouter, Depends, BackgroundTasks, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional

from app.dependencies import get_db
from app.models.patient import (
    PatientCreate, PatientUpdate, PatientResponse, PatientListResponse, PatientListItem
)
from app.models.document import DocumentResponse, ProcessingStatus
from app.models.enums import DocumentType
from app.services.patient_service import (
    create_patient, get_patient_or_404, list_patients, update_patient, get_processing_status
)
from app.services.upload_service import handle_upload
from app.services.document_service import process_document
from app.db.repositories.document_repo import DocumentRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/patients", tags=["Patients"])


@router.post("", response_model=PatientResponse, status_code=201)
async def create_patient_endpoint(data: PatientCreate, db: Session = Depends(get_db)):
    patient = create_patient(data, db)
    doc_repo = DocumentRepository(db)
    docs = doc_repo.list_for_patient(patient.id)
    return _build_patient_response(patient, docs)


@router.get("", response_model=PatientListResponse)
async def list_patients_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=100),
    ward: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    patients, total = list_patients(page, page_size, search, ward, db)
    doc_repo = DocumentRepository(db)
    items = []
    for p in patients:
        count = doc_repo.count_by_status(p.id)
        total_docs = sum(count.values())
        items.append(
            PatientListItem(
                id=p.id,
                mrn=p.mrn,
                first_name=p.first_name,
                last_name=p.last_name,
                ward=p.ward,
                admission_date=p.admission_date,
                document_count=total_docs,
                created_at=p.created_at,
            )
        )
    return PatientListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient_endpoint(patient_id: str, db: Session = Depends(get_db)):
    patient = get_patient_or_404(patient_id, db)
    doc_repo = DocumentRepository(db)
    docs = doc_repo.list_for_patient(patient.id)
    return _build_patient_response(patient, docs)


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient_endpoint(
    patient_id: str, data: PatientUpdate, db: Session = Depends(get_db)
):
    patient = update_patient(patient_id, data, db)
    doc_repo = DocumentRepository(db)
    docs = doc_repo.list_for_patient(patient.id)
    return _build_patient_response(patient, docs)


@router.post("/{patient_id}/documents", response_model=DocumentResponse, status_code=202)
async def upload_document(
    patient_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    declared_type: Optional[DocumentType] = None
    if document_type:
        try:
            declared_type = DocumentType(document_type)
        except ValueError:
            pass

    file_bytes = await file.read()
    doc = await handle_upload(
        patient_id=patient_id,
        filename=file.filename or "upload.pdf",
        file_bytes=file_bytes,
        declared_type=declared_type,
        db=db,
    )

    # Kick off async processing
    background_tasks.add_task(process_document, doc.id, db)

    return _build_doc_response(doc)


@router.get("/{patient_id}/documents")
async def list_documents(patient_id: str, db: Session = Depends(get_db)):
    get_patient_or_404(patient_id, db)
    doc_repo = DocumentRepository(db)
    docs = doc_repo.list_for_patient(patient_id)
    return {
        "items": [_build_doc_response(d) for d in docs],
        "total": len(docs),
    }


@router.get("/{patient_id}/processing-status", response_model=ProcessingStatus)
async def processing_status(patient_id: str, db: Session = Depends(get_db)):
    status = get_processing_status(patient_id, db)
    status["documents"] = [_build_doc_response(d) for d in status["documents"]]
    return status


def _build_patient_response(patient, docs) -> PatientResponse:
    from app.models.patient import PatientDocumentSummary
    from app.models.enums import DocumentType
    doc_summaries = [
        PatientDocumentSummary(
            id=d.id,
            document_type=d.document_type,
            file_name=d.file_name,
            status=d.status,
            page_count=d.page_count,
            created_at=d.created_at,
        )
        for d in docs
    ]
    return PatientResponse(
        id=patient.id,
        mrn=patient.mrn,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        admission_date=patient.admission_date,
        discharge_date=patient.discharge_date,
        attending_md=patient.attending_md,
        ward=patient.ward,
        document_count=len(docs),
        documents=doc_summaries,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
    )


def _build_doc_response(doc) -> DocumentResponse:
    from app.models.enums import DocumentStatus, ClassificationMethod
    return DocumentResponse(
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
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
