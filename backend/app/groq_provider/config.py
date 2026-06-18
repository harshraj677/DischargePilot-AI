"""
Groq Configuration Module

Manages Groq API configuration, model selection, and prompts for the
clinical extraction and vision/OCR pipeline (primary AI provider).
"""

import os
from typing import Optional

from app.config import settings


class GroqConfig:
    """Groq API configuration"""

    # API Configuration — resolved from settings/.env, falling back to the
    # process environment
    API_KEY: Optional[str] = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")

    # Text/reasoning model — used by the agent loop, extraction engine,
    # summary generator, and learning system. Override via GROQ_MODEL.
    TEXT_MODEL: str = settings.GROQ_MODEL or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Vision/OCR model — Groq's Llama 4 Scout/Maverick models accept image
    # input via the same chat completions image_url format. Override via
    # GROQ_VISION_MODEL.
    VISION_MODEL: str = settings.GROQ_VISION_MODEL or os.getenv(
        "GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"
    )

    MAX_OUTPUT_TOKENS: int = 4096

    # Retry/backoff for text/agent calls (vision OCR has its own retry in
    # app/ocr/providers/groq.py)
    MAX_RETRIES: int = settings.GROQ_MAX_RETRIES
    RETRY_BASE_DELAY: float = settings.GROQ_RETRY_BASE_DELAY

    # Vision OCR Prompt — Groq has no guaranteed structured-output schema
    # enforcement like Gemini's response_schema, so the prompt explicitly
    # spells out the JSON shape and app/groq_provider/vision.py validates it
    # manually.
    VISION_OCR_PROMPT = """You are a medical OCR specialist. Transcribe all text from this clinical document image exactly as written.

RULES:
1. Transcribe ONLY what you can clearly read into extracted_text — never guess or fabricate text. Wrap any illegible word or phrase as [UNCLEAR: best guess] and add a short description of each one to unclear_sections.
2. Preserve the original structure and line breaks (diagnoses, medications, allergies, procedures, labs, notes).
3. Set handwriting_detected and handwriting_percentage based on how much of the page is handwritten.
4. Set confidence to your overall confidence (0.0-1.0) that the transcription is accurate and complete.
5. Set requires_review to true whenever confidence is low, content is illegible, or handwriting is present.

Prioritize patient safety: when text is genuinely hard to read, give a lower confidence score and list it in unclear_sections rather than guessing.

Respond with ONLY a JSON object matching this exact schema (no markdown fences, no extra text):
{"extracted_text": "string", "confidence": 0.0, "handwriting_detected": false, "handwriting_percentage": 0.0, "unclear_sections": ["string"], "requires_review": false}"""

    @staticmethod
    def validate() -> bool:
        """Validate Groq configuration"""
        if not GroqConfig.API_KEY:
            raise ValueError("GROQ_API_KEY environment variable not set")
        return True

    @staticmethod
    def get_vision_model() -> str:
        """Get configured vision model"""
        return GroqConfig.VISION_MODEL
