"""
Tests for ClaudeVisionOCR (STEP 4 of the Gemini -> Claude migration).

Covers:
- OCR across image formats (JPEG, PNG, WEBP) — STEP 4 final-goal upload formats
- Scanned-page OCR via the OCR fallback engine (STEP 4 workflow)
- Failure handling: OCR errors never raise, they produce a low-confidence
  OCRResult flagged for manual review (STEP 7 "do not crash")
- Usage stats wiring (STEP 8: Claude OCR Status)
"""
import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.claude.client import ClaudeClient
from app.claude.config import ClaudeConfig
from app.claude.usage import get_claude_usage_stats
from app.claude.vision import ClaudeVisionService, ImageProcessingError, OCRPageExtraction
from app.ocr.fallback_engine import OCRFallbackEngine
from app.ocr.models import OCRMetadata, OCRResult, PageClassification, PageType
from app.ocr.providers.claude import ClaudeVisionOCR


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.setattr(ClaudeConfig, "API_KEY", "test-anthropic-key")
    ClaudeClient._instance = None

    stats = get_claude_usage_stats()
    for attr in ("text_requests", "vision_requests", "ocr_requests", "errors", "cache_hits", "cache_misses"):
        setattr(stats, attr, 0)
    stats.last_request_at = None
    stats.last_error = None
    stats.last_error_at = None

    yield

    ClaudeClient._instance = None


@pytest.fixture
def claude_ocr():
    with patch("app.claude.client.anthropic.Anthropic"):
        return ClaudeVisionOCR()


def _image_bytes(fmt: str) -> bytes:
    img = Image.new("RGB", (200, 100), color="white")
    buffer = io.BytesIO()
    img.save(buffer, format=fmt)
    buffer.seek(0)
    return buffer.getvalue()


def _classification(page_type: PageType = PageType.SCANNED_PAGE) -> PageClassification:
    return PageClassification(
        page_number=1,
        page_type=page_type,
        confidence=0.9,
        extracted_text_length=0,
        has_images=True,
    )


def _extraction(
    text: str = "Patient: John Doe\nMRN: 12345\nDiagnosis: Pneumonia",
    confidence: float = 0.92,
    requires_review: bool = False,
    handwriting: bool = False,
    unclear: list[str] | None = None,
) -> OCRPageExtraction:
    return OCRPageExtraction(
        extracted_text=text,
        confidence=confidence,
        handwriting_detected=handwriting,
        handwriting_percentage=0.0,
        unclear_sections=unclear or [],
        requires_review=requires_review,
    )


# ── Image format support (STEP 4: JPG, PNG, WEBP) ────────────────────────────────

class TestImageFormatSupport:
    @pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
    def test_process_image_supports_format(self, claude_ocr, fmt):
        with patch.object(claude_ocr.vision_service, "perform_ocr", return_value=_extraction()):
            result = claude_ocr.process_image(
                image_bytes=_image_bytes(fmt),
                page_number=1,
                document_id="doc-1",
                page_classification=_classification(),
            )

        assert result is not None
        assert result.extracted_text == "Patient: John Doe\nMRN: 12345\nDiagnosis: Pneumonia"
        assert result.metadata.provider == "claude"
        assert result.metadata.model_name == ClaudeConfig.VISION_MODEL


# ── Successful OCR ────────────────────────────────────────────────────────────────

class TestProcessImageSuccess:
    def test_returns_ocr_result_with_claude_metadata(self, claude_ocr):
        with patch.object(claude_ocr.vision_service, "perform_ocr", return_value=_extraction(confidence=0.88)):
            result = claude_ocr.process_image(
                image_bytes=_image_bytes("PNG"),
                page_number=2,
                document_id="doc-42",
                page_classification=_classification(),
            )

        assert result.document_id == "doc-42"
        assert result.page_number == 2
        assert result.confidence_score == 0.88
        assert result.requires_manual_review is False
        assert result.metadata.provider == "claude"

    def test_records_ocr_usage_stat(self, claude_ocr):
        with patch.object(claude_ocr.vision_service, "perform_ocr", return_value=_extraction()):
            claude_ocr.process_image(
                image_bytes=_image_bytes("PNG"),
                page_number=1,
                document_id="doc-1",
                page_classification=_classification(),
            )

        usage = get_claude_usage_stats().to_dict()
        assert usage["ocr_requests"] == 1

    def test_low_confidence_flags_for_review(self, claude_ocr):
        with patch.object(
            claude_ocr.vision_service,
            "perform_ocr",
            return_value=_extraction(confidence=0.4, requires_review=True, unclear=["dosage line"]),
        ):
            result = claude_ocr.process_image(
                image_bytes=_image_bytes("PNG"),
                page_number=1,
                document_id="doc-1",
                page_classification=_classification(),
            )

        assert result.requires_manual_review is True
        assert "Unclear sections" in result.review_reason

    def test_handwriting_detection_flags_for_review(self, claude_ocr):
        with patch.object(
            claude_ocr.vision_service,
            "perform_ocr",
            return_value=_extraction(confidence=0.7, requires_review=True, handwriting=True),
        ):
            result = claude_ocr.process_image(
                image_bytes=_image_bytes("PNG"),
                page_number=1,
                document_id="doc-1",
                page_classification=_classification(page_type=PageType.HANDWRITTEN_PAGE),
            )

        assert result.requires_manual_review is True
        assert "Handwritten" in result.review_reason

    def test_keyword_detection_flags(self, claude_ocr):
        text = "Medications: Metformin 500mg tablet. Diagnosis: Type 2 Diabetes. MRN: 12345"
        with patch.object(claude_ocr.vision_service, "perform_ocr", return_value=_extraction(text=text)):
            result = claude_ocr.process_image(
                image_bytes=_image_bytes("PNG"),
                page_number=1,
                document_id="doc-1",
                page_classification=_classification(),
            )

        assert result.contains_medication_names is True
        assert result.contains_diagnosis_terms is True
        assert result.contains_patient_identifiers is True


# ── STEP 7: failure handling — never crash ───────────────────────────────────────

class TestProcessImageFailure:
    def test_ocr_failure_returns_zero_confidence_result_not_exception(self, claude_ocr):
        with patch.object(
            claude_ocr.vision_service, "perform_ocr", side_effect=ImageProcessingError("Claude unavailable")
        ):
            result = claude_ocr.process_image(
                image_bytes=_image_bytes("PNG"),
                page_number=3,
                document_id="doc-9",
                page_classification=_classification(),
            )

        assert result is not None
        assert result.confidence_score == 0.0
        assert result.requires_manual_review is True
        assert "OCR failed after retries" in result.review_reason
        assert result.extracted_text == ""

    def test_failure_records_error_usage_stat(self, claude_ocr):
        with patch.object(
            claude_ocr.vision_service, "perform_ocr", side_effect=ImageProcessingError("Claude unavailable")
        ):
            claude_ocr.process_image(
                image_bytes=_image_bytes("PNG"),
                page_number=1,
                document_id="doc-1",
                page_classification=_classification(),
            )

        usage = get_claude_usage_stats().to_dict()
        assert usage["errors"] == 1
        assert usage["last_error"] == "Claude unavailable"


# ── Provider metadata ─────────────────────────────────────────────────────────────

class TestProviderMetadata:
    def test_supports_handwriting(self, claude_ocr):
        assert claude_ocr.supports_handwriting() is True

    def test_provider_name(self, claude_ocr):
        assert claude_ocr.get_provider_name() == "Claude Vision"


# ── Scanned PDF workflow via OCR fallback engine (STEP 4) ────────────────────────

class TestScannedPageWorkflow:
    def test_should_run_ocr_for_scanned_page_with_no_text(self):
        with patch.object(OCRFallbackEngine, "_initialize_providers", lambda self: None):
            engine = OCRFallbackEngine.__new__(OCRFallbackEngine)
            engine.primary_provider = "claude"
            engine.fallback_providers = ["easyocr", "tesseract"]
            engine.enable_fallback = True
            engine.enable_optimization = True
            engine.providers = {}

        assert engine.should_run_ocr("", _classification(PageType.SCANNED_PAGE)) is True

    def test_should_skip_ocr_for_text_page_with_sufficient_text(self):
        with patch.object(OCRFallbackEngine, "_initialize_providers", lambda self: None):
            engine = OCRFallbackEngine.__new__(OCRFallbackEngine)
            engine.primary_provider = "claude"
            engine.fallback_providers = ["easyocr", "tesseract"]
            engine.enable_fallback = True
            engine.enable_optimization = True
            engine.providers = {}

        long_text = "Discharge summary text. " * 10
        assert engine.should_run_ocr(long_text, _classification(PageType.TEXT_PAGE)) is False

    def test_process_page_uses_claude_as_primary_provider(self, claude_ocr):
        with patch.object(OCRFallbackEngine, "_initialize_providers", lambda self: None):
            engine = OCRFallbackEngine.__new__(OCRFallbackEngine)
            engine.primary_provider = "claude"
            engine.fallback_providers = ["easyocr", "tesseract"]
            engine.enable_fallback = True
            engine.enable_optimization = True
            engine.providers = {"claude": claude_ocr}
            engine.image_extractor = MagicMock()
            engine.logger = MagicMock()

        engine.image_extractor.extract_page_image.return_value = _image_bytes("PNG")

        with patch.object(claude_ocr.vision_service, "perform_ocr", return_value=_extraction(confidence=0.9)):
            result = engine.process_page(
                page=MagicMock(),
                page_number=1,
                document_id="doc-scanned",
                native_text="",
                page_classification=_classification(PageType.SCANNED_PAGE),
            )

        assert result is not None
        assert result.selected_result.metadata.provider == "claude"
        assert result.selected_result.confidence_score == 0.9
        assert "claude" in result.selection_reason
