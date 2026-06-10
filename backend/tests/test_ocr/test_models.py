"""Tests for OCR models"""
import pytest
from datetime import datetime
from app.ocr.models import (
    PageType,
    OCRResult,
    PageClassification,
    OCRMetadata,
    HandwritingDetection,
)


class TestPageClassification:
    """Tests for PageClassification model."""
    
    def test_page_classification_creation(self):
        """Test creating a PageClassification."""
        classification = PageClassification(
            page_number=1,
            page_type=PageType.SCANNED_PAGE,
            confidence=0.85,
            extracted_text_length=100,
            has_images=True,
        )
        
        assert classification.page_number == 1
        assert classification.page_type == PageType.SCANNED_PAGE
        assert classification.confidence == 0.85
        assert classification.extracted_text_length == 100
        assert classification.has_images is True
    
    def test_handwriting_detection(self):
        """Test HandwritingDetection model."""
        hw = HandwritingDetection(
            is_handwritten=True,
            confidence=0.75,
            handwriting_percentage=0.5,
            requires_review=True,
        )
        
        assert hw.is_handwritten is True
        assert hw.confidence == 0.75
        assert hw.handwriting_percentage == 0.5
        assert hw.requires_review is True


class TestOCRResult:
    """Tests for OCRResult model."""
    
    def test_ocr_result_creation(self):
        """Test creating an OCRResult."""
        classification = PageClassification(
            page_number=1,
            page_type=PageType.SCANNED_PAGE,
            confidence=0.85,
            extracted_text_length=100,
            has_images=True,
        )
        
        metadata = OCRMetadata(
            provider="claude",
            model_name="claude-3-sonnet",
            processing_time_ms=1500.0,
            confidence=0.88,
        )
        
        result = OCRResult(
            document_id="doc-123",
            page_number=1,
            extracted_text="Sample text from OCR",
            page_classification=classification,
            metadata=metadata,
            confidence_score=0.88,
        )
        
        assert result.document_id == "doc-123"
        assert result.page_number == 1
        assert result.extracted_text == "Sample text from OCR"
        assert result.confidence_score == 0.88
    
    def test_confidence_level_high(self):
        """Test high confidence level determination."""
        classification = PageClassification(
            page_number=1,
            page_type=PageType.TEXT_PAGE,
            confidence=0.95,
            extracted_text_length=200,
            has_images=False,
        )
        
        metadata = OCRMetadata(
            provider="claude",
            processing_time_ms=1000.0,
            confidence=0.9,
        )
        
        result = OCRResult(
            document_id="doc-123",
            page_number=1,
            extracted_text="Text",
            page_classification=classification,
            metadata=metadata,
            confidence_score=0.9,
        )
        
        assert result.is_high_confidence()
        assert not result.is_medium_confidence()
        assert not result.is_low_confidence()
    
    def test_confidence_level_medium(self):
        """Test medium confidence level determination."""
        classification = PageClassification(
            page_number=1,
            page_type=PageType.SCANNED_PAGE,
            confidence=0.80,
            extracted_text_length=100,
            has_images=True,
        )
        
        metadata = OCRMetadata(
            provider="easyocr",
            processing_time_ms=800.0,
            confidence=0.72,
        )
        
        result = OCRResult(
            document_id="doc-123",
            page_number=1,
            extracted_text="Text",
            page_classification=classification,
            metadata=metadata,
            confidence_score=0.72,
        )
        
        assert not result.is_high_confidence()
        assert result.is_medium_confidence()
        assert not result.is_low_confidence()
    
    def test_confidence_level_low(self):
        """Test low confidence level determination."""
        classification = PageClassification(
            page_number=1,
            page_type=PageType.HANDWRITTEN_PAGE,
            confidence=0.60,
            extracted_text_length=50,
            has_images=True,
            handwriting=HandwritingDetection(
                is_handwritten=True,
                confidence=0.55,
                handwriting_percentage=0.9,
                requires_review=True,
            ),
        )
        
        metadata = OCRMetadata(
            provider="tesseract",
            processing_time_ms=600.0,
            confidence=0.55,
        )
        
        result = OCRResult(
            document_id="doc-123",
            page_number=1,
            extracted_text="Text",
            page_classification=classification,
            metadata=metadata,
            confidence_score=0.55,
        )
        
        assert not result.is_high_confidence()
        assert not result.is_medium_confidence()
        assert result.is_low_confidence()
    
    def test_ocr_result_with_clinical_content(self):
        """Test OCR result with clinical content flags."""
        classification = PageClassification(
            page_number=1,
            page_type=PageType.SCANNED_PAGE,
            confidence=0.85,
            extracted_text_length=100,
            has_images=True,
        )
        
        metadata = OCRMetadata(
            provider="claude",
            processing_time_ms=1000.0,
            confidence=0.88,
        )
        
        result = OCRResult(
            document_id="doc-123",
            page_number=1,
            extracted_text="Aspirin 500mg, Diagnosis: Hypertension",
            page_classification=classification,
            metadata=metadata,
            confidence_score=0.88,
            contains_medication_names=True,
            contains_diagnosis_terms=True,
        )
        
        assert result.contains_medication_names is True
        assert result.contains_diagnosis_terms is True
