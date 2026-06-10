"""
OCR Provider Abstraction Layer

Defines interface for different OCR backends:
- Claude Vision (Anthropic)
- EasyOCR
- Tesseract
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import time

from app.ocr.models import OCRResult, PageClassification
from app.utils.logging import get_logger

logger = get_logger(__name__)


class OCRProvider(ABC):
    """Abstract base class for OCR providers."""
    
    @abstractmethod
    def process_image(
        self,
        image_bytes: bytes,
        page_number: int,
        document_id: str,
        page_classification: PageClassification,
    ) -> Optional[OCRResult]:
        """
        Process an image and extract text.
        
        Args:
            image_bytes: Image data (PNG, JPEG, etc.)
            page_number: 1-based page number
            document_id: Document identifier
            page_classification: Classification of the page
        
        Returns:
            OCRResult with extracted text and metadata, or None on failure
        """
        pass
    
    @abstractmethod
    def supports_handwriting(self) -> bool:
        """Whether this provider can detect and extract handwriting."""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get human-readable provider name."""
        pass
    
    def _log_processing(
        self,
        page_number: int,
        document_id: str,
        duration_ms: float,
        text_length: int,
        confidence: float,
    ) -> None:
        """Log OCR processing metrics."""
        logger.info(
            "OCR processing completed",
            provider=self.get_provider_name(),
            page=page_number,
            document_id=document_id,
            duration_ms=round(duration_ms, 2),
            text_length=text_length,
            confidence=round(confidence, 3),
        )
