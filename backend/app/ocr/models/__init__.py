"""OCR Models and Data Structures"""
from .ocr_result import (
    OCRResult,
    OCRResultWithFallback,
    PageClassification,
    PageType,
    HandwritingDetection,
    OCRMetadata,
)

__all__ = [
    "OCRResult",
    "OCRResultWithFallback",
    "PageClassification",
    "PageType",
    "HandwritingDetection",
    "OCRMetadata",
]
