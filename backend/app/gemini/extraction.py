"""
Gemini Clinical Extractor

Performs structured clinical information extraction from documents with
safety validation, confidence scoring, and evidence preservation.
"""

import json
import logging
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field

from .client import get_gemini_client
from .config import GeminiConfig

logger = logging.getLogger(__name__)

class ExtractionSource(str, Enum):
    """Source of extracted data"""
    NATIVE_PDF = "native_pdf"
    SCANNED_PDF = "scanned_pdf"
    IMAGE_UPLOAD = "image_upload"
    VISION_OCR = "vision_ocr"

class ConfidenceLevel(str, Enum):
    """Confidence levels for extracted data"""
    HIGH = "high"        # >= 0.85
    MEDIUM = "medium"    # 0.60-0.85
    LOW = "low"          # < 0.60

class Diagnosis(BaseModel):
    """Extracted diagnosis"""
    name: str
    icd_code: Optional[str] = None
    confidence: float = Field(..., ge=0, le=1)
    evidence: Optional[str] = None
    requires_review: bool = False

class Medication(BaseModel):
    """Extracted medication"""
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    confidence: float = Field(..., ge=0, le=1)
    evidence: Optional[str] = None
    requires_review: bool = False

class Allergy(BaseModel):
    """Extracted allergy"""
    substance: str
    reaction: Optional[str] = None
    severity: Optional[str] = None  # mild, moderate, severe
    confidence: float = Field(..., ge=0, le=1)
    evidence: Optional[str] = None
    requires_review: bool = False

class Procedure(BaseModel):
    """Extracted procedure"""
    name: str
    date: Optional[str] = None
    confidence: float = Field(..., ge=0, le=1)
    evidence: Optional[str] = None
    requires_review: bool = False

class LabResult(BaseModel):
    """Extracted lab result"""
    test_name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    date: Optional[str] = None
    confidence: float = Field(..., ge=0, le=1)
    evidence: Optional[str] = None
    requires_review: bool = False

class ExtractedClinicalData(BaseModel):
    """Container for all extracted clinical data"""
    diagnoses: List[Diagnosis] = []
    medications: List[Medication] = []
    allergies: List[Allergy] = []
    procedures: List[Procedure] = []
    lab_results: List[LabResult] = []
    clinical_notes: Optional[str] = None
    follow_up_instructions: Optional[str] = None
    pending_results: Optional[str] = None
    
    # Metadata
    source: ExtractionSource
    extraction_confidence: float = Field(..., ge=0, le=1)
    requires_review: bool = False
    review_reasons: List[str] = []
    
    # Safety flags
    has_fabricated_content: bool = False
    has_uncertain_sections: bool = False
    evidence_chain_complete: bool = True

class GeminiClinicalExtractor:
    """
    Performs structured clinical extraction with safety validation.
    
    Features:
    - Structured extraction to Pydantic models
    - Confidence scoring
    - Evidence preservation
    - Safety validation
    - Low-confidence flagging
    """
    
    # Clinical keywords requiring higher confidence
    CRITICAL_KEYWORDS = {
        'contraindication', 'allergy', 'adverse', 'reaction',
        'drug_interaction', 'dangerous', 'fatal', 'lethal',
        'do_not', 'stop', 'discontinue', 'caution', 'warning'
    }
    
    def __init__(self):
        """Initialize clinical extractor"""
        self.client = get_gemini_client()
    
    async def extract(
        self,
        text: str,
        source: ExtractionSource = ExtractionSource.NATIVE_PDF,
        context: Optional[str] = None,
    ) -> ExtractedClinicalData:
        """
        Extract clinical data from text with safety validation.
        
        Args:
            text: Document text
            source: Source of the text
            context: Optional additional context
            
        Returns:
            ExtractedClinicalData with all structured information
        """
        try:
            # Build extraction prompt
            prompt = self._build_extraction_prompt(text, context)
            
            # Generate extraction
            response = await self.client.generate_content(
                prompt=prompt,
                model_type="text",
                config=GeminiConfig.GENERATION_CONFIG,
            )
            
            # Parse response
            data = self._parse_extraction_response(response, source)
            
            # Validate extraction
            data = self._validate_extraction(data)
            
            # Calculate confidence
            data.extraction_confidence = self._calculate_confidence(data)
            data.requires_review = data.extraction_confidence < 0.75
            
            logger.info(f"Extraction complete - confidence: {data.extraction_confidence:.2f}, "
                       f"requires_review: {data.requires_review}")
            
            return data
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            # Return minimal data with error flag
            return ExtractedClinicalData(
                source=source,
                extraction_confidence=0.0,
                requires_review=True,
                review_reasons=["Extraction failed: " + str(e)],
                has_fabricated_content=True,
            )
    
    def _build_extraction_prompt(self, text: str, context: Optional[str]) -> str:
        """Build extraction prompt"""
        base_prompt = GeminiConfig.CLINICAL_EXTRACTION_PROMPT
        
        context_section = ""
        if context:
            context_section = f"\n\nContext: {context}"
        
        document_section = f"\n\nDocument:\n{text[:5000]}"  # Limit to 5000 chars
        
        return f"{base_prompt}{context_section}{document_section}\n\nExtract and return as JSON only."
    
    def _parse_extraction_response(
        self,
        response: str,
        source: ExtractionSource
    ) -> ExtractedClinicalData:
        """Parse extraction response into structured data"""
        try:
            # Extract JSON from response
            data_dict = self._parse_json_from_response(response)
            
            # Build diagnosis list
            diagnoses = []
            for d in data_dict.get('diagnoses', []):
                diagnoses.append(Diagnosis(
                    name=d.get('name', ''),
                    icd_code=d.get('icd_code'),
                    confidence=d.get('confidence', 0.5),
                    evidence=d.get('evidence'),
                    requires_review=d.get('confidence', 0.5) < 0.75,
                ))
            
            # Build medication list
            medications = []
            for m in data_dict.get('medications', []):
                medications.append(Medication(
                    name=m.get('name', ''),
                    dosage=m.get('dosage'),
                    frequency=m.get('frequency'),
                    route=m.get('route'),
                    confidence=m.get('confidence', 0.5),
                    evidence=m.get('evidence'),
                    requires_review=m.get('confidence', 0.5) < 0.75,
                ))
            
            # Build allergy list
            allergies = []
            for a in data_dict.get('allergies', []):
                allergies.append(Allergy(
                    substance=a.get('substance', ''),
                    reaction=a.get('reaction'),
                    severity=a.get('severity'),
                    confidence=a.get('confidence', 0.5),
                    evidence=a.get('evidence'),
                    requires_review=a.get('confidence', 0.5) < 0.75,
                ))
            
            # Build procedure list
            procedures = []
            for p in data_dict.get('procedures', []):
                procedures.append(Procedure(
                    name=p.get('name', ''),
                    date=p.get('date'),
                    confidence=p.get('confidence', 0.5),
                    evidence=p.get('evidence'),
                    requires_review=p.get('confidence', 0.5) < 0.75,
                ))
            
            # Build lab results list
            labs = []
            for l in data_dict.get('lab_results', []):
                labs.append(LabResult(
                    test_name=l.get('test_name', ''),
                    value=l.get('value'),
                    unit=l.get('unit'),
                    reference_range=l.get('reference_range'),
                    date=l.get('date'),
                    confidence=l.get('confidence', 0.5),
                    evidence=l.get('evidence'),
                    requires_review=l.get('confidence', 0.5) < 0.75,
                ))
            
            return ExtractedClinicalData(
                diagnoses=diagnoses,
                medications=medications,
                allergies=allergies,
                procedures=procedures,
                lab_results=labs,
                clinical_notes=data_dict.get('clinical_notes'),
                follow_up_instructions=data_dict.get('follow_up_instructions'),
                pending_results=data_dict.get('pending_results'),
                source=source,
                extraction_confidence=data_dict.get('overall_confidence', 0.5),
                has_uncertain_sections='[UNCLEAR]' in str(response) or '[LOW_CONFIDENCE]' in str(response),
            )
        except Exception as e:
            logger.error(f"Failed to parse extraction response: {e}")
            return ExtractedClinicalData(
                source=source,
                extraction_confidence=0.0,
                requires_review=True,
                review_reasons=["Parse error: " + str(e)],
            )
    
    def _parse_json_from_response(self, response: str) -> Dict[str, Any]:
        """Extract JSON from response"""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            try:
                start = response.find('{')
                end = response.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(response[start:end])
            except:
                pass
            
            logger.warning("Could not parse extraction response as JSON")
            return {}
    
    def _validate_extraction(self, data: ExtractedClinicalData) -> ExtractedClinicalData:
        """Validate extracted data for safety"""
        review_reasons = []
        
        # Flag low-confidence critical information
        for d in data.diagnoses:
            if self._is_critical(d.name) and d.confidence < 0.85:
                d.requires_review = True
                review_reasons.append(f"Low confidence diagnosis: {d.name}")
        
        for m in data.medications:
            if self._is_critical(m.name) and m.confidence < 0.85:
                m.requires_review = True
                review_reasons.append(f"Low confidence medication: {m.name}")
        
        for a in data.allergies:
            if a.confidence < 0.85:
                a.requires_review = True
                review_reasons.append(f"Allergy requires review: {a.substance}")
        
        # Check for fabricated content
        empty_evidence = sum(1 for d in data.diagnoses if not d.evidence)
        if empty_evidence > len(data.diagnoses) * 0.3:
            review_reasons.append("Multiple items lack evidence references")
        
        # Flag uncertain sections
        if data.has_uncertain_sections:
            review_reasons.append("Document contains uncertain or unclear sections")
        
        data.review_reasons = review_reasons
        if review_reasons:
            data.requires_review = True
        
        return data
    
    def _calculate_confidence(self, data: ExtractedClinicalData) -> float:
        """Calculate overall extraction confidence"""
        if not data.diagnoses and not data.medications and not data.allergies:
            return 0.3  # Very low confidence if nothing extracted
        
        scores = []
        
        # Diagnoses confidence
        if data.diagnoses:
            scores.append(sum(d.confidence for d in data.diagnoses) / len(data.diagnoses))
        
        # Medications confidence
        if data.medications:
            scores.append(sum(m.confidence for m in data.medications) / len(data.medications))
        
        # Allergies confidence (critical, weight higher)
        if data.allergies:
            allergy_conf = sum(a.confidence for a in data.allergies) / len(data.allergies)
            scores.append(allergy_conf * 1.2)  # Weight allergies higher
        
        # Procedures and labs
        if data.procedures:
            scores.append(sum(p.confidence for p in data.procedures) / len(data.procedures))
        
        if data.lab_results:
            scores.append(sum(l.confidence for l in data.lab_results) / len(data.lab_results))
        
        # Average all scores
        overall = sum(scores) / len(scores) if scores else 0.5
        
        # Adjust down if uncertain sections
        if data.has_uncertain_sections:
            overall *= 0.9
        
        # Clamp to 0-1
        return max(0.0, min(1.0, overall))
    
    def _is_critical(self, text: str) -> bool:
        """Check if text contains critical keywords"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.CRITICAL_KEYWORDS)
