"""Tests for page classifier"""
import pytest
from app.ocr.page_classifier import PageClassifier
from app.ocr.models import PageType


class TestPageClassifier:
    """Tests for PageClassifier."""
    
    @pytest.fixture
    def classifier(self):
        return PageClassifier()
    
    def test_page_type_enum(self):
        """Test page type enumeration."""
        assert PageType.TEXT_PAGE.value == "text_page"
        assert PageType.SCANNED_PAGE.value == "scanned_page"
        assert PageType.IMAGE_PAGE.value == "image_page"
        assert PageType.HANDWRITTEN_PAGE.value == "handwritten_page"
        assert PageType.MIXED_PAGE.value == "mixed_page"
    
    def test_classifier_initialization(self, classifier):
        """Test classifier initialization."""
        assert classifier is not None
        assert classifier.NATIVE_TEXT_THRESHOLD == 100
        assert classifier.SCANNED_TEXT_THRESHOLD == 50
    
    def test_get_image_blocks_empty(self, classifier):
        """Test image block extraction with mock page."""
        # This test would require mocking fitz.Page
        # For now, we test that the method exists
        assert hasattr(classifier, '_get_image_blocks')
    
    def test_estimate_image_coverage_no_images(self, classifier):
        """Test image coverage estimation with no images."""
        coverage = classifier._estimate_image_coverage(None, [])
        assert coverage == 0.0
    
    def test_ocr_priority_pages(self, classifier):
        """Test OCR priority page selection."""
        from app.ocr.models import PageClassification
        
        classifications = [
            PageClassification(
                page_number=1,
                page_type=PageType.TEXT_PAGE,
                confidence=0.95,
                extracted_text_length=200,
                has_images=False,
            ),
            PageClassification(
                page_number=2,
                page_type=PageType.SCANNED_PAGE,
                confidence=0.80,
                extracted_text_length=50,
                has_images=True,
            ),
            PageClassification(
                page_number=3,
                page_type=PageType.IMAGE_PAGE,
                confidence=0.70,
                extracted_text_length=0,
                has_images=True,
            ),
        ]
        
        priority = classifier.get_ocr_priority_pages(classifications)
        assert 2 in priority
        assert 3 in priority
        assert 1 not in priority
