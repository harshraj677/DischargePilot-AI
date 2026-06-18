"""
Groq Vision Service

Provides vision-based OCR for clinical document page images using Groq's
chat completions with an image_url content block. Unlike Gemini's
response_schema, Groq has no enforced structured-output schema, so the
prompt (GroqConfig.VISION_OCR_PROMPT) explicitly specifies the JSON shape
and the response is parsed + validated against OCRPageExtraction here.
"""

import io
import json
import logging
from typing import List, Optional, Tuple

from PIL import Image
from pydantic import BaseModel, Field, ValidationError

from .client import get_groq_client
from .config import GroqConfig

logger = logging.getLogger(__name__)


class ImageProcessingError(Exception):
    """Image processing / OCR error"""
    pass


class OCRPageExtraction(BaseModel):
    """Schema Groq's OCR response is validated against for one page."""

    extracted_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    handwriting_detected: bool
    handwriting_percentage: float = Field(ge=0.0, le=100.0)
    unclear_sections: List[str] = Field(default_factory=list)
    requires_review: bool


def _parse_ocr_json(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())


class GroqVisionService:
    """
    Vision service using Groq for clinical document OCR.
    """

    SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
    MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20MB

    def __init__(self):
        """Initialize vision service"""
        self.client = get_groq_client()

    def perform_ocr(
        self,
        image: Image.Image,
        page_number: Optional[int] = None,
    ) -> OCRPageExtraction:
        """
        Perform OCR on a document page image.

        Returns an OCRPageExtraction parsed and validated from Groq's JSON
        response — required fields are enforced by pydantic, raising
        ImageProcessingError if the response doesn't conform.
        """
        media_type, image_bytes = self._encode_image(image)
        import base64
        b64_data = base64.b64encode(image_bytes).decode("ascii")

        try:
            response = self.client.chat.completions.create(
                model=GroqConfig.VISION_MODEL,
                max_tokens=GroqConfig.MAX_OUTPUT_TOKENS,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{b64_data}"},
                            },
                            {"type": "text", "text": GroqConfig.VISION_OCR_PROMPT},
                        ],
                    }
                ],
            )
        except Exception as e:
            # Let groq.APIError subclasses (rate-limit / server errors)
            # propagate as-is so the OCR provider's retry decorator can
            # recognize and retry them.
            import groq

            if isinstance(e, groq.APIError):
                raise
            logger.error(f"OCR failed: {e}")
            raise ImageProcessingError(f"OCR processing failed: {e}") from e

        raw_text = response.choices[0].message.content or ""
        try:
            data = _parse_ocr_json(raw_text)
            result = OCRPageExtraction(**data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ImageProcessingError(f"Groq returned no structured OCR result: {exc}") from exc

        logger.info(f"OCR completed for page {page_number}: {result.confidence:.2f} confidence")
        return result

    def _encode_image(self, image: Image.Image) -> Tuple[str, bytes]:
        """Serialize a PIL image to bytes plus its media type."""
        fmt = (image.format or "PNG").upper()
        save_format = "JPEG" if fmt == "JPG" else fmt
        media_type = f"image/{save_format.lower()}"

        buffer = io.BytesIO()
        image.save(buffer, format=save_format)
        return media_type, buffer.getvalue()

    def validate_image(self, image: Image.Image) -> bool:
        """
        Validate image before processing.

        Args:
            image: PIL Image

        Returns:
            True if valid, raises ImageProcessingError otherwise
        """
        if not image:
            raise ImageProcessingError("Image is None")

        if image.format and image.format.upper() not in self.SUPPORTED_FORMATS:
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
        if image.mode in ("RGBA", "P", "CMYK"):
            rgb_image = Image.new("RGB", image.size, (255, 255, 255))
            rgb_image.paste(image, (0, 0), image if image.mode == "RGBA" else None)
            return rgb_image
        return image
