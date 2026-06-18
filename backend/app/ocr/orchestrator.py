"""
OCR Orchestrator

Orchestrates the complete OCR pipeline:
1. Classification
2. Fallback decision
3. Image extraction
4. Provider selection
5. Handwriting detection
6. Safety validation
"""
from typing import Optional, List
import fitz

from app.ocr.page_classifier import PageClassifier
from app.ocr.fallback_engine import OCRFallbackEngine
from app.ocr.image_extractor import PDFImageExtractor
from app.ocr.handwriting_processor import HandwritingProcessor
from app.ocr.models import (
    OCRResult,
    OCRResultWithFallback,
    PageClassification,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class OCROrchestrator:
    """
    Orchestrates document OCR processing with fallback and safety.
    
    Workflow:
    1. Classify all pages
    2. For each page needing OCR:
       a. Determine if OCR is necessary
       b. Extract page image
       c. Run through fallback engine
       d. Process handwriting if detected
       e. Validate safety
    3. Collect results with provenance
    """
    
    def __init__(
        self,
        primary_provider: str = "groq",
        enable_handwriting_detection: bool = True,
    ):
        """
        Initialize OCR orchestrator.
        
        Args:
            primary_provider: Primary OCR provider
            enable_handwriting_detection: Whether to detect handwriting
        """
        self.classifier = PageClassifier()
        self.fallback_engine = OCRFallbackEngine(
            primary_provider=primary_provider
        )
        self.handwriting_processor = HandwritingProcessor()
        self.image_extractor = PDFImageExtractor()
        
        self.enable_handwriting_detection = enable_handwriting_detection
        self.logger = logger
    
    def process_document(
        self,
        doc: fitz.Document,
        document_id: str,
        document_name: str,
        page_texts: List[str],
    ) -> dict:
        """
        Process entire document with OCR pipeline.
        
        Args:
            doc: PyMuPDF document
            document_id: Document ID
            document_name: Document filename
            page_texts: Native text extraction per page
        
        Returns:
            Dict with:
            - classifications: List of PageClassification per page
            - ocr_results: Dict of page_number -> OCRResultWithFallback
            - summary: Processing summary
        """
        
        self.logger.info(
            "Starting OCR orchestration",
            document_id=document_id,
            document_name=document_name,
            pages=len(doc),
        )
        
        # Step 1: Classify all pages
        classifications = self.classifier.classify_pages(
            doc,
            page_texts,
            enable_handwriting_detection=self.enable_handwriting_detection,
        )
        
        # Step 2: Determine which pages need OCR
        ocr_priority_pages = self.classifier.get_ocr_priority_pages(
            classifications
        )
        
        self.logger.info(
            "Page classification complete",
            total_pages=len(doc),
            ocr_priority_pages=len(ocr_priority_pages),
            priority_pages=ocr_priority_pages,
        )
        
        # Step 3: Process priority pages with OCR
        ocr_results = {}
        ocr_attempt_count = 0
        ocr_success_count = 0
        
        for page_num in ocr_priority_pages:
            page_idx = page_num - 1  # Convert to 0-based
            
            if page_idx < 0 or page_idx >= len(doc):
                continue
            
            page = doc[page_idx]
            classification = classifications[page_idx]
            native_text = page_texts[page_idx] if page_idx < len(page_texts) else ""
            
            ocr_attempt_count += 1
            
            result = self.fallback_engine.process_page(
                page=page,
                page_number=page_num,
                document_id=document_id,
                native_text=native_text,
                page_classification=classification,
            )
            
            if result:
                ocr_success_count += 1
                
                # Process handwriting if detected
                selected_result = result.selected_result
                if selected_result.page_classification.handwriting:
                    cleaned_text, hw_conf, requires_review = (
                        self.handwriting_processor.process_ocr_result(
                            selected_result
                        )
                    )
                    selected_result.extracted_text = cleaned_text
                    selected_result.confidence_score = min(
                        selected_result.confidence_score,
                        hw_conf,
                    )
                    selected_result.requires_manual_review = (
                        selected_result.requires_manual_review or requires_review
                    )
                
                ocr_results[page_num] = result
                
                self.logger.info(
                    "OCR processed",
                    page=page_num,
                    provider=selected_result.metadata.provider,
                    confidence=selected_result.confidence_score,
                    requires_review=selected_result.requires_manual_review,
                )
        
        # Step 4: Create summary
        summary = {
            "document_id": document_id,
            "document_name": document_name,
            "total_pages": len(doc),
            "pages_with_native_text": sum(
                1 for c in classifications if c.extracted_text_length > 0
            ),
            "pages_requiring_ocr": len(ocr_priority_pages),
            "ocr_attempts": ocr_attempt_count,
            "ocr_successful": ocr_success_count,
            "available_providers": self.fallback_engine.get_available_providers(),
        }
        
        self.logger.info(
            "OCR orchestration complete",
            **summary,
        )
        
        return {
            "classifications": classifications,
            "ocr_results": ocr_results,
            "summary": summary,
        }
    
    def get_combined_text(
        self,
        doc: fitz.Document,
        document_id: str,
        page_texts: List[str],
        ocr_results: dict,
    ) -> str:
        """
        Combine native and OCR text for complete document.
        
        Uses native text if available, falls back to OCR text.
        
        Args:
            doc: PyMuPDF document
            document_id: Document ID
            page_texts: Native extraction per page
            ocr_results: Dict of OCR results from process_document
        
        Returns:
            Combined text with page markers
        """
        combined_parts = []
        
        for page_num in range(len(doc)):
            page_number = page_num + 1
            
            # Try native text first
            if page_num < len(page_texts) and page_texts[page_num].strip():
                text = page_texts[page_num]
                source = "native"
            
            # Fall back to OCR
            elif page_number in ocr_results:
                result = ocr_results[page_number]
                text = result.selected_result.extracted_text
                source = f"ocr_{result.selected_result.metadata.provider}"
            
            else:
                text = ""
                source = "none"
            
            if text.strip():
                combined_parts.append(
                    f"--- Page {page_number} ({source}) ---\n{text}"
                )
        
        return "\n\n".join(combined_parts)
