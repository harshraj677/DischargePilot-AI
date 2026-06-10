"""
Handwriting Processor

Detects and extracts handwritten content from documents.
Features:
- Confidence scoring for handwriting detection
- Flags uncertain content for manual review
- Never presents uncertain handwriting as confirmed fact
"""
from typing import Optional
import re

from app.ocr.models import OCRResult, HandwritingDetection
from app.utils.logging import get_logger

logger = get_logger(__name__)


class HandwritingProcessor:
    """
    Processes handwritten content with safety guardrails.
    """
    
    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    MEDIUM_CONFIDENCE_THRESHOLD = 0.60
    
    # Uncertainty markers from Claude Vision
    UNCERTAINTY_MARKERS = [
        "[uncertain",
        "[handwritten",
        "unclear",
        "illegible",
        "ambiguous",
    ]
    
    def __init__(self):
        self.logger = logger
    
    def process_ocr_result(
        self,
        ocr_result: OCRResult,
    ) -> tuple[str, float, bool]:
        """
        Process OCR result and extract handwriting information.
        
        Args:
            ocr_result: OCR result from provider
        
        Returns:
            Tuple of:
            - cleaned_text: Handwriting-flagged content removed or marked
            - confidence: Confidence score for handwritten content
            - requires_review: Whether manual review is required
        """
        
        # Check if handwriting was detected by classifier
        if (
            ocr_result.page_classification.handwriting
            and ocr_result.page_classification.handwriting.is_handwritten
        ):
            handwriting_info = ocr_result.page_classification.handwriting
            
            # Process text for uncertainty markers
            cleaned_text = self._sanitize_uncertain_content(
                ocr_result.extracted_text
            )
            
            return (
                cleaned_text,
                handwriting_info.confidence,
                handwriting_info.requires_review,
            )
        
        return (
            ocr_result.extracted_text,
            1.0,
            False,
        )
    
    def _sanitize_uncertain_content(self, text: str) -> str:
        """
        Remove or flag uncertain content in text.
        
        Markers like [UNCERTAIN: ...], [HANDWRITTEN], etc.
        are preserved with clear flagging.
        """
        # Preserve markers but wrap them for safety
        processed_lines = []
        
        for line in text.split("\n"):
            line_lower = line.lower()
            
            # Check for uncertainty markers
            has_uncertainty = any(
                marker in line_lower for marker in self.UNCERTAINTY_MARKERS
            )
            
            if has_uncertainty:
                # Wrap in safety marker
                processed_lines.append(f"[REQUIRES_MANUAL_REVIEW] {line}")
            else:
                processed_lines.append(line)
        
        return "\n".join(processed_lines)
    
    def create_handwriting_evidence(
        self,
        ocr_result: OCRResult,
        handwriting_confidence: float,
        requires_review: bool,
    ) -> dict:
        """
        Create evidence structure for handwritten content.
        
        Returns:
            Dict with evidence metadata for knowledge repository
        """
        return {
            "extraction_method": "ocr_handwriting",
            "ocr_provider": ocr_result.metadata.provider,
            "confidence": handwriting_confidence,
            "page_number": ocr_result.page_number,
            "document_id": ocr_result.document_id,
            "requires_review": requires_review,
            "review_reason": "Handwritten content may contain extraction errors",
            "uncertainty_markers_present": (
                "[REQUIRES_MANUAL_REVIEW]" in ocr_result.extracted_text
            ),
        }
    
    def score_handwriting_confidence(
        self,
        text: str,
        provider: str,
        has_uncertainty_markers: bool,
    ) -> float:
        """
        Calculate confidence score for handwritten OCR.
        
        Factors:
        - Provider capability
        - Uncertainty markers in text
        - Text complexity
        
        Returns:
            Confidence score (0.0-1.0)
        """
        base_confidence = 0.60  # Conservative base for handwriting
        
        # Adjust by provider
        provider_adjustments = {
            "claude": 0.15,      # +15% - best handwriting support
            "easyocr": 0.05,     # +5% - limited support
            "tesseract": 0.00,   # No adjustment - minimal support
        }
        
        base_confidence += provider_adjustments.get(provider, 0.0)
        
        # Penalize for uncertainty markers
        if has_uncertainty_markers:
            uncertainty_count = text.count("[REQUIRES_MANUAL_REVIEW]")
            uncertainty_ratio = min(uncertainty_count / max(1, len(text.split("\n"))), 1.0)
            base_confidence *= (1.0 - uncertainty_ratio * 0.3)
        
        # Ensure within bounds
        return max(0.0, min(base_confidence, 1.0))
    
    def requires_clinical_review(
        self,
        text: str,
        confidence: float,
        page_type: str,
    ) -> bool:
        """
        Determine if handwritten content requires clinical review.
        
        Returns True if:
        - Confidence below threshold
        - Contains uncertainty markers
        - Contains medication/diagnosis keywords
        
        Args:
            text: Extracted text
            confidence: Confidence score
            page_type: Page classification
        
        Returns:
            Whether clinical review is required
        """
        # Low confidence always requires review
        if confidence < self.MEDIUM_CONFIDENCE_THRESHOLD:
            return True
        
        # Uncertainty markers require review
        if "[REQUIRES_MANUAL_REVIEW]" in text:
            return True
        
        # Clinical keywords in uncertain text require review
        clinical_keywords = [
            "medication", "diagnosis", "allergy", "contraindication",
            "dosage", "frequency", "route", "procedure",
        ]
        
        text_lower = text.lower()
        has_clinical_keywords = any(
            keyword in text_lower for keyword in clinical_keywords
        )
        
        if has_clinical_keywords and confidence < self.HIGH_CONFIDENCE_THRESHOLD:
            return True
        
        return False
    
    def create_review_note(
        self,
        text: str,
        confidence: float,
        contains_medication: bool,
        contains_diagnosis: bool,
    ) -> str:
        """
        Create a structured review note for clinical staff.
        
        Args:
            text: Extracted text
            confidence: Confidence score
            contains_medication: Whether medication info was detected
            contains_diagnosis: Whether diagnosis info was detected
        
        Returns:
            Formatted review note
        """
        confidence_level = (
            "HIGH" if confidence >= 0.85
            else "MEDIUM" if confidence >= 0.60
            else "LOW"
        )
        
        note_parts = [
            f"HANDWRITING EXTRACTION REVIEW",
            f"Confidence Level: {confidence_level} ({confidence:.1%})",
            "",
        ]
        
        if contains_medication:
            note_parts.append("⚠️  CONTAINS MEDICATION INFORMATION")
            note_parts.append("   → Verify medication names, dosages, and frequencies")
            note_parts.append("")
        
        if contains_diagnosis:
            note_parts.append("⚠️  CONTAINS DIAGNOSIS INFORMATION")
            note_parts.append("   → Verify diagnosis codes and descriptions")
            note_parts.append("")
        
        if "[REQUIRES_MANUAL_REVIEW]" in text:
            note_parts.append("⚠️  UNCERTAIN SECTIONS MARKED")
            note_parts.append("   → Review marked sections for accuracy")
            note_parts.append("")
        
        note_parts.append("EXTRACTED TEXT:")
        note_parts.append("-" * 40)
        note_parts.append(text)
        
        return "\n".join(note_parts)
