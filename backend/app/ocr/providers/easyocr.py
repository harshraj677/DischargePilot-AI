"""
EasyOCR Provider

Lightweight OCR provider using the EasyOCR library.
Good for quick processing and resource-constrained environments.
"""
import io
import time
from typing import Optional

import easyocr
from PIL import Image

from app.ocr.models import (
    OCRResult,
    PageClassification,
    OCRMetadata,
)
from app.ocr.providers.base import OCRProvider
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EasyOCRProvider(OCRProvider):
    """OCR provider using EasyOCR."""
    
    def __init__(self, languages: list[str] = None, gpu: bool = False):
        """
        Initialize EasyOCR provider.
        
        Args:
            languages: Languages to recognize (default: English)
            gpu: Whether to use GPU (if available)
        """
        self.languages = languages or ["en"]
        self.gpu = gpu
        
        try:
            self.reader = easyocr.Reader(self.languages, gpu=gpu)
            logger.info(
                "EasyOCR reader initialized",
                languages=self.languages,
                gpu=gpu,
            )
        except Exception as e:
            logger.error("Failed to initialize EasyOCR reader", error=str(e))
            self.reader = None
    
    def process_image(
        self,
        image_bytes: bytes,
        page_number: int,
        document_id: str,
        page_classification: PageClassification,
    ) -> Optional[OCRResult]:
        """
        Process an image using EasyOCR.
        
        Args:
            image_bytes: PNG or JPEG image data
            page_number: 1-based page number
            document_id: Document ID for tracking
            page_classification: Classification from page classifier
        
        Returns:
            OCRResult with extracted text and confidence
        """
        start_time = time.perf_counter()
        
        if self.reader is None:
            logger.error("EasyOCR reader not initialized")
            return self._error_result(
                page_number=page_number,
                document_id=document_id,
                page_classification=page_classification,
                error="EasyOCR reader not initialized",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )
        
        try:
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_bytes))
            image_array = self._pil_to_array(image)
            
            logger.info(
                "Processing image with EasyOCR",
                page=page_number,
                document_id=document_id,
                image_shape=image_array.shape,
            )
            
            # Run OCR
            results = self.reader.readtext(image_array)
            
            # Extract text and calculate confidence
            extracted_text, avg_confidence = self._extract_from_results(results)
            
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
                    provider="easyocr",
                    model_name="easyocr",
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
                "EasyOCR processing failed",
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
    
    def _pil_to_array(self, image: Image.Image):
        """Convert PIL Image to numpy array for EasyOCR."""
        import numpy as np
        
        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        return np.array(image)
    
    def _extract_from_results(self, results: list) -> tuple[str, float]:
        """
        Extract text and calculate average confidence from EasyOCR results.
        
        Returns:
            Tuple of (extracted_text, avg_confidence)
        """
        if not results:
            return "", 0.0
        
        texts = []
        confidences = []
        
        for result in results:
            # Each result is (bbox, text, confidence)
            text = result[1]
            confidence = result[2]
            
            texts.append(text)
            confidences.append(confidence)
        
        extracted_text = "\n".join(texts)
        avg_confidence = (
            sum(confidences) / len(confidences) if confidences else 0.0
        )
        
        return extracted_text, avg_confidence
    
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
                provider="easyocr",
                processing_time_ms=duration_ms,
                confidence=0.0,
                error_message=error,
            ),
            confidence_score=0.0,
            requires_manual_review=True,
            review_reason=f"OCR failed: {error}",
        )
    
    def supports_handwriting(self) -> bool:
        """EasyOCR can attempt to detect handwriting but with limited accuracy."""
        return False  # Conservative - requires review for handwritten
    
    def get_provider_name(self) -> str:
        return "EasyOCR"
