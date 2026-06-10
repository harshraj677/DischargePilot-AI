"""
Anthropic Claude Vision Service

Provides vision-based OCR for clinical document page images using Claude's
native structured-output support: passing output_format=OCRPageExtraction to
client.messages.parse() guarantees a schema-conformant, validated response —
no markdown-fence stripping, no manual JSON parsing, no missing "confidence"
field to default away (the bug class that made every low-signal Gemini page
fall through to the much slower EasyOCR pass).
"""

import io
import base64
import logging
from typing import List, Optional, Tuple

from PIL import Image
from pydantic import BaseModel, Field

from .client import get_claude_client
from .config import ClaudeConfig

logger = logging.getLogger(__name__)


class ImageProcessingError(Exception):
    """Image processing / OCR error"""
    pass


class OCRPageExtraction(BaseModel):
    """Schema Claude's structured output is constrained to for one page."""

    extracted_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    handwriting_detected: bool
    handwriting_percentage: float = Field(ge=0.0, le=100.0)
    unclear_sections: List[str] = Field(default_factory=list)
    requires_review: bool


class ClaudeVisionService:
    """
    Vision service using Claude for clinical document OCR.
    """

    SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
    MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20MB — Anthropic's per-image limit

    def __init__(self):
        """Initialize vision service"""
        self.client = get_claude_client()

    def perform_ocr(
        self,
        image: Image.Image,
        page_number: Optional[int] = None,
    ) -> OCRPageExtraction:
        """
        Perform OCR on a document page image.

        Returns an OCRPageExtraction — guaranteed schema-conformant by
        Claude's structured outputs (output_format), so required fields such
        as "confidence" are never missing or defaulted.
        """
        media_type, image_b64 = self._encode_image(image)

        try:
            response = self.client.messages.parse(
                model=ClaudeConfig.VISION_MODEL,
                max_tokens=ClaudeConfig.MAX_OUTPUT_TOKENS,
                output_config={"effort": "low"},  # straightforward transcription task
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_b64,
                                },
                            },
                            {"type": "text", "text": ClaudeConfig.VISION_OCR_PROMPT},
                        ],
                    }
                ],
                output_format=OCRPageExtraction,
            )

            result = response.parsed_output
            logger.info(f"OCR completed for page {page_number}: {result.confidence:.2f} confidence")
            return result

        except Exception as e:
            logger.error(f"OCR failed: {e}")
            raise ImageProcessingError(f"OCR processing failed: {e}") from e

    def _encode_image(self, image: Image.Image) -> Tuple[str, str]:
        """Serialize a PIL image to base64 plus its Anthropic media type."""
        fmt = (image.format or "PNG").upper()
        save_format = "JPEG" if fmt == "JPG" else fmt
        media_type = f"image/{save_format.lower()}"

        buffer = io.BytesIO()
        image.save(buffer, format=save_format)
        return media_type, base64.standard_b64encode(buffer.getvalue()).decode("utf-8")

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
