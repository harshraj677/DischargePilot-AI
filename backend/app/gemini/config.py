"""
Google Gemini Configuration Module

Manages Gemini API configuration, model selection, and system prompts.
"""

import os
from enum import Enum
from typing import Optional

from app.config import settings

class GeminiModel(str, Enum):
    """Available Gemini models"""
    # Vision models
    GEMINI_2_5_PRO = "gemini-2.5-pro"
    GEMINI_2_0_FLASH = "gemini-2.0-flash"
    GEMINI_2_0_FLASH_EXP = "gemini-2.0-flash-exp"
    GEMINI_PRO_VISION = "gemini-pro-vision"
    
    # Text models
    GEMINI_PRO = "gemini-pro"

class GeminiConfig:
    """Gemini API Configuration"""
    
    # API Configuration
    API_KEY: Optional[str] = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    API_TIMEOUT: int = 120  # seconds
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0  # seconds

    # Model Selection
    VISION_MODEL: str = settings.GEMINI_VISION_MODEL or os.getenv("GEMINI_VISION_MODEL", GeminiModel.GEMINI_2_5_PRO)
    TEXT_MODEL: str = settings.GEMINI_TEXT_MODEL or os.getenv("GEMINI_TEXT_MODEL", GeminiModel.GEMINI_2_5_PRO)
    
    # Safety Configuration
    SAFETY_SETTINGS = [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_NONE",
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_NONE",
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_NONE",
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_NONE",
        },
    ]
    
    # Generation Configuration
    GENERATION_CONFIG = {
        "temperature": 0.3,  # Lower for clinical precision
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 4096,
    }
    
    # Vision OCR Configuration
    # response_mime_type forces Gemini to emit valid JSON (no markdown fences,
    # no missing fields) — without it the model frequently omits "confidence",
    # which made every page fall back to the much slower EasyOCR pass.
    VISION_OCR_CONFIG = {
        "temperature": 0.1,  # Very low for OCR accuracy
        "top_p": 0.9,
        "top_k": 10,
        "max_output_tokens": 4096,
        "response_mime_type": "application/json",
    }
    
    # System Prompts
    CLINICAL_EXTRACTION_PROMPT = """You are a medical document analyzer. Extract clinical information from the provided document.

IMPORTANT RULES:
1. Only extract information that is explicitly stated in the document
2. Never fabricate or assume medical information
3. Mark uncertain extractions with [LOW_CONFIDENCE]
4. Preserve exact wording for critical information
5. Include page numbers and context
6. Output valid JSON only

Extract and structure:
- Diagnoses (ICD codes if available)
- Medications (with dosages, frequencies)
- Allergies (with severity levels)
- Procedures
- Lab Results (with reference ranges)
- Clinical Notes
- Follow-up Instructions
- Pending Results
- Evidence references (where found in document)

Output format: Valid JSON with key-value pairs. Never include markdown formatting."""

    VISION_OCR_PROMPT = """You are a medical OCR specialist. Transcribe all text from this clinical document image exactly as written.

RULES:
1. Transcribe ONLY what you can clearly read — never guess or fabricate text
2. Wrap any illegible word or phrase as [UNCLEAR: best guess] in extracted_text and add a short note for it to unclear_sections
3. Preserve the original structure and line breaks (diagnoses, medications, allergies, procedures, labs, notes)
4. Detect handwritten content and assess how legible it is

Respond with ONLY a JSON object — no markdown fences, no commentary — matching exactly this schema:
{
  "extracted_text": "<the full transcribed text of the page>",
  "confidence": <REQUIRED float from 0.0 to 1.0 — your overall confidence that the transcription is accurate and complete>,
  "handwriting_detected": <true|false>,
  "handwriting_percentage": <float 0-100>,
  "unclear_sections": ["<short description of each illegible or ambiguous region>"],
  "requires_review": <true|false — true when confidence is low or content is illegible>
}

The "confidence" field is REQUIRED and must be a number, not text. Prioritize patient safety: when text is genuinely hard to read, give a lower confidence score and list it in unclear_sections rather than guessing."""

    SUMMARY_GENERATION_PROMPT = """You are a clinical summary generator. Create a discharge summary from the patient's clinical data.

RULES:
1. Use only provided clinical data - NEVER fabricate
2. Mark missing information as [NOT PROVIDED]
3. For low-confidence data, mark as [PENDING VERIFICATION]
4. Structure: Demographics, Hospital Course, Diagnoses, Medications, Allergies, Procedures, Labs, Instructions, Flags
5. Include evidence references
6. Flag for clinician review any uncertain or incomplete data

Output: Clinically valid, evidence-based discharge summary. Prioritize patient safety."""

    AGENT_PLANNER_PROMPT = """You are a clinical agent planner. Analyze patient documents and generate a structured task plan.

RULES:
1. Create dependency-ordered tasks
2. Consider clinical safety requirements
3. Mark tasks requiring manual review
4. Never plan fabrication or hallucination
5. Ensure evidence traceability
6. Output: JSON task graph with dependencies

Task priority: Safety > Completeness > Optimization"""

    AGENT_REASONER_PROMPT = """You are a clinical reasoning engine. Analyze tool outputs and determine next actions.

RULES:
1. Evidence-based reasoning only
2. Flag conflicts and contradictions
3. Assess confidence levels
4. Recommend escalation if needed
5. Never reason beyond provided evidence
6. Output: JSON reasoning with confidence and recommendation"""

    @staticmethod
    def validate() -> bool:
        """Validate Gemini configuration"""
        if not GeminiConfig.API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        return True
    
    @staticmethod
    def get_vision_model() -> str:
        """Get configured vision model"""
        return GeminiConfig.VISION_MODEL
    
    @staticmethod
    def get_text_model() -> str:
        """Get configured text model"""
        return GeminiConfig.TEXT_MODEL
