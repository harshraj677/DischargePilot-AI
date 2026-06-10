"""
Page Classification Engine

Analyzes PDF pages and classifies them as:
- TEXT_PAGE: Native text PDF
- SCANNED_PAGE: Scanned document (text in image form)
- IMAGE_PAGE: Image-only content
- HANDWRITTEN_PAGE: Primarily handwritten
- MIXED_PAGE: Mix of text and images

Uses heuristics and optional handwriting detection.
"""
from typing import Optional, Dict, Any
import fitz  # PyMuPDF
import io

from app.ocr.models import PageType, PageClassification, HandwritingDetection
from app.utils.logging import get_logger

logger = get_logger(__name__)


class PageClassifier:
    """
    Classifies PDF pages by content type and characteristics.
    """
    
    # Configuration thresholds
    NATIVE_TEXT_THRESHOLD = 100  # Min chars to consider as native text
    SCANNED_TEXT_THRESHOLD = 50   # Min chars from OCR to consider as scanned
    HANDWRITTEN_THRESHOLD = 0.6   # Confidence threshold for handwriting detection
    IMAGE_TO_TEXT_RATIO = 0.7     # If >70% images, likely image page
    
    def __init__(self):
        self.logger = logger
    
    def classify_page(
        self,
        page: fitz.Page,
        page_number: int,
        native_text: str,
        enable_handwriting_detection: bool = True,
    ) -> PageClassification:
        """
        Classify a single PDF page.
        
        Args:
            page: PyMuPDF page object
            page_number: 1-based page number
            native_text: Text extracted using PyMuPDF get_text()
            enable_handwriting_detection: Whether to detect handwriting
        
        Returns:
            PageClassification with page type and confidence
        """
        
        # Extract page images
        image_blocks = self._get_image_blocks(page)
        has_images = len(image_blocks) > 0
        
        # Analyze native text
        native_text_length = len(native_text.strip())
        has_sufficient_native_text = native_text_length >= self.NATIVE_TEXT_THRESHOLD
        
        # Calculate image coverage
        image_coverage = self._estimate_image_coverage(page, image_blocks)
        
        # Initial classification
        if has_sufficient_native_text and not has_images:
            page_type = PageType.TEXT_PAGE
            confidence = 0.95
            details = {"reason": "Native text PDF with no images"}
        
        elif has_sufficient_native_text and has_images:
            page_type = PageType.MIXED_PAGE
            confidence = 0.85
            details = {
                "reason": "Contains both text and images",
                "image_coverage": image_coverage,
            }
        
        elif has_images and not has_sufficient_native_text:
            # Likely scanned or image-only - detect handwriting
            handwriting_info = None
            if enable_handwriting_detection:
                handwriting_info = self._detect_handwriting(image_blocks)
            
            if handwriting_info and handwriting_info.is_handwritten:
                page_type = PageType.HANDWRITTEN_PAGE
                confidence = handwriting_info.confidence
                details = {
                    "reason": "Detected handwritten content",
                    "handwriting_confidence": handwriting_info.confidence,
                }
            elif image_coverage > self.IMAGE_TO_TEXT_RATIO:
                page_type = PageType.IMAGE_PAGE
                confidence = 0.85
                details = {
                    "reason": "Primarily image content",
                    "image_coverage": image_coverage,
                }
            else:
                page_type = PageType.SCANNED_PAGE
                confidence = 0.80
                details = {
                    "reason": "Likely scanned document",
                    "image_coverage": image_coverage,
                }
        
        else:
            # No text, no images - blank or corrupted
            page_type = PageType.IMAGE_PAGE
            confidence = 0.50
            details = {"reason": "Blank or content-less page"}
        
        handwriting = None
        if enable_handwriting_detection and page_type in (
            PageType.HANDWRITTEN_PAGE,
            PageType.MIXED_PAGE,
        ):
            handwriting = self._detect_handwriting(image_blocks)
        
        return PageClassification(
            page_number=page_number,
            page_type=page_type,
            confidence=confidence,
            extracted_text_length=native_text_length,
            has_images=has_images,
            handwriting=handwriting,
            classification_details=details,
        )
    
    def classify_pages(
        self,
        doc: fitz.Document,
        page_texts: list[str],
        enable_handwriting_detection: bool = True,
    ) -> list[PageClassification]:
        """
        Classify all pages in a PDF document.
        
        Args:
            doc: PyMuPDF document
            page_texts: List of extracted texts per page
            enable_handwriting_detection: Whether to detect handwriting
        
        Returns:
            List of PageClassification per page
        """
        classifications = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            native_text = page_texts[page_num] if page_num < len(page_texts) else ""
            
            classification = self.classify_page(
                page=page,
                page_number=page_num + 1,
                native_text=native_text,
                enable_handwriting_detection=enable_handwriting_detection,
            )
            classifications.append(classification)
            
            self.logger.info(
                "Classified page",
                page_number=page_num + 1,
                page_type=classification.page_type.value,
                confidence=classification.confidence,
            )
        
        return classifications
    
    def _get_image_blocks(self, page: fitz.Page) -> list[Dict[str, Any]]:
        """Extract all image blocks from a page."""
        try:
            page_dict = page.get_text("dict")
            images = []
            
            for block in page_dict.get("blocks", []):
                if block.get("type") == 1:  # Image block
                    images.append(block)
            
            return images
        except Exception as e:
            self.logger.warning("Failed to extract image blocks", error=str(e))
            return []
    
    def _estimate_image_coverage(
        self,
        page: fitz.Page,
        image_blocks: list[Dict[str, Any]],
    ) -> float:
        """
        Estimate what percentage of page is covered by images.
        
        Returns:
            Float between 0.0 and 1.0
        """
        if not image_blocks:
            return 0.0
        
        try:
            page_area = page.get_area()
            if page_area == 0:
                return 0.0
            
            image_area = 0.0
            for block in image_blocks:
                rect = block.get("bbox")
                if rect:
                    x0, y0, x1, y1 = rect
                    image_area += (x1 - x0) * (y1 - y0)
            
            coverage = min(image_area / page_area, 1.0)
            return round(coverage, 2)
        
        except Exception as e:
            self.logger.warning("Failed to estimate image coverage", error=str(e))
            return 0.5
    
    def _detect_handwriting(
        self,
        image_blocks: list[Dict[str, Any]],
    ) -> Optional[HandwritingDetection]:
        """
        Detect if page contains handwritten content.
        
        This is a heuristic implementation. In production, you might use
        specialized handwriting detection ML models.
        
        For now, returns placeholder with requires_review=True for mixed content.
        """
        # Placeholder implementation
        # In production, this would call a handwriting detection model
        # or use advanced image analysis
        
        if not image_blocks:
            return None
        
        # Heuristic: if images exist and text is sparse, likely handwritten
        # Return with requires_review=True to be safe
        return HandwritingDetection(
            is_handwritten=True,
            confidence=0.60,  # Conservative confidence
            handwriting_percentage=0.70,
            requires_review=True,  # Always require review for handwritten
        )
    
    def get_ocr_priority_pages(
        self,
        classifications: list[PageClassification],
    ) -> list[int]:
        """
        Get page numbers that should be prioritized for OCR.
        
        Returns pages that are:
        - SCANNED_PAGE
        - IMAGE_PAGE
        - HANDWRITTEN_PAGE
        - Mixed pages with low native text
        
        Args:
            classifications: List of PageClassification objects
        
        Returns:
            List of 1-based page numbers to OCR
        """
        priority_pages = []
        
        for classification in classifications:
            if classification.page_type in (
                PageType.SCANNED_PAGE,
                PageType.IMAGE_PAGE,
                PageType.HANDWRITTEN_PAGE,
            ):
                priority_pages.append(classification.page_number)
            
            elif (
                classification.page_type == PageType.MIXED_PAGE
                and classification.extracted_text_length < self.NATIVE_TEXT_THRESHOLD / 2
            ):
                priority_pages.append(classification.page_number)
        
        return priority_pages
