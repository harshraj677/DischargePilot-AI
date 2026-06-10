"""Tests for OCR safety validator"""
import pytest
from app.ocr.safety_validator import (
    OCRSafetyValidator,
    SafetyLevel,
)
from app.ocr.models import (
    OCRResult,
    PageClassification,
    OCRMetadata,
    PageType,
)


class TestOCRSafetyValidator:
    """Tests for OCRSafetyValidator."""
    
    @pytest.fixture
    def validator(self):
        return OCRSafetyValidator()
    
    @pytest.fixture
    def safe_ocr_result(self):
        """Create a high-confidence OCR result."""
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
            confidence=0.92,
        )
        
        return OCRResult(
            document_id="doc-123",
            page_number=1,
            extracted_text="Normal patient presentation with stable vitals.",
            page_classification=classification,
            metadata=metadata,
            confidence_score=0.92,
        )
    
    @pytest.fixture
    def low_confidence_result(self):
        """Create a low-confidence OCR result."""
        classification = PageClassification(
            page_number=2,
            page_type=PageType.HANDWRITTEN_PAGE,
            confidence=0.55,
            extracted_text_length=50,
            has_images=True,
        )
        
        metadata = OCRMetadata(
            provider="tesseract",
            processing_time_ms=600.0,
            confidence=0.50,
        )
        
        return OCRResult(
            document_id="doc-123",
            page_number=2,
            extracted_text="[UNCERTAIN: possibly hand-written notes]",
            page_classification=classification,
            metadata=metadata,
            confidence_score=0.50,
            requires_manual_review=True,
        )
    
    def test_validator_initialization(self, validator):
        """Test validator initialization."""
        assert validator is not None
        assert validator.HIGH_CONFIDENCE_THRESHOLD == 0.85
        assert validator.MEDIUM_CONFIDENCE_THRESHOLD == 0.70
        assert validator.LOW_CONFIDENCE_THRESHOLD == 0.60
    
    def test_safe_result_assessment(self, validator, safe_ocr_result):
        """Test assessment of safe OCR result."""
        assessment = validator.assess_safety(safe_ocr_result)
        
        assert assessment.level == SafetyLevel.SAFE
        assert assessment.confidence_score == 0.92
        assert assessment.should_require_review is False
        assert len(assessment.safety_issues) == 0
    
    def test_low_confidence_assessment(self, validator, low_confidence_result):
        """Test assessment of low confidence result."""
        assessment = validator.assess_safety(low_confidence_result)
        
        assert assessment.level == SafetyLevel.UNSAFE
        assert assessment.confidence_score == 0.50
        assert assessment.should_require_review is True
        assert len(assessment.safety_issues) > 0
    
    def test_medication_content_assessment(self, validator):
        """Test assessment with medication content."""
        classification = PageClassification(
            page_number=1,
            page_type=PageType.SCANNED_PAGE,
            confidence=0.75,
            extracted_text_length=100,
            has_images=True,
        )
        
        metadata = OCRMetadata(
            provider="claude",
            processing_time_ms=1000.0,
            confidence=0.76,
        )
        
        result = OCRResult(
            document_id="doc-123",
            page_number=1,
            extracted_text="Aspirin 500mg twice daily, Lisinopril 10mg once daily",
            page_classification=classification,
            metadata=metadata,
            confidence_score=0.76,
            contains_medication_names=True,
        )
        
        assessment = validator.assess_safety(result)
        
        # Medication with medium confidence should require review
        assert assessment.should_require_review is True
        assert assessment.level == SafetyLevel.CONDITIONAL
    
    def test_critical_keyword_assessment(self, validator):
        """Test assessment with critical safety keywords."""
        classification = PageClassification(
            page_number=1,
            page_type=PageType.SCANNED_PAGE,
            confidence=0.65,
            extracted_text_length=100,
            has_images=True,
        )
        
        metadata = OCRMetadata(
            provider="easyocr",
            processing_time_ms=800.0,
            confidence=0.65,
        )
        
        result = OCRResult(
            document_id="doc-123",
            page_number=1,
            extracted_text="CONTRAINDICATION: Do not administer aspirin if allergy detected",
            page_classification=classification,
            metadata=metadata,
            confidence_score=0.65,
        )
        
        assessment = validator.assess_safety(result)
        
        # Critical keywords with medium confidence should trigger conditional level
        assert assessment.should_require_review is True
        assert assessment.level in (SafetyLevel.CONDITIONAL, SafetyLevel.UNSAFE)
    
    def test_validation_for_knowledge_extraction(
        self,
        validator,
        safe_ocr_result,
    ):
        """Test validation for knowledge extraction."""
        is_safe, reason = validator.validate_for_knowledge_extraction(
            safe_ocr_result
        )
        
        assert is_safe is True
        assert "safety requirements" in reason.lower()
    
    def test_review_report_generation(
        self,
        validator,
        low_confidence_result,
    ):
        """Test review report generation."""
        report = validator.create_review_report(low_confidence_result)
        
        assert "OCR SAFETY ASSESSMENT REPORT" in report
        assert "UNSAFE" in report
        assert low_confidence_result.document_id in report
        assert str(low_confidence_result.page_number) in report
    
    def test_threshold_constants(self, validator):
        """Test threshold constants."""
        assert validator.HIGH_CONFIDENCE_THRESHOLD > validator.MEDIUM_CONFIDENCE_THRESHOLD
        assert validator.MEDIUM_CONFIDENCE_THRESHOLD > validator.LOW_CONFIDENCE_THRESHOLD
        assert validator.HIGH_CONFIDENCE_THRESHOLD == 0.85
        assert validator.MEDIUM_CONFIDENCE_THRESHOLD == 0.70
        assert validator.LOW_CONFIDENCE_THRESHOLD == 0.60
