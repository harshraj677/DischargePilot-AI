"""
Google Gemini Integration Module

Provides complete Gemini API integration for DischargePilot AI with:
- Vision-based OCR for scanned PDFs and images
- Clinical content extraction
- Discharge summary generation
- Agent planning and reasoning
"""

from .client import GeminiClient, get_gemini_client, generate_with_gemini
from .config import GeminiConfig, GeminiModel
from .vision import GeminiVisionService, ImageProcessingError
from .extraction import (
    GeminiClinicalExtractor,
    ExtractedClinicalData,
    ExtractionSource,
    ConfidenceLevel,
    Diagnosis,
    Medication,
    Allergy,
    Procedure,
    LabResult,
)

__all__ = [
    # Client
    'GeminiClient',
    'get_gemini_client',
    'generate_with_gemini',
    
    # Configuration
    'GeminiConfig',
    'GeminiModel',
    
    # Vision
    'GeminiVisionService',
    'ImageProcessingError',
    
    # Extraction
    'GeminiClinicalExtractor',
    'ExtractedClinicalData',
    'ExtractionSource',
    'ConfidenceLevel',
    'Diagnosis',
    'Medication',
    'Allergy',
    'Procedure',
    'LabResult',
]
