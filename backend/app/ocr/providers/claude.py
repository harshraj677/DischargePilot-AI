"""
Claude Vision OCR Provider

Uses Anthropic's Claude (vision + structured outputs) as the primary OCR
backend for scanned/image-only clinical document pages.
"""
import time
import io
from typing import Optional, Tuple

from PIL import Image
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.ocr.models import (
    OCRResult,
    PageClassification,
    OCRMetadata,
)
from app.ocr.providers.base import OCRProvider
from app.claude.vision import ClaudeVisionService, ImageProcessingError, OCRPageExtraction
from app.claude.config import ClaudeConfig
from app.utils.logging import get_logger

logger = get_logger(__name__)


# Claude Vision is occasionally flaky under transient load (rate limits, brief
# server overloads, connection hiccups) — retry up to 3 times with exponential
# backoff before giving up on a page. The SDK already retries these internally
# (default max_retries=2); this absorbs the rarer case where every internal
# attempt is exhausted. Authentication/permission/invalid-request errors are
# deliberately excluded — they won't clear on their own, so retrying just
# burns time before falling through to the (slower) fallback providers anyway.
_ocr_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type((
        anthropic.RateLimitError,
        anthropic.APIConnectionError,
        anthropic.InternalServerError,
    )),
    reraise=True,
)


class ClaudeVisionOCR(OCRProvider):
    """
    OCR provider using Claude's vision capabilities with structured outputs.
    """

    def __init__(self):
        """Initialize Claude Vision OCR provider."""
        self.vision_service = ClaudeVisionService()
        self.logger = logger

    def process_image(
        self,
        image_bytes: bytes,
        page_number: int,
        document_id: str,
        page_classification: PageClassification,
    ) -> Optional[OCRResult]:
        """
        Process an image using Claude Vision.
        """
        start_time = time.perf_counter()

        try:
            try:
                img = Image.open(io.BytesIO(image_bytes))
                self.vision_service.validate_image(img)
                img = self.vision_service.convert_to_rgb(img)
                img = self.vision_service.resize_image_if_needed(img)
            except Exception as e:
                self.logger.error("Failed to load image for Claude Vision", error=str(e))
                raise e

            self.logger.info(
                "Calling Claude Vision API",
                page=page_number,
                document_id=document_id,
                model=ClaudeConfig.VISION_MODEL,
            )

            extraction, retry_count = self._call_claude_with_retry(img, page_number)

            duration_ms = (time.perf_counter() - start_time) * 1000

            extracted_text = extraction.extracted_text
            confidence = extraction.confidence
            requires_review = extraction.requires_review
            handwriting_detected = extraction.handwriting_detected
            unclear_sections = extraction.unclear_sections

            review_reason = None
            if requires_review:
                if unclear_sections:
                    review_reason = "Unclear sections: " + ", ".join(unclear_sections)
                elif handwriting_detected:
                    review_reason = "Handwritten content detected"
                else:
                    review_reason = "Low confidence extraction"

            # Basic keyword checks
            extracted_text_lower = extracted_text.lower()
            contains_med = any(k in extracted_text_lower for k in ["mg", "dose", "tablet", "medication"])
            contains_diag = any(k in extracted_text_lower for k in ["diagnosis", "disease", "syndrome", "condition"])
            contains_pii = "mrn" in extracted_text_lower or "dob" in extracted_text_lower

            self._log_processing(
                page_number=page_number,
                document_id=document_id,
                duration_ms=duration_ms,
                text_length=len(extracted_text),
                confidence=confidence,
            )

            return OCRResult(
                document_id=document_id,
                page_number=page_number,
                extracted_text=extracted_text,
                page_classification=page_classification,
                metadata=OCRMetadata(
                    provider="claude",
                    model_name=ClaudeConfig.VISION_MODEL,
                    processing_time_ms=duration_ms,
                    confidence=confidence,
                    retry_count=retry_count,
                ),
                confidence_score=confidence,
                requires_manual_review=requires_review,
                review_reason=review_reason,
                contains_medication_names=contains_med,
                contains_diagnosis_terms=contains_diag,
                contains_patient_identifiers=contains_pii,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000

            self.logger.error(
                "Claude Vision OCR failed after retries",
                page=page_number,
                document_id=document_id,
                error=str(e),
            )
            return OCRResult(
                document_id=document_id,
                page_number=page_number,
                extracted_text="",
                page_classification=page_classification,
                metadata=OCRMetadata(
                    provider="claude",
                    model_name=ClaudeConfig.VISION_MODEL,
                    processing_time_ms=duration_ms,
                    confidence=0.0,
                    retry_count=3,
                    error_message=str(e),
                ),
                confidence_score=0.0,
                requires_manual_review=True,
                review_reason=f"OCR failed after retries: {str(e)}",
            )

    def _call_claude_with_retry(self, img: Image.Image, page_number: int) -> Tuple[OCRPageExtraction, int]:
        """
        Call Claude Vision OCR with up to 3 attempts (exponential backoff) to
        absorb transient rate-limit / overload / connection errors. Returns
        (extraction, attempts_used - 1).

        Unlike the Gemini provider, no asyncio bridging is needed here — the
        Claude vision service uses the synchronous Anthropic client directly,
        matching the synchronous OCRProvider interface.
        """
        attempts = {"count": 0}

        @_ocr_retry
        def _call() -> OCRPageExtraction:
            attempts["count"] += 1
            return self.vision_service.perform_ocr(img, page_number)

        result = _call()
        return result, attempts["count"] - 1

    def supports_handwriting(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "Claude Vision"
