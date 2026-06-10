"""
Gemini Vision OCR Provider

Uses Google's Gemini 2.5 Pro model with vision capabilities for OCR.
"""
import time
import io
import asyncio
from typing import Optional

from PIL import Image
from google.api_core.exceptions import ResourceExhausted
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from app.ocr.models import (
    OCRResult,
    PageClassification,
    OCRMetadata,
)
from app.ocr.providers.base import OCRProvider
from app.gemini.vision import GeminiVisionService, ImageProcessingError
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _is_quota_exhausted(exc: BaseException) -> bool:
    """
    True if `exc` is (or wraps) a Gemini 429 ResourceExhausted quota error.

    GeminiVisionService wraps the original google.api_core error in a generic
    ImageProcessingError, so the type is recovered by walking the implicit
    exception chain (__cause__ / __context__) rather than isinstance-checking
    the outermost exception.
    """
    seen: set[int] = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ResourceExhausted):
            return True
        current = current.__cause__ or current.__context__
    return False


# Gemini Vision OCR is flaky under rate limits / transient API errors —
# retry up to 3 times with exponential backoff before giving up on a page.
# Daily-quota errors (429 ResourceExhausted) are excluded: they don't clear
# within a backoff window, so retrying just burns ~30-60s per page before
# falling through to the (already slow) EasyOCR fallback anyway.
_ocr_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception(lambda e: not _is_quota_exhausted(e)),
    reraise=True,
)


class GeminiVisionOCR(OCRProvider):
    """
    OCR provider using Gemini's vision capabilities.
    """
    
    def __init__(self):
        """Initialize Gemini Vision OCR provider."""
        self.vision_service = GeminiVisionService()
        self.logger = logger
        # Set once a daily-quota (429 ResourceExhausted) error is seen. The
        # quota won't clear mid-run, so once it trips we skip straight to the
        # fallback providers for the rest of this document instead of paying
        # a network round-trip per page just to get the same 429 again.
        self.quota_exhausted = False

    def process_image(
        self,
        image_bytes: bytes,
        page_number: int,
        document_id: str,
        page_classification: PageClassification,
    ) -> Optional[OCRResult]:
        """
        Process an image using Gemini Vision.
        """
        start_time = time.perf_counter()

        if self.quota_exhausted:
            self.logger.debug(
                "Skipping Gemini Vision — daily quota already exhausted for this run",
                page=page_number,
                document_id=document_id,
            )
            return OCRResult(
                document_id=document_id,
                page_number=page_number,
                extracted_text="",
                page_classification=page_classification,
                metadata=OCRMetadata(
                    provider="gemini",
                    model_name="gemini-2.5-pro",
                    processing_time_ms=0.0,
                    confidence=0.0,
                    error_message="Skipped — Gemini daily quota exhausted earlier in this run",
                ),
                confidence_score=0.0,
                requires_manual_review=True,
                review_reason="Gemini daily quota exhausted — skipped, see fallback result",
            )

        try:
            # Determine image media type and convert to PIL Image
            try:
                img = Image.open(io.BytesIO(image_bytes))
                self.vision_service.validate_image(img)
                img = self.vision_service.convert_to_rgb(img)
                img = self.vision_service.resize_image_if_needed(img)
            except Exception as e:
                self.logger.error("Failed to load image for Gemini Vision", error=str(e))
                raise e
            
            self.logger.info(
                "Calling Gemini Vision API",
                page=page_number,
                document_id=document_id,
            )

            result_dict, retry_count = self._call_gemini_with_retry(img, page_number)

            duration_ms = (time.perf_counter() - start_time) * 1000
            
            extracted_text = result_dict.get("extracted_text", "")
            confidence = result_dict.get("confidence", 0.5)
            requires_review = result_dict.get("requires_review", False)
            handwriting_detected = result_dict.get("handwriting_detected", False)
            unclear_sections = result_dict.get("unclear_sections", [])
            
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
                    provider="gemini",
                    model_name="gemini-2.5-pro",
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

            if _is_quota_exhausted(e):
                self.quota_exhausted = True
                self.logger.warning(
                    "Gemini daily quota exhausted — skipping it for the rest of this document",
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
                        provider="gemini",
                        model_name="gemini-2.5-pro",
                        processing_time_ms=duration_ms,
                        confidence=0.0,
                        retry_count=0,
                        error_message=f"Daily quota exhausted: {e}",
                    ),
                    confidence_score=0.0,
                    requires_manual_review=True,
                    review_reason="Gemini daily quota exhausted — falling back to other OCR providers",
                )

            self.logger.error(
                "Gemini Vision OCR failed after retries",
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
                    provider="gemini",
                    model_name="gemini-2.5-pro",
                    processing_time_ms=duration_ms,
                    confidence=0.0,
                    retry_count=3,
                    error_message=str(e),
                ),
                confidence_score=0.0,
                requires_manual_review=True,
                review_reason=f"OCR failed after retries: {str(e)}",
            )

    def _call_gemini_with_retry(self, img: Image.Image, page_number: int) -> tuple[dict, int]:
        """
        Call Gemini Vision OCR with up to 3 attempts (exponential backoff) to
        absorb transient API/rate-limit errors. Returns (result_dict, attempts_used - 1).
        """
        attempts = {"count": 0}

        @_ocr_retry
        def _call() -> dict:
            attempts["count"] += 1
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()

            return loop.run_until_complete(self.vision_service.perform_ocr(img, page_number))

        result = _call()
        return result, attempts["count"] - 1

    def supports_handwriting(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "Gemini Vision"
