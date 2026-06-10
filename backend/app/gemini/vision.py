"""
Google Gemini Vision Service

Provides vision-specific functionality for clinical document analysis,
OCR, and image processing.
"""

import json
import logging
from typing import Optional, List, Dict, Any
from PIL import Image
import io

from .client import get_gemini_client
from .config import GeminiConfig

logger = logging.getLogger(__name__)

class ImageProcessingError(Exception):
    """Image processing error"""
    pass

class GeminiVisionService:
    """
    Vision service using Gemini for clinical document analysis.
    
    Provides:
    - Clinical content extraction from images
    - Handwriting detection
    - Confidence scoring
    - OCR with safety validation
    """
    
    # Supported image formats
    SUPPORTED_FORMATS = {'JPEG', 'PNG', 'WEBP', 'GIF'}
    MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20MB
    
    def __init__(self):
        """Initialize vision service"""
        self.client = get_gemini_client()
    
    async def extract_clinical_content(
        self,
        image: Image.Image,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract clinical content from image.
        
        Args:
            image: PIL Image
            context: Optional document context
            
        Returns:
            Dict with extracted clinical content
            {
                "diagnoses": [...],
                "medications": [...],
                "allergies": [...],
                "procedures": [...],
                "labs": [...],
                "clinical_notes": "...",
                "handwriting_detected": bool,
                "handwriting_confidence": float,
                "overall_confidence": float,
                "requires_review": bool,
            }
        """
        try:
            prompt = self._build_extraction_prompt(context)
            
            response = await self.client.analyze_image(
                image=image,
                prompt=prompt,
                config=GeminiConfig.VISION_OCR_CONFIG,
            )
            
            # Parse response as JSON
            result = self._parse_json_response(response)
            
            # Add confidence scoring
            confidence = self._calculate_confidence(result)
            result['overall_confidence'] = confidence
            result['requires_review'] = confidence < 0.7
            
            logger.info(f"Extracted clinical content with confidence: {confidence:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"Clinical content extraction failed: {e}")
            raise ImageProcessingError(f"Failed to extract clinical content: {e}")
    
    async def perform_ocr(
        self,
        image: Image.Image,
        page_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Perform OCR on document image.
        
        Args:
            image: PIL Image
            page_number: Optional page number for tracking
            
        Returns:
            Dict with OCR results
            {
                "extracted_text": "...",
                "handwriting_percentage": float,
                "confidence": float,
                "page_number": int,
                "requires_review": bool,
                "unclear_sections": [...],
                "handwriting_assessment": {...}
            }
        """
        try:
            prompt = GeminiConfig.VISION_OCR_PROMPT
            
            response = await self.client.analyze_image(
                image=image,
                prompt=prompt,
                config=GeminiConfig.VISION_OCR_CONFIG,
            )
            
            result = self._parse_json_response(response)
            
            # Add page tracking
            if page_number is not None:
                result['page_number'] = page_number
            
            # Assess if review needed
            confidence = result.get('confidence', 0.5)
            has_handwriting = result.get('handwriting_detected', False)
            has_unclear = len(result.get('unclear_sections', [])) > 0
            
            result['requires_review'] = (
                confidence < 0.75 or 
                has_handwriting or 
                has_unclear
            )
            
            logger.info(f"OCR completed for page {page_number}: {confidence:.2f} confidence")
            return result
            
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            raise ImageProcessingError(f"OCR processing failed: {e}")
    
    async def detect_handwriting(
        self,
        image: Image.Image,
    ) -> Dict[str, Any]:
        """
        Detect and assess handwriting in image.
        
        Args:
            image: PIL Image
            
        Returns:
            Dict with handwriting assessment
            {
                "is_handwritten": bool,
                "handwriting_percentage": float,
                "clarity_score": float,
                "legibility": "high" | "medium" | "low",
                "requires_manual_review": bool,
                "assessment": "..."
            }
        """
        try:
            prompt = """Analyze this image for handwritten content.

Return JSON with:
- is_handwritten: boolean
- handwriting_percentage: 0-100 (percentage of handwritten content)
- clarity_score: 0-100 (how clear is the handwriting)
- legibility: "high" (clear) | "medium" (partially clear) | "low" (unclear)
- requires_manual_review: boolean (true if legibility low)
- assessment: brief description

Focus on clinical clarity for safety."""
            
            response = await self.client.analyze_image(
                image=image,
                prompt=prompt,
                config=GeminiConfig.VISION_OCR_CONFIG,
            )
            
            result = self._parse_json_response(response)
            
            # Safety: flag unclear handwriting
            if result.get('legibility') == 'low':
                result['requires_manual_review'] = True
            
            logger.info(f"Handwriting assessment: {result.get('legibility')} legibility")
            return result
            
        except Exception as e:
            logger.error(f"Handwriting detection failed: {e}")
            raise ImageProcessingError(f"Handwriting detection failed: {e}")
    
    def _build_extraction_prompt(self, context: Optional[str]) -> str:
        """Build clinical extraction prompt with context"""
        base_prompt = GeminiConfig.VISION_OCR_PROMPT
        
        if context:
            return f"{base_prompt}\n\nContext: {context}"
        return base_prompt
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from Gemini response"""
        try:
            # Try direct JSON parsing first
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            try:
                start = response.find('{')
                end = response.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = response[start:end]
                    return json.loads(json_str)
            except:
                pass
            
            # Fallback: return structured response
            logger.warning("Could not parse JSON response, returning structured dict")
            return {
                "extracted_text": response,
                "confidence": 0.5,
                "parsing_note": "Response was not valid JSON",
            }
    
    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """Calculate overall confidence from extraction result"""
        # Start with base confidence from response
        confidence = result.get('confidence', 0.7)
        
        # Adjust for handwriting
        if result.get('handwriting_detected', False):
            hw_conf = result.get('handwriting_confidence', 0.5)
            confidence = min(confidence, hw_conf)
        
        # Adjust for unclear sections
        unclear_count = len(result.get('unclear_sections', []))
        if unclear_count > 0:
            confidence *= (1 - (unclear_count * 0.1))  # Reduce by 10% per unclear section
        
        # Clamp to 0-1
        return max(0.0, min(1.0, confidence))
    
    def validate_image(self, image: Image.Image) -> bool:
        """
        Validate image before processing.
        
        Args:
            image: PIL Image
            
        Returns:
            True if valid, raises error otherwise
        """
        if not image:
            raise ImageProcessingError("Image is None")
        
        # Check format
        if image.format not in self.SUPPORTED_FORMATS:
            raise ImageProcessingError(f"Unsupported image format: {image.format}")
        
        # Check size — serialize in-memory so this works for images that have
        # no backing file path (e.g. PDF pages rendered straight to a buffer)
        buffer = io.BytesIO()
        image.save(buffer, format=image.format or "PNG")
        size_bytes = buffer.tell()
        if size_bytes > self.MAX_IMAGE_SIZE:
            raise ImageProcessingError(f"Image too large: {size_bytes / 1024 / 1024:.1f}MB (max 20MB)")
        
        return True
    
    @staticmethod
    def resize_image_if_needed(image: Image.Image, max_width: int = 4096, max_height: int = 4096) -> Image.Image:
        """Resize image if it exceeds maximum dimensions"""
        if image.width > max_width or image.height > max_height:
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            logger.info(f"Resized image to {image.width}x{image.height}")
        return image
    
    @staticmethod
    def convert_to_rgb(image: Image.Image) -> Image.Image:
        """Convert image to RGB if needed"""
        if image.mode in ('RGBA', 'P', 'CMYK'):
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            rgb_image.paste(image, (0, 0), image if image.mode == 'RGBA' else None)
            return rgb_image
        return image
