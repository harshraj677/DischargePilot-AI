"""Tests for handwriting processor"""
import pytest
from app.ocr.handwriting_processor import HandwritingProcessor
from app.ocr.models import (
    OCRResult,
    PageClassification,
    OCRMetadata,
    PageType,
    HandwritingDetection,
)


class TestHandwritingProcessor:
    """Tests for HandwritingProcessor."""
    
    @pytest.fixture
    def processor(self):
        return HandwritingProcessor()
    
    def test_processor_initialization(self, processor):
        """Test processor initialization."""
        assert processor is not None
        assert processor.HIGH_CONFIDENCE_THRESHOLD == 0.85
        assert processor.MEDIUM_CONFIDENCE_THRESHOLD == 0.60
    
    def test_sanitize_uncertain_content(self, processor):
        """Test sanitization of uncertain content."""
        text = "Patient notes: [UNCERTAIN: maybe aspirin]\nClear text here"
        
        sanitized = processor._sanitize_uncertain_content(text)
        
        assert "[REQUIRES_MANUAL_REVIEW]" in sanitized
        assert "[UNCERTAIN" in sanitized
    
    def test_score_handwriting_confidence_claude(self, processor):
        """Test confidence scoring for Claude-extracted handwriting."""
        confidence = processor.score_handwriting_confidence(
            text="Some text",
            provider="claude",
            has_uncertainty_markers=False,
        )
        
        assert 0.0 <= confidence <= 1.0
        # Claude should score higher
        assert confidence > 0.60
    
    def test_score_handwriting_confidence_with_uncertainty(self, processor):
        """Test confidence scoring with uncertainty markers."""
        text = "[REQUIRES_MANUAL_REVIEW] Some content\n" * 5
        
        confidence = processor.score_handwriting_confidence(
            text=text,
            provider="claude",
            has_uncertainty_markers=True,
        )
        
        # Should be penalized for uncertainty
        assert confidence < 0.70
    
    def test_requires_clinical_review_low_confidence(self, processor):
        """Test clinical review requirement with low confidence."""
        requires_review = processor.requires_clinical_review(
            text="Patient admitted with fever",
            confidence=0.50,
            page_type="handwritten_page",
        )
        
        assert requires_review is True
    
    def test_requires_clinical_review_with_medication(self, processor):
        """Test clinical review requirement with medication content."""
        requires_review = processor.requires_clinical_review(
            text="Aspirin 500mg prescribed",
            confidence=0.75,
            page_type="handwritten_page",
        )
        
        assert requires_review is True
    
    def test_requires_clinical_review_high_confidence_normal_content(self, processor):
        """Test no review required for high confidence normal content."""
        requires_review = processor.requires_clinical_review(
            text="Patient in stable condition",
            confidence=0.90,
            page_type="text_page",
        )
        
        assert requires_review is False
    
    def test_create_review_note(self, processor):
        """Test review note creation."""
        note = processor.create_review_note(
            text="Aspirin 500mg twice daily",
            confidence=0.72,
            contains_medication=True,
            contains_diagnosis=False,
        )
        
        assert "HANDWRITING EXTRACTION REVIEW" in note
        assert "MEDICATION INFORMATION" in note
        assert "Aspirin 500mg" in note
    
    def test_process_ocr_result_with_handwriting(self, processor):
        """Test processing OCR result with handwritten content."""
        hw_detection = HandwritingDetection(
            is_handwritten=True,
            confidence=0.70,
            handwriting_percentage=0.8,
            requires_review=True,
        )
        
        classification = PageClassification(
            page_number=1,
            page_type=PageType.HANDWRITTEN_PAGE,
            confidence=0.70,
            extracted_text_length=100,
            has_images=True,
            handwriting=hw_detection,
        )
        
        metadata = OCRMetadata(
            provider="claude",
            processing_time_ms=1000.0,
            confidence=0.72,
        )
        
        result = OCRResult(
            document_id="doc-123",
            page_number=1,
            extracted_text="Patient notes in handwriting",
            page_classification=classification,
            metadata=metadata,
            confidence_score=0.72,
        )
        
        cleaned_text, conf, requires_review = processor.process_ocr_result(result)
        
        assert cleaned_text is not None
        assert 0.0 <= conf <= 1.0
        assert requires_review is True
    
    def test_create_handwriting_evidence(self, processor):
        """Test evidence creation for handwritten content."""
        classification = PageClassification(
            page_number=1,
            page_type=PageType.HANDWRITTEN_PAGE,
            confidence=0.70,
            extracted_text_length=100,
            has_images=True,
        )
        
        metadata = OCRMetadata(
            provider="claude",
            processing_time_ms=1000.0,
            confidence=0.72,
        )
        
        result = OCRResult(
            document_id="doc-123",
            page_number=1,
            extracted_text="Handwritten text",
            page_classification=classification,
            metadata=metadata,
            confidence_score=0.72,
        )
        
        evidence = processor.create_handwriting_evidence(
            ocr_result=result,
            handwriting_confidence=0.70,
            requires_review=True,
        )
        
        assert evidence["extraction_method"] == "ocr_handwriting"
        assert evidence["ocr_provider"] == "claude"
        assert evidence["requires_review"] is True
        assert evidence["confidence"] == 0.70
