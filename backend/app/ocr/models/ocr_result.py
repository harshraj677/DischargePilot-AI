"""
OCR Result Models — Pydantic models for OCR processing results
"""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

from pydantic import BaseModel, Field


class PageType(str, Enum):
    """Classification of page content type"""
    TEXT_PAGE = "text_page"  # Native text PDF page
    SCANNED_PAGE = "scanned_page"  # Scanned document
    IMAGE_PAGE = "image_page"  # Image-only page
    HANDWRITTEN_PAGE = "handwritten_page"  # Handwritten content
    MIXED_PAGE = "mixed_page"  # Mix of text and images


class HandwritingDetection(BaseModel):
    """Handwriting detection result"""
    is_handwritten: bool
    confidence: float = Field(ge=0.0, le=1.0)
    handwriting_percentage: float = Field(ge=0.0, le=1.0, description="Percentage of page that is handwritten")
    requires_review: bool = Field(description="Whether manual review is required")


class PageClassification(BaseModel):
    """Page classification result"""
    page_number: int
    page_type: PageType
    confidence: float = Field(ge=0.0, le=1.0)
    extracted_text_length: int
    has_images: bool
    handwriting: Optional[HandwritingDetection] = None
    classification_details: Dict[str, Any] = Field(default_factory=dict)


class OCRMetadata(BaseModel):
    """Metadata about OCR processing"""
    provider: str  # e.g., "claude", "easyocr", "tesseract"
    model_name: Optional[str] = None
    processing_time_ms: float
    confidence: float = Field(ge=0.0, le=1.0)
    retry_count: int = 0
    fallback_used: bool = False
    error_message: Optional[str] = None


class OCRResult(BaseModel):
    """Complete OCR processing result with provenance"""
    
    ocr_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    page_number: int
    
    # Raw results
    extracted_text: str
    extracted_html: Optional[str] = None  # Structured format with formatting/tables
    
    # Classification and confidence
    page_classification: PageClassification
    
    # OCR processing metadata
    metadata: OCRMetadata
    
    # Evidence for audit trail
    confidence_score: float = Field(ge=0.0, le=1.0)
    requires_manual_review: bool = False
    review_reason: Optional[str] = None
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Safety flags
    contains_medication_names: bool = False
    contains_diagnosis_terms: bool = False
    contains_patient_identifiers: bool = False
    
    def is_high_confidence(self, threshold: float = 0.80) -> bool:
        """Check if OCR result meets high confidence threshold"""
        return self.confidence_score >= threshold
    
    def is_medium_confidence(self, low: float = 0.60, high: float = 0.80) -> bool:
        """Check if OCR result is medium confidence"""
        return low <= self.confidence_score < high
    
    def is_low_confidence(self, threshold: float = 0.60) -> bool:
        """Check if OCR result is below confidence threshold"""
        return self.confidence_score < threshold


class OCRResultWithFallback(BaseModel):
    """OCR result with fallback chain information"""
    
    primary_result: OCRResult
    fallback_results: list[OCRResult] = Field(default_factory=list)
    selected_result: OCRResult
    fallback_reason: Optional[str] = None
    selection_reason: str
