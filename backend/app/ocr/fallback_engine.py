"""
OCR Fallback Engine

Manages OCR provider selection and fallback strategy.
- Attempts primary provider
- Falls back to alternative providers on failure
- Selects best result based on confidence
- Optimizes by skipping OCR when unnecessary
"""
from typing import Optional, List
import fitz

from app.config import settings
from app.ocr.models import (
    OCRResult,
    OCRResultWithFallback,
    PageClassification,
    PageType,
)
from app.ocr.providers import (
    OCRProvider,
    ClaudeVisionOCR,
    GroqVisionOCR,
    EasyOCRProvider,
    TesseractOCRProvider,
)
from app.ocr.image_extractor import PDFImageExtractor
from app.utils.logging import get_logger

logger = get_logger(__name__)


class OCRFallbackEngine:
    """
    Manages OCR processing with fallback strategy.
    
    Workflow:
    1. Check if text extraction is sufficient
    2. If not, try primary OCR provider
    3. If primary fails, try fallback providers
    4. Select best result based on confidence
    5. Return with metadata about selection
    """
    
    # Text thresholds
    SUFFICIENT_TEXT_THRESHOLD = 100  # Chars for no OCR needed
    LOW_TEXT_THRESHOLD = 30  # Chars - consider OCR
    
    # Provider priority order (can be configured)
    DEFAULT_PROVIDER_PRIORITY = [
        "groq",       # Primary - best for medical
        "claude",     # Fallback 1 - secondary AI vision provider
        "easyocr",    # Fallback 2 - lightweight
        "tesseract",  # Fallback 3 - reliable
    ]

    def __init__(
        self,
        primary_provider: str = "groq",
        fallback_providers: Optional[List[str]] = None,
        enable_fallback: bool = True,
        enable_optimization: bool = True,
    ):
        """
        Initialize OCR fallback engine.
        
        Args:
            primary_provider: Primary OCR provider ("claude", "easyocr", "tesseract")
            fallback_providers: List of fallback providers in priority order
            enable_fallback: Whether to use fallback providers
            enable_optimization: Whether to skip OCR when unnecessary
        """
        self.primary_provider = primary_provider
        self.fallback_providers = (
            fallback_providers
            or self.DEFAULT_PROVIDER_PRIORITY[1:]
        )
        self.enable_fallback = enable_fallback
        self.enable_optimization = enable_optimization
        
        self.providers: dict[str, OCRProvider] = {}
        self.image_extractor = PDFImageExtractor()

        self._initialize_providers()
        self._ensure_primary_provider_available()
        self.logger = logger

    def _ensure_primary_provider_available(self) -> None:
        """
        If the configured primary provider failed to initialize (e.g. its API
        key isn't set yet), fall through to the first available provider in
        priority order instead of letting every page silently fail OCR — see
        process_page(), which returns None outright when primary_provider
        isn't a registered provider.
        """
        if self.primary_provider in self.providers:
            return

        candidates = [self.primary_provider, *self.fallback_providers, *self.DEFAULT_PROVIDER_PRIORITY]
        fallback = next((name for name in candidates if name in self.providers), None)

        if fallback and fallback != self.primary_provider:
            logger.warning(
                "Configured primary OCR provider unavailable — using fallback instead",
                configured=self.primary_provider,
                using=fallback,
            )
            self.primary_provider = fallback
    
    def _initialize_providers(self) -> None:
        """Initialize available OCR providers."""
        try:
            self.providers["groq"] = GroqVisionOCR()
            logger.info("Groq Vision OCR initialized")
        except Exception as e:
            logger.warning("Failed to initialize Groq Vision OCR", error=str(e))

        try:
            self.providers["claude"] = ClaudeVisionOCR()
            logger.info("Claude Vision OCR initialized")
        except Exception as e:
            logger.warning("Failed to initialize Claude Vision OCR", error=str(e))

        try:
            self.providers["easyocr"] = EasyOCRProvider()
            logger.info("EasyOCR initialized")
        except Exception as e:
            logger.warning("Failed to initialize EasyOCR", error=str(e))
        
        try:
            self.providers["tesseract"] = TesseractOCRProvider()
            logger.info("Tesseract OCR initialized")
        except Exception as e:
            logger.warning("Failed to initialize Tesseract OCR", error=str(e))
    
    def should_run_ocr(
        self,
        native_text: str,
        page_classification: PageClassification,
    ) -> bool:
        """
        Determine if OCR should be run.
        
        Returns False if:
        - Optimization enabled AND native text is sufficient
        - Page is classified as TEXT_PAGE
        
        Returns True if:
        - Page is SCANNED_PAGE, IMAGE_PAGE, or HANDWRITTEN_PAGE
        - Native text is insufficient
        """
        if not self.enable_optimization:
            return page_classification.page_type != PageType.TEXT_PAGE
        
        # Check text sufficiency
        text_length = len(native_text.strip())
        if text_length >= self.SUFFICIENT_TEXT_THRESHOLD:
            return False
        
        # Check page type
        if page_classification.page_type == PageType.TEXT_PAGE:
            return False
        
        # Need OCR for non-text pages or insufficient text
        return text_length < self.LOW_TEXT_THRESHOLD or page_classification.page_type in (
            PageType.SCANNED_PAGE,
            PageType.IMAGE_PAGE,
            PageType.HANDWRITTEN_PAGE,
            PageType.MIXED_PAGE,
        )
    
    def process_page(
        self,
        page: fitz.Page,
        page_number: int,
        document_id: str,
        native_text: str,
        page_classification: PageClassification,
    ) -> Optional[OCRResultWithFallback]:
        """
        Process a page using OCR with fallback strategy.
        
        Args:
            page: PyMuPDF page object
            page_number: 1-based page number
            document_id: Document ID
            native_text: Text from native PDF extraction
            page_classification: Page classification result
        
        Returns:
            OCRResultWithFallback or None if OCR not needed
        """
        # Check if OCR is necessary
        if not self.should_run_ocr(native_text, page_classification):
            logger.debug(
                "Skipping OCR - sufficient native text",
                page=page_number,
                native_text_length=len(native_text),
            )
            return None
        
        logger.info(
            "Running OCR",
            page=page_number,
            page_type=page_classification.page_type.value,
        )
        
        # Extract page image
        image_bytes = self.image_extractor.extract_page_image(page, page_number)
        if image_bytes is None:
            logger.error("Failed to extract page image", page=page_number)
            return None
        
        # Try primary provider
        primary_result = None
        if self.primary_provider in self.providers:
            provider = self.providers[self.primary_provider]
            primary_result = provider.process_image(
                image_bytes=image_bytes,
                page_number=page_number,
                document_id=document_id,
                page_classification=page_classification,
            )
        
        if primary_result is None:
            logger.error(
                "Primary OCR provider failed",
                provider=self.primary_provider,
                page=page_number,
            )
            return None
        
        # Check if we need fallback
        fallback_results = []
        selected_result = primary_result
        fallback_reason = None
        
        if (
            self.enable_fallback
            and primary_result.confidence_score < 0.60
        ):
            logger.info(
                "Primary OCR confidence low, trying fallback providers",
                page=page_number,
                confidence=primary_result.confidence_score,
            )
            
            for provider_name in self.fallback_providers:
                if provider_name not in self.providers:
                    continue
                
                provider = self.providers[provider_name]
                fallback_result = provider.process_image(
                    image_bytes=image_bytes,
                    page_number=page_number,
                    document_id=document_id,
                    page_classification=page_classification,
                )
                
                if fallback_result:
                    fallback_results.append(fallback_result)
                    
                    # Select best result
                    if (
                        fallback_result.confidence_score
                        > selected_result.confidence_score
                    ):
                        selected_result = fallback_result
                        fallback_reason = (
                            f"Selected from {provider_name} "
                            f"(confidence: {fallback_result.confidence_score:.2f})"
                        )
        
        return OCRResultWithFallback(
            primary_result=primary_result,
            fallback_results=fallback_results,
            selected_result=selected_result,
            fallback_reason=fallback_reason,
            selection_reason=(
                fallback_reason
                or f"Primary provider {self.primary_provider} "
                f"selected (confidence: {primary_result.confidence_score:.2f})"
            ),
        )
    
    def set_provider(self, name: str, provider: OCRProvider) -> None:
        """Register a custom OCR provider."""
        self.providers[name] = provider
        logger.info("OCR provider registered", name=name)
    
    def get_available_providers(self) -> list[str]:
        """Get list of available OCR providers."""
        return list(self.providers.keys())
