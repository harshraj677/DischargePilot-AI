"""
Tesseract OCR Provider

OCR provider using the Tesseract-OCR engine via pytesseract.
Most reliable for text-heavy documents and printed materials.
"""
import io
import time
from typing import Optional

try:
    import pytesseract
    from pytesseract import Output
except ImportError:
    pytesseract = None

from PIL import Image

from app.ocr.models import (
    OCRResult,
    PageClassification,
    OCRMetadata,
)
from app.ocr.providers.base import OCRProvider
from app.utils.logging import get_logger

logger = get_logger(__name__)


class TesseractOCRProvider(OCRProvider):
    """OCR provider using Tesseract."""
    
    def __init__(self, lang: str = "eng"):
        """
        Initialize Tesseract OCR provider.
        
        Args:
            lang: Tesseract language code (default: English)
        """
        if pytesseract is None:
            logger.warning("pytesseract not installed - install with: pip install pytesseract")
        
        self.lang = lang
        self.available = pytesseract is not None
        
        if self.available:
            try:
                # Test Tesseract availability
                pytesseract.get_tesseract_version()
                logger.info("Tesseract OCR initialized", language=lang)
            except Exception as e:
                logger.error(
                    "Tesseract OCR not available",
                    error=str(e),
                )
                self.available = False
    
    def process_image(
        self,
        image_bytes: bytes,
        page_number: int,
        document_id: str,
        page_classification: PageClassification,
    ) -> Optional[OCRResult]:
        """
        Process an image using Tesseract.
        
        Args:
            image_bytes: PNG or JPEG image data
            page_number: 1-based page number
            document_id: Document ID for tracking
            page_classification: Classification from page classifier
        
        Returns:
            OCRResult with extracted text and confidence
        """
        start_time = time.perf_counter()
        
        if not self.available:
            return self._error_result(
                page_number=page_number,
                document_id=document_id,
                page_classification=page_classification,
                error="Tesseract not available",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )
        
        try:
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_bytes))
            
            logger.info(
                "Processing image with Tesseract",
                page=page_number,
                document_id=document_id,
                image_size=image.size,
            )
            
            # Run OCR with confidence data
            data = pytesseract.image_to_data(
                image,
                lang=self.lang,
                output_type=Output.DICT,
            )
            
            # Extract text and calculate confidence
            extracted_text = pytesseract.image_to_string(image, lang=self.lang)
            avg_confidence = self._calculate_confidence(data)
            
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            self._log_processing(
                page_number=page_number,
                document_id=document_id,
                duration_ms=duration_ms,
                text_length=len(extracted_text),
                confidence=avg_confidence,
            )
            
            return OCRResult(
                document_id=document_id,
                page_number=page_number,
                extracted_text=extracted_text,
                page_classification=page_classification,
                metadata=OCRMetadata(
                    provider="tesseract",
                    model_name="tesseract",
                    processing_time_ms=duration_ms,
                    confidence=avg_confidence,
                ),
                confidence_score=avg_confidence,
                requires_manual_review=avg_confidence < 0.70,
                review_reason=(
                    "Low confidence OCR result"
                    if avg_confidence < 0.70
                    else None
                ),
                contains_medication_names=self._contains_medication_keywords(
                    extracted_text
                ),
                contains_diagnosis_terms=self._contains_diagnosis_keywords(
                    extracted_text
                ),
            )
        
        except Exception as e:
            logger.error(
                "Tesseract OCR processing failed",
                page=page_number,
                document_id=document_id,
                error=str(e),
            )
            return self._error_result(
                page_number=page_number,
                document_id=document_id,
                page_classification=page_classification,
                error=str(e),
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )
    
    def _calculate_confidence(self, data: dict) -> float:
        """
        Calculate average confidence from Tesseract output.
        
        Args:
            data: Output from pytesseract.image_to_data() with Output.DICT
        
        Returns:
            Average confidence (0.0-1.0)
        """
        try:
            confidences = [int(conf) / 100.0 for conf in data["conf"]]
            valid_confidences = [c for c in confidences if c > 0]
            
            if valid_confidences:
                return sum(valid_confidences) / len(valid_confidences)
            else:
                return 0.5
        
        except Exception as e:
            logger.warning("Failed to calculate confidence", error=str(e))
            return 0.5
    
    def _contains_medication_keywords(self, text: str) -> bool:
        """Check if text contains medication-related keywords."""
        medication_keywords = [
            "mg", "dose", "tablet", "capsule", "injection", "administered",
            "medication", "drug", "prescription", "pharmacy",
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in medication_keywords)
    
    def _contains_diagnosis_keywords(self, text: str) -> bool:
        """Check if text contains diagnosis-related keywords."""
        diagnosis_keywords = [
            "diagnosis", "icd", "syndrome", "disease", "condition", "disorder",
            "infection", "acute", "chronic",
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in diagnosis_keywords)
    
    def _error_result(
        self,
        page_number: int,
        document_id: str,
        page_classification: PageClassification,
        error: str,
        duration_ms: float,
    ) -> OCRResult:
        """Create error result."""
        return OCRResult(
            document_id=document_id,
            page_number=page_number,
            extracted_text="",
            page_classification=page_classification,
            metadata=OCRMetadata(
                provider="tesseract",
                processing_time_ms=duration_ms,
                confidence=0.0,
                error_message=error,
            ),
            confidence_score=0.0,
            requires_manual_review=True,
            review_reason=f"OCR failed: {error}",
        )
    
    def supports_handwriting(self) -> bool:
        """Tesseract has limited handwriting support."""
        return False  # Conservative - requires review for handwritten
    
    def get_provider_name(self) -> str:
        return "Tesseract OCR"
