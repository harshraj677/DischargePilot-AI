import uuid
import json
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models import Document
from app.models.document import (
    DocumentCreate, PageChunk, ClinicalMetadata, ProcessingLog
)
from app.models.enums import DocumentStatus
from app.utils.logging import get_logger

logger = get_logger(__name__)


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: DocumentCreate) -> Document:
        doc = Document(
            id=str(uuid.uuid4()),
            patient_id=data.patient_id,
            document_type=data.document_type.value,
            declared_type=data.declared_type.value if data.declared_type else None,
            file_name=data.file_name,
            file_path=data.file_path,
            file_size_bytes=data.file_size_bytes,
            status=DocumentStatus.UPLOADED.value,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        logger.info("Document record created", document_id=doc.id, filename=data.file_name)
        return doc

    def get_by_id(self, document_id: str) -> Optional[Document]:
        return self.db.get(Document, document_id)

    def list_for_patient(self, patient_id: str) -> List[Document]:
        stmt = select(Document).where(Document.patient_id == patient_id).order_by(Document.created_at)
        return list(self.db.execute(stmt).scalars())

    def set_status(self, document_id: str, status: DocumentStatus, error: Optional[str] = None) -> None:
        doc = self.db.get(Document, document_id)
        if doc:
            doc.status = status.value
            if error:
                doc.processing_error = error
            doc.updated_at = datetime.utcnow()
            self.db.commit()

    def set_processing(self, document_id: str) -> None:
        self.set_status(document_id, DocumentStatus.PROCESSING)

    def set_failed(self, document_id: str, error: str) -> None:
        doc = self.db.get(Document, document_id)
        if doc:
            doc.status = DocumentStatus.FAILED.value
            doc.processing_error = error
            doc.retry_count += 1
            doc.updated_at = datetime.utcnow()
            self.db.commit()

    def set_review_required(self, document_id: str, reason: str) -> None:
        doc = self.db.get(Document, document_id)
        if doc:
            doc.status = DocumentStatus.REVIEW_REQUIRED.value
            doc.processing_error = reason
            doc.updated_at = datetime.utcnow()
            self.db.commit()

    def save_extraction_results(
        self,
        document_id: str,
        page_chunks: List[PageChunk],
        page_count: int,
        full_text: str,
        metadata: Optional[ClinicalMetadata],
        doc_type: str,
        confidence: float,
        method: str,
        processing_logs: List[ProcessingLog],
        file_hash: Optional[str] = None,
    ) -> None:
        doc = self.db.get(Document, document_id)
        if not doc:
            return

        doc.status = DocumentStatus.PROCESSED.value
        doc.page_count = page_count
        doc.extracted_text = full_text
        doc.page_chunks = json.dumps([c.model_dump() for c in page_chunks], default=str)
        doc.document_type = doc_type
        doc.classification_confidence = confidence
        doc.classification_method = method
        doc.processing_logs = json.dumps([l.model_dump() for l in processing_logs], default=str)
        doc.file_hash = file_hash

        if metadata:
            doc.clinical_metadata = metadata.model_dump_json()

        doc.updated_at = datetime.utcnow()
        self.db.commit()
        logger.info(
            "Extraction results saved",
            document_id=document_id,
            pages=page_count,
            doc_type=doc_type,
            confidence=round(confidence, 3),
        )

    def get_page_chunks(self, document_id: str) -> List[PageChunk]:
        doc = self.db.get(Document, document_id)
        if not doc or not doc.page_chunks:
            return []
        raw = json.loads(doc.page_chunks)
        return [PageChunk(**c) for c in raw]

    def get_clinical_metadata(self, document_id: str) -> Optional[ClinicalMetadata]:
        doc = self.db.get(Document, document_id)
        if not doc or not doc.clinical_metadata:
            return None
        return ClinicalMetadata.model_validate_json(doc.clinical_metadata)

    def get_processing_logs(self, document_id: str) -> List[ProcessingLog]:
        doc = self.db.get(Document, document_id)
        if not doc or not doc.processing_logs:
            return []
        raw = json.loads(doc.processing_logs)
        return [ProcessingLog(**l) for l in raw]

    def count_by_status(self, patient_id: str) -> dict:
        docs = self.list_for_patient(patient_id)
        counts: dict = {s.value: 0 for s in DocumentStatus}
        for doc in docs:
            counts[doc.status] = counts.get(doc.status, 0) + 1
        return counts
