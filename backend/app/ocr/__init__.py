"""
OCR & Vision Enhancement Module

Adds OCR capabilities to DischargePilot AI for processing:
- Scanned PDFs
- Image-only PDFs
- Hospital document photos
- Embedded images in PDFs
- Handwritten clinical notes

Architecture:
1. Page Classification Engine - classify page types
2. Image Extraction - render pages to images
3. OCR Provider Abstraction - support multiple backends
4. Fallback Engine - provider fallback with selection
5. Handwriting Processor - safe handwriting extraction
6. Orchestrator - complete pipeline orchestration
"""

from .models import (
    OCRResult,
    PageClassification,
    PageType,
    HandwritingDetection,
    OCRMetadata,
)
from .page_classifier import PageClassifier
from .image_extractor import PDFImageExtractor
from .fallback_engine import OCRFallbackEngine
from .handwriting_processor import HandwritingProcessor
from .orchestrator import OCROrchestrator
from .providers import (
    OCRProvider,
    ClaudeVisionOCR,
    EasyOCRProvider,
    TesseractOCRProvider,
)

__all__ = [
    # Models
    "OCRResult",
    "PageClassification",
    "PageType",
    "HandwritingDetection",
    "OCRMetadata",
    # Engines
    "PageClassifier",
    "PDFImageExtractor",
    "OCRFallbackEngine",
    "HandwritingProcessor",
    "OCROrchestrator",
    # Providers
    "OCRProvider",
    "ClaudeVisionOCR",
    "EasyOCRProvider",
    "TesseractOCRProvider",
]
