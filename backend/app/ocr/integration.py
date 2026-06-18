"""
OCR Integration with PDF Extractor

Enhances the existing PDF extraction pipeline with OCR fallback.
Maintains backward compatibility with existing code.

Workflow:
1. Extract native PDF text (existing behavior)
2. Classify pages
3. For insufficient text, run OCR
4. Combine native + OCR text
5. Preserve evidence chain
"""
from typing import Optional, Dict, List, Tuple
import fitz

from app.config import settings
from app.ocr.orchestrator import OCROrchestrator
from app.ocr.models import OCRResult
from app.processing.pdf_extractor import ExtractionResult
from app.models.document import PageChunk
from app.models.enums import DocumentType
from app.utils.logging import get_logger

logger = get_logger(__name__)


class OCREnhancedExtractor:
    """
    Enhanced PDF extractor with OCR fallback.
    
    Integrates with existing pdf_extractor.extract_pdf() function
    to add OCR support for scanned/image PDFs.
    """
    
    def __init__(
        self,
        enable_ocr: bool = True,
        primary_ocr_provider: str = "groq",
        enable_handwriting_detection: bool = True,
    ):
        """
        Initialize OCR-enhanced extractor.
        
        Args:
            enable_ocr: Whether to enable OCR fallback
            primary_ocr_provider: Primary OCR provider
            enable_handwriting_detection: Whether to detect handwriting
        """
        self.enable_ocr = enable_ocr
        self.orchestrator = (
            OCROrchestrator(
                primary_provider=primary_ocr_provider,
                enable_handwriting_detection=enable_handwriting_detection,
            )
            if enable_ocr
            else None
        )
        self.logger = logger
    
    def enhance_extraction_result(
        self,
        original_result: ExtractionResult,
        doc: fitz.Document,
        document_id: str,
        document_name: str,
    ) -> Tuple[ExtractionResult, Dict]:
        """
        Enhance extraction result with OCR for scanned pages.
        
        Args:
            original_result: Result from existing pdf_extractor.extract_pdf()
            doc: PyMuPDF document
            document_id: Document ID
            document_name: Document name
        
        Returns:
            Tuple of:
            - Enhanced ExtractionResult with combined text
            - OCR metadata dict for tracking
        """
        
        if not self.enable_ocr or self.orchestrator is None:
            return original_result, {"ocr_enabled": False}
        
        # Extract native texts from original result
        page_texts = [chunk.text for chunk in original_result.page_chunks]
        
        # Run OCR orchestration
        ocr_orchestration = self.orchestrator.process_document(
            doc=doc,
            document_id=document_id,
            document_name=document_name,
            page_texts=page_texts,
        )
        
        # Combine native and OCR text
        combined_text = self.orchestrator.get_combined_text(
            doc=doc,
            document_id=document_id,
            page_texts=page_texts,
            ocr_results=ocr_orchestration["ocr_results"],
        )
        
        # Update page chunks with OCR results where applicable
        enhanced_chunks = self._enhance_page_chunks(
            page_chunks=original_result.page_chunks,
            ocr_results=ocr_orchestration["ocr_results"],
            classifications=ocr_orchestration["classifications"],
        )
        
        # Create enhanced result
        enhanced_result = ExtractionResult(
            page_chunks=enhanced_chunks,
            full_text=combined_text,
            page_count=original_result.page_count,
            processing_logs=original_result.processing_logs,
            empty_page_count=original_result.empty_page_count,
            duration_ms=original_result.duration_ms,
        )
        
        # Create metadata
        ocr_metadata = {
            "ocr_enabled": True,
            "ocr_orchestration": ocr_orchestration["summary"],
            "ocr_provider": self.orchestrator.fallback_engine.primary_provider,
            "pages_enhanced_with_ocr": len(ocr_orchestration["ocr_results"]),
        }
        
        self.logger.info(
            "PDF extraction enhanced with OCR",
            document_id=document_id,
            pages_with_ocr=len(ocr_orchestration["ocr_results"]),
            success_rate=(
                len(ocr_orchestration["ocr_results"])
                / max(1, ocr_orchestration["summary"]["ocr_attempts"])
            ),
        )
        
        return enhanced_result, ocr_metadata
    
    def _enhance_page_chunks(
        self,
        page_chunks: List[PageChunk],
        ocr_results: Dict[int, OCRResult],
        classifications,
    ) -> List[PageChunk]:
        """
        Enhance page chunks with OCR text where applicable.
        
        Args:
            page_chunks: Original page chunks
            ocr_results: OCR results by page number
            classifications: Page classifications
        
        Returns:
            Enhanced page chunks with OCR text included
        """
        enhanced = []
        
        for chunk in page_chunks:
            page_num = chunk.page_number
            
            # Check if OCR was applied to this page
            if page_num in ocr_results:
                ocr_result_with_fallback = ocr_results[page_num]
                selected_result = ocr_result_with_fallback.selected_result
                
                # Combine native and OCR text
                combined_text = f"{chunk.text}\n\n[OCR]\n{selected_result.extracted_text}"
                
                # Create enhanced chunk with OCR metadata attached
                enhanced_chunk = PageChunk(
                    page_number=chunk.page_number,
                    text=combined_text,
                    char_count=len(combined_text),
                    word_count=len(combined_text.split()),
                    is_empty=False,  # Has OCR text
                    document_id=chunk.document_id,
                    document_name=chunk.document_name,
                    document_type=chunk.document_type,
                    ocr_metadata={
                        "provider": selected_result.metadata.provider,
                        "confidence": selected_result.confidence_score,
                        "requires_review": selected_result.requires_manual_review,
                        "extraction_method": "ocr",
                    },
                )

                enhanced.append(enhanced_chunk)
            
            else:
                # No OCR, keep original chunk
                enhanced.append(chunk)
        
        return enhanced
