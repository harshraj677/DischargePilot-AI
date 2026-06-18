"""
System API — AI provider status for the frontend status panels.

Routes:
    GET /api/v1/system/groq-status — Groq configuration, model,
        request counts, cache hits, rate limits, and OCR status (primary
        AI provider)
    GET /api/v1/system/claude-status — Claude configuration, model, request
        counts, cache hits, and OCR status (secondary OCR fallback provider)
    GET /api/v1/system/llm-status — live Groq authentication/connectivity
        check (does the configured GROQ_API_KEY actually work right now)
"""
from __future__ import annotations

from fastapi import APIRouter

from app.claude.config import ClaudeConfig
from app.claude.usage import get_claude_usage_stats
from app.groq_provider.config import GroqConfig
from app.groq_provider.health import GroqHealthService
from app.groq_provider.usage import get_groq_usage_stats
from app.config import settings

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/llm-status")
async def llm_status() -> dict:
    return await GroqHealthService.check_connection()


@router.get("/groq-status")
async def groq_status() -> dict:
    usage = get_groq_usage_stats().to_dict()
    configured = bool(GroqConfig.API_KEY)

    if not configured:
        status_value = "not_configured"
    elif usage["errors"] > 0 and usage["last_error_at"] == usage["last_request_at"]:
        status_value = "degraded"
    else:
        status_value = "connected"

    return {
        "provider": "groq",
        "status": status_value,
        "configured": configured,
        "text_model": GroqConfig.TEXT_MODEL,
        "vision_model": GroqConfig.VISION_MODEL,
        "requests": {
            "total": usage["total_requests"],
            "text": usage["text_requests"],
            "vision": usage["vision_requests"],
            "ocr": usage["ocr_requests"],
            "errors": usage["errors"],
            "last_request_at": usage["last_request_at"],
            "last_error": usage["last_error"],
            "last_error_at": usage["last_error_at"],
        },
        "cache": {
            "enabled": settings.GROQ_CACHE_ENABLED,
            "hits": usage["cache_hits"],
            "misses": usage["cache_misses"],
        },
        "ocr": {
            "enabled": settings.OCR_ENABLED,
            "primary_provider": settings.OCR_PRIMARY_PROVIDER,
            "status": "active" if (configured and settings.OCR_PRIMARY_PROVIDER == "groq") else "inactive",
            "requests": usage["ocr_requests"],
        },
        "rate_limit": {
            "hits": usage["rate_limited_count"],
        },
    }


@router.get("/claude-status")
async def claude_status() -> dict:
    usage = get_claude_usage_stats().to_dict()
    configured = bool(ClaudeConfig.API_KEY)

    if not configured:
        status_value = "not_configured"
    elif usage["errors"] > 0 and usage["last_error_at"] == usage["last_request_at"]:
        status_value = "degraded"
    else:
        status_value = "connected"

    return {
        "provider": "claude",
        "status": status_value,
        "configured": configured,
        "text_model": ClaudeConfig.TEXT_MODEL,
        "vision_model": ClaudeConfig.VISION_MODEL,
        "requests": {
            "total": usage["total_requests"],
            "text": usage["text_requests"],
            "vision": usage["vision_requests"],
            "ocr": usage["ocr_requests"],
            "errors": usage["errors"],
            "last_request_at": usage["last_request_at"],
            "last_error": usage["last_error"],
            "last_error_at": usage["last_error_at"],
        },
        "cache": {
            "enabled": settings.CLAUDE_RESPONSE_CACHE_ENABLED,
            "hits": usage["cache_hits"],
            "misses": usage["cache_misses"],
        },
        "ocr": {
            "enabled": settings.OCR_ENABLED,
            "primary_provider": settings.OCR_PRIMARY_PROVIDER,
            "status": "active" if (configured and settings.OCR_PRIMARY_PROVIDER == "claude") else "inactive",
            "requests": usage["ocr_requests"],
        },
    }
