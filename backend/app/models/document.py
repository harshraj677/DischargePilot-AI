from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.models.enums import DocumentType, DocumentStatus, ClassificationMethod


class PageChunk(BaseModel):
    page_number: int
    text: str
    char_count: int
    word_count: int
    is_empty: bool = False
    document_id: str = ""
    document_name: str = ""
    document_type: DocumentType = DocumentType.UNKNOWN
    ocr_metadata: Optional[Dict[str, Any]] = None


class EvidenceRef(BaseModel):
    document_id: str
    document_name: str
    document_type: DocumentType
    page_number: int
    excerpt: str = Field(..., description="Exact text excerpt — max 500 chars")
    char_start: Optional[int] = None
    char_end: Optional[int] = None

    def short_excerpt(self, max_len: int = 120) -> str:
        if len(self.excerpt) <= max_len:
            return self.excerpt
        return self.excerpt[:max_len].rsplit(" ", 1)[0] + "…"


class ClassificationResult(BaseModel):
    document_type: DocumentType
    confidence: float = Field(..., ge=0.0, le=1.0)
    method: ClassificationMethod
    scores: Dict[str, float] = {}
    reasoning: Optional[str] = None


class ClinicalMetadata(BaseModel):
    patient_name: Optional[str] = None
    patient_name_evidence: Optional[EvidenceRef] = None

    mrn: Optional[str] = None
    mrn_evidence: Optional[EvidenceRef] = None

    date_of_birth: Optional[str] = None
    dob_evidence: Optional[EvidenceRef] = None

    admission_date: Optional[str] = None
    admission_date_evidence: Optional[EvidenceRef] = None

    discharge_date: Optional[str] = None
    discharge_date_evidence: Optional[EvidenceRef] = None

    provider_name: Optional[str] = None
    provider_evidence: Optional[EvidenceRef] = None

    document_date: Optional[str] = None
    document_date_evidence: Optional[EvidenceRef] = None

    facility_name: Optional[str] = None

    raw_extractions: Dict[str, Any] = {}


class ProcessingLog(BaseModel):
    event: str
    timestamp: datetime
    message: str
    details: Dict[str, Any] = {}
    is_error: bool = False


class DocumentCreate(BaseModel):
    patient_id: str
    document_type: DocumentType
    file_name: str
    file_path: str
    file_size_bytes: Optional[int] = None
    declared_type: Optional[DocumentType] = None


class DocumentResponse(BaseModel):
    id: str
    patient_id: str
    document_type: DocumentType
    file_name: str
    file_size_bytes: Optional[int] = None
    page_count: Optional[int] = None
    status: DocumentStatus
    classification_confidence: Optional[float] = None
    classification_method: Optional[ClassificationMethod] = None
    processing_error: Optional[str] = None
    metadata: Optional[ClinicalMetadata] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentDetailResponse(DocumentResponse):
    page_chunks: List[PageChunk] = []
    processing_logs: List[ProcessingLog] = []


class ProcessingStatus(BaseModel):
    patient_id: str
    total_documents: int
    processed: int
    processing: int
    failed: int
    uploaded: int
    all_ready: bool
    documents: List[DocumentResponse]


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int


class KnowledgeChunk(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    document_type: DocumentType
    patient_id: str
    page_number: int
    text: str
    char_count: int
    word_count: int
    evidence_ref: EvidenceRef
