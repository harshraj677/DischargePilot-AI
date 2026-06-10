"""
Anthropic Claude Configuration Module

Manages Claude API configuration, model selection, and prompts for the
vision/OCR pipeline (replaces Gemini as the primary OCR provider).
"""

import os
from typing import Optional

from app.config import settings


class ClaudeConfig:
    """Anthropic Claude API configuration"""

    # API Configuration — resolved from settings/.env, falling back to the
    # process environment
    API_KEY: Optional[str] = settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")

    # Model Selection — override via ANTHROPIC_VISION_MODEL in .env
    VISION_MODEL: str = settings.ANTHROPIC_VISION_MODEL or os.getenv(
        "ANTHROPIC_VISION_MODEL", "claude-opus-4-8"
    )

    # Text/reasoning model — used by the agent loop, extraction engine,
    # summary generator, and learning system. Override via ANTHROPIC_TEXT_MODEL.
    TEXT_MODEL: str = settings.ANTHROPIC_TEXT_MODEL or os.getenv(
        "ANTHROPIC_TEXT_MODEL", "claude-sonnet-4-6"
    )

    MAX_OUTPUT_TOKENS: int = 4096

    # Retry/backoff for text/agent calls (vision OCR has its own retry in
    # app/ocr/providers/claude.py)
    MAX_RETRIES: int = settings.CLAUDE_MAX_RETRIES
    RETRY_BASE_DELAY: float = settings.CLAUDE_RETRY_BASE_DELAY

    # Vision OCR Prompt
    # No JSON-schema description needed here — output_format=OCRPageExtraction
    # (see app/claude/vision.py) makes Claude's structured-output support
    # guarantee a schema-conformant response, so fields like "confidence" can
    # never be missing (the root cause of the old Gemini confidence-defaulting bug).
    VISION_OCR_PROMPT = """You are a medical OCR specialist. Transcribe all text from this clinical document image exactly as written.

RULES:
1. Transcribe ONLY what you can clearly read into extracted_text — never guess or fabricate text. Wrap any illegible word or phrase as [UNCLEAR: best guess] and add a short description of each one to unclear_sections.
2. Preserve the original structure and line breaks (diagnoses, medications, allergies, procedures, labs, notes).
3. Set handwriting_detected and handwriting_percentage based on how much of the page is handwritten.
4. Set confidence to your overall confidence (0.0-1.0) that the transcription is accurate and complete.
5. Set requires_review to true whenever confidence is low, content is illegible, or handwriting is present.

Prioritize patient safety: when text is genuinely hard to read, give a lower confidence score and list it in unclear_sections rather than guessing."""

    @staticmethod
    def validate() -> bool:
        """Validate Claude configuration"""
        if not ClaudeConfig.API_KEY:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        return True

    @staticmethod
    def get_vision_model() -> str:
        """Get configured vision model"""
        return ClaudeConfig.VISION_MODEL
