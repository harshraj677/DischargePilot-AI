"""
OCR Safety Validator

Validates OCR results against safety requirements:
1. Confidence thresholds
2. Handwritten content flagging
3. Uncertain content review
4. Clinical keyword confidence checks
5. Never present uncertain content as confirmed
"""
from enum import Enum
from typing import Optional, List
from dataclasses import dataclass

from app.ocr.models import OCRResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SafetyLevel(str, Enum):
    """Safety level assessment for OCR result"""
    SAFE = "safe"  # Can be used directly
    CONDITIONAL = "conditional"  # Can be used with review flag
    UNSAFE = "unsafe"  # Should not be used without manual review


@dataclass
class SafetyAssessment:
    """Assessment result for OCR content"""
    level: SafetyLevel
    confidence_score: float
    should_require_review: bool
    safety_issues: List[str]
    recommendations: List[str]


class OCRSafetyValidator:
    """
    Validates OCR results for clinical safety.
    """
    
    # Confidence thresholds for different content types
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    MEDIUM_CONFIDENCE_THRESHOLD = 0.70
    LOW_CONFIDENCE_THRESHOLD = 0.60
    
    # Clinical content that requires higher confidence
    CRITICAL_KEYWORDS = [
        "contraindication", "allergy", "adverse reaction",
        "drug interaction", "dangerous", "fatal", "lethal",
        "do not", "stop medication", "discontinue",
    ]
    
    # Handwriting confidence requirements
    HANDWRITING_SAFE_CONFIDENCE = 0.75
    
    def __init__(self):
        self.logger = logger
    
    def assess_safety(
        self,
        ocr_result: OCRResult,
    ) -> SafetyAssessment:
        """
        Assess safety of OCR result for clinical use.
        
        Args:
            ocr_result: OCR result to assess
        
        Returns:
            SafetyAssessment with level and recommendations
        """
        issues = []
        recommendations = []
        confidence = ocr_result.confidence_score
        should_review = False
        level = SafetyLevel.SAFE
        
        # Check 1: Overall confidence
        if confidence < self.LOW_CONFIDENCE_THRESHOLD:
            issues.append(
                f"Low OCR confidence: {confidence:.1%} < {self.LOW_CONFIDENCE_THRESHOLD:.0%}"
            )
            recommendations.append("Require manual review before clinical use")
            should_review = True
            level = SafetyLevel.UNSAFE
        
        elif confidence < self.MEDIUM_CONFIDENCE_THRESHOLD:
            issues.append(
                f"Medium OCR confidence: {confidence:.1%} "
                f"({self.LOW_CONFIDENCE_THRESHOLD:.0%}-{self.MEDIUM_CONFIDENCE_THRESHOLD:.0%})"
            )
            recommendations.append("Flag for review if contains clinical keywords")
            should_review = True
            level = SafetyLevel.CONDITIONAL
        
        # Check 2: Handwritten content
        if (
            ocr_result.page_classification.handwriting
            and ocr_result.page_classification.handwriting.is_handwritten
        ):
            hw_confidence = ocr_result.page_classification.handwriting.confidence
            if hw_confidence < self.HANDWRITING_SAFE_CONFIDENCE:
                issues.append(
                    f"Handwritten content with low confidence: {hw_confidence:.1%}"
                )
                recommendations.append(
                    "Manual review required for all handwritten content"
                )
                should_review = True
                level = SafetyLevel.CONDITIONAL
        
        # Check 3: Clinical content
        text_lower = ocr_result.extracted_text.lower()
        
        has_medication = ocr_result.contains_medication_names
        has_diagnosis = ocr_result.contains_diagnosis_terms
        has_critical_keywords = any(
            keyword in text_lower for keyword in self.CRITICAL_KEYWORDS
        )
        
        if has_medication and confidence < self.HIGH_CONFIDENCE_THRESHOLD:
            issues.append(
                "Medication information with confidence < {0:.0%}".format(
                    self.HIGH_CONFIDENCE_THRESHOLD
                )
            )
            recommendations.append(
                "Manual verification of medication names, dosages, routes"
            )
            should_review = True
            level = SafetyLevel.CONDITIONAL
        
        if has_diagnosis and confidence < self.HIGH_CONFIDENCE_THRESHOLD:
            issues.append(
                "Diagnosis information with confidence < {0:.0%}".format(
                    self.HIGH_CONFIDENCE_THRESHOLD
                )
            )
            recommendations.append("Manual verification of diagnosis codes and terms")
            should_review = True
            level = SafetyLevel.CONDITIONAL
        
        if has_critical_keywords:
            issues.append("Critical safety keywords detected in OCR text")
            recommendations.append(
                "Require manual review of critical safety information"
            )
            should_review = True
            
            if confidence < self.MEDIUM_CONFIDENCE_THRESHOLD:
                level = SafetyLevel.UNSAFE
        
        # Check 4: Uncertainty markers
        has_uncertainty = "[REQUIRES_MANUAL_REVIEW]" in ocr_result.extracted_text
        if has_uncertainty:
            issues.append("Uncertain content marked by OCR provider")
            recommendations.append(
                "Review marked uncertain sections"
            )
            should_review = True
            level = SafetyLevel.CONDITIONAL
        
        # Check 5: Already flagged by OCR result
        if ocr_result.requires_manual_review:
            issues.append("OCR result flagged for manual review by provider")
            should_review = True
            if level == SafetyLevel.SAFE:
                level = SafetyLevel.CONDITIONAL
        
        return SafetyAssessment(
            level=level,
            confidence_score=confidence,
            should_require_review=should_review,
            safety_issues=issues,
            recommendations=recommendations,
        )
    
    def validate_for_knowledge_extraction(
        self,
        ocr_result: OCRResult,
    ) -> tuple[bool, str]:
        """
        Determine if OCR result is safe for knowledge extraction.
        
        Returns:
            Tuple of (is_safe, reason)
        """
        assessment = self.assess_safety(ocr_result)
        
        if assessment.level == SafetyLevel.SAFE:
            return True, "OCR result meets safety requirements"
        
        elif assessment.level == SafetyLevel.CONDITIONAL:
            reason = (
                f"OCR result acceptable with review: {', '.join(assessment.safety_issues)}"
            )
            return True, reason
        
        else:  # UNSAFE
            reason = (
                f"OCR result not suitable for direct use: {', '.join(assessment.safety_issues)}"
            )
            return False, reason
    
    def create_review_report(
        self,
        ocr_result: OCRResult,
    ) -> str:
        """
        Create a detailed safety review report.
        
        Args:
            ocr_result: OCR result to review
        
        Returns:
            Formatted review report
        """
        assessment = self.assess_safety(ocr_result)
        
        report_parts = [
            "=" * 60,
            "OCR SAFETY ASSESSMENT REPORT",
            "=" * 60,
            "",
            f"Document ID: {ocr_result.document_id}",
            f"Page Number: {ocr_result.page_number}",
            f"OCR Provider: {ocr_result.metadata.provider}",
            f"Extraction Method: {ocr_result.metadata.provider}",
            "",
            f"Safety Level: {assessment.level.value.upper()}",
            f"OCR Confidence: {assessment.confidence_score:.1%}",
            f"Requires Manual Review: {'YES' if assessment.should_require_review else 'NO'}",
            "",
        ]
        
        if assessment.safety_issues:
            report_parts.append("SAFETY ISSUES:")
            for issue in assessment.safety_issues:
                report_parts.append(f"  • {issue}")
            report_parts.append("")
        
        if assessment.recommendations:
            report_parts.append("RECOMMENDATIONS:")
            for rec in assessment.recommendations:
                report_parts.append(f"  • {rec}")
            report_parts.append("")
        
        # Add clinical content indicators
        report_parts.append("CLINICAL CONTENT DETECTED:")
        report_parts.append(
            f"  • Medication: {'YES' if ocr_result.contains_medication_names else 'NO'}"
        )
        report_parts.append(
            f"  • Diagnosis: {'YES' if ocr_result.contains_diagnosis_terms else 'NO'}"
        )
        report_parts.append(
            f"  • Patient ID: {'YES' if ocr_result.contains_patient_identifiers else 'NO'}"
        )
        report_parts.append("")
        
        # Add page classification
        report_parts.append("PAGE CLASSIFICATION:")
        report_parts.append(
            f"  • Type: {ocr_result.page_classification.page_type.value}"
        )
        report_parts.append(
            f"  • Classification Confidence: {ocr_result.page_classification.confidence:.1%}"
        )
        
        if ocr_result.page_classification.handwriting:
            hw = ocr_result.page_classification.handwriting
            report_parts.append(f"  • Handwriting Detected: YES ({hw.confidence:.1%})")
            report_parts.append(f"  • Handwriting %: {hw.handwriting_percentage:.0%}")
        
        report_parts.append("")
        report_parts.append("EXTRACTED TEXT SAMPLE (first 500 chars):")
        report_parts.append("-" * 60)
        sample = ocr_result.extracted_text[:500]
        if len(ocr_result.extracted_text) > 500:
            sample += "\n... (truncated)"
        report_parts.append(sample)
        report_parts.append("=" * 60)
        
        return "\n".join(report_parts)
