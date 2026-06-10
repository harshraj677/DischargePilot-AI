"""
Gemini Vision-Based OCR Module

Provides OCR capabilities for scanned documents, handwritten notes,
and image-based clinical documents using Google Gemini Vision.
"""

import json
import logging
from typing import Optional, Dict, Any
from PIL import Image
from datetime import datetime

from .client import get_gemini_client
from .config import GeminiConfig
from .vision import GeminiVisionService

logger = logging.getLogger(__name__)

class GeminiVisionOCR:
    """
    OCR service using Gemini Vision for clinical documents.
    
    Handles:
    - Text extraction from scanned PDFs
    - Handwritten note recognition
    - Clinical content preservation
    - Confidence scoring
    - Safety validation
    """
    
    def __init__(self):
        """Initialize OCR service"""
        self.client = get_gemini_client()
        self.vision_service = GeminiVisionService()
    
    async def extract_from_image(
        self,
        image: Image.Image,
        page_number: Optional[int] = None,
        document_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract all clinical content from document image.
        
        Args:
            image: PIL Image of document
            page_number: Optional page number for tracking
            document_context: Optional document type/context
            
        Returns:
            Dict with extracted content and confidence
            {
                "raw_text": "...",
                "diagnoses": [...],
                "medications": [...],
                "allergies": [...],
                "procedures": [...],
                "labs": [...],
                "clinical_notes": "...",
                "handwriting_detected": bool,
                "handwriting_confidence": float,
                "text_confidence": float,
                "overall_confidence": float,
                "page_number": int,
                "requires_review": bool,
                "review_reasons": [...]
            }
        """
        try:
            # Validate and prepare image
            image = self.vision_service.convert_to_rgb(image)
            image = self.vision_service.resize_image_if_needed(image)
            
            # Extract clinical content
            extraction = await self._extract_clinical_content(image, document_context)
            
            # Perform OCR
            ocr_result = await self.vision_service.perform_ocr(image, page_number)
            
            # Detect handwriting
            handwriting = await self.vision_service.detect_handwriting(image)
            
            # Combine results
            result = {
                "raw_text": ocr_result.get("extracted_text", ""),
                "diagnoses": extraction.get("diagnoses", []),
                "medications": extraction.get("medications", []),
                "allergies": extraction.get("allergies", []),
                "procedures": extraction.get("procedures", []),
                "labs": extraction.get("labs", []),
                "clinical_notes": extraction.get("clinical_notes", ""),
                "handwriting_detected": handwriting.get("is_handwritten", False),
                "handwriting_confidence": handwriting.get("clarity_score", 0) / 100.0,
                "text_confidence": ocr_result.get("confidence", 0.5),
                "page_number": page_number,
                "extracted_at": datetime.now().isoformat(),
            }
            
            # Calculate overall confidence
            result['overall_confidence'] = self._calculate_confidence(result)
            
            # Determine if review needed
            review_reasons = []
            if result['overall_confidence'] < 0.75:
                review_reasons.append("Low overall confidence")
            if result['handwriting_detected'] and result['handwriting_confidence'] < 0.7:
                review_reasons.append("Unclear handwriting detected")
            if ocr_result.get('requires_review'):
                review_reasons.append("OCR requires manual verification")
            
            result['requires_review'] = len(review_reasons) > 0
            result['review_reasons'] = review_reasons
            
            logger.info(f"OCR extraction complete for page {page_number}: "
                       f"confidence={result['overall_confidence']:.2f}, "
                       f"handwriting={result['handwriting_detected']}")
            
            return result
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return {
                "raw_text": "",
                "diagnoses": [],
                "medications": [],
                "allergies": [],
                "procedures": [],
                "labs": [],
                "clinical_notes": "",
                "handwriting_detected": False,
                "handwriting_confidence": 0.0,
                "text_confidence": 0.0,
                "overall_confidence": 0.0,
                "page_number": page_number,
                "requires_review": True,
                "review_reasons": [f"Extraction error: {str(e)}"],
            }
    
    async def _extract_clinical_content(
        self,
        image: Image.Image,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract clinical content from image"""
        prompt = """Analyze this clinical document image and extract structured clinical information.

EXTRACT AND STRUCTURE:
- diagnoses: list of diagnoses found
- medications: list of medications with dosages if available
- allergies: list of allergies with severity
- procedures: list of medical procedures
- labs: list of lab results with values
- clinical_notes: summary of clinical notes
- special_findings: any important findings

Return ONLY valid JSON with these keys.
If information is not clearly visible, omit the key.
For unclear items, add [UNCLEAR] marker.

Focus on accuracy over completeness - only extract what you can clearly read."""

        try:
            response = await self.client.analyze_image(
                image=image,
                prompt=prompt,
                config=GeminiConfig.VISION_OCR_CONFIG,
            )
            
            # Parse response as JSON
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                start = response.find('{')
                end = response.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(response[start:end])
                
                # Fallback
                return {
                    "clinical_notes": response,
                }
        except Exception as e:
            logger.error(f"Clinical content extraction failed: {e}")
            return {}
    
    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """Calculate overall OCR confidence"""
        text_conf = result.get('text_confidence', 0.5)
        handwriting_conf = result.get('handwriting_confidence', 1.0)
        
        # If handwriting detected, use lower confidence
        if result.get('handwriting_detected'):
            combined = min(text_conf, handwriting_conf) * 0.95  # Slight penalty for mixed
        else:
            combined = text_conf
        
        # If much content requires review, lower confidence
        review_count = len(result.get('review_reasons', []))
        if review_count > 0:
            combined *= (1 - (review_count * 0.1))
        
        return max(0.0, min(1.0, combined))


# Convenience function
async def ocr_image(
    image: Image.Image,
    page_number: Optional[int] = None,
) -> Dict[str, Any]:
    """Perform OCR on image"""
    ocr = GeminiVisionOCR()
    return await ocr.extract_from_image(image, page_number)
