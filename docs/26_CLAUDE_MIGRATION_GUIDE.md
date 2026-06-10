# DischargePilot AI — Gemini → Claude Migration Guide

**Migration Status**: Complete
**Date**: 2026-06-10
**Supersedes**: `25_GEMINI_MIGRATION_PLAN.md` (the Claude→Gemini plan — reversed by this migration)

---

## 1. Summary

DischargePilot AI's single AI provider is now **Anthropic Claude**, used for:

- Agent loop reasoning (tool selection, planning, summarization)
- Clinical knowledge extraction (diagnoses, medications, allergies, procedures, labs, etc.)
- Discharge summary generation and learning/review feedback
- Vision OCR for scanned/image pages and uploaded JPG/PNG/WEBP images

The Gemini provider (`app/gemini/`), its config, `.env` keys, and all `GeminiClient`/`GeminiVisionOCR` references have been removed. No architectural changes were made — the Agent Loop, Tool Registry, Safety Engine, Medication Reconciliation, Conflict Detection, Learning System, Trace Viewer, and frontend UI are unchanged; only the underlying LLM provider was swapped.

---

## 2. Environment Variables

Remove (no longer used):

```
GEMINI_API_KEY
GEMINI_MODEL
GEMINI_VISION_MODEL
```

Add to `backend/.env` (see `backend/.env.example`):

```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_VISION_MODEL=claude-opus-4-8
ANTHROPIC_TEXT_MODEL=claude-sonnet-4-6
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_MAX_RETRIES=3
CLAUDE_RETRY_BASE_DELAY=2.0
CLAUDE_RESPONSE_CACHE_ENABLED=true
OCR_PRIMARY_PROVIDER=claude
```

`ANTHROPIC_API_KEY` is required at startup — `ClaudeAgentClient` and `ClaudeClient` both raise `ValueError("ANTHROPIC_API_KEY environment variable not set")` if it's missing.

---

## 3. Model Selection (`app/claude/config.py`)

| Setting | Default | Used by |
|---|---|---|
| `ANTHROPIC_TEXT_MODEL` | `claude-sonnet-4-6` | Agent loop, extraction engine, summary generator, learning/reviewer |
| `ANTHROPIC_VISION_MODEL` | `claude-opus-4-8` | `ClaudeVisionOCR` / `ClaudeVisionService` (scanned pages, image uploads) |

Both are overridable per-environment without code changes.

---

## 4. New Components

### `app/claude/client.py` — `ClaudeClient`
Singleton synchronous `anthropic.Anthropic` wrapper used by the OCR vision service (the `OCRProvider` interface is synchronous; OCR runs via `asyncio.to_thread`, so no event-loop bridging is needed).

### `app/claude/agent_client.py` — `ClaudeAgentClient`
Singleton `anthropic.AsyncAnthropic` wrapper exposing a Gemini-compatible `generate_content(prompt, images=None, model_type="text")` interface, used throughout the agent loop, tools, and services. Retries `RateLimitError`, `APIConnectionError`, and `InternalServerError` up to `CLAUDE_MAX_RETRIES` times with exponential backoff (`tenacity`); other errors (auth, invalid request) raise `ClaudeUnavailableError` immediately.

### `app/claude/vision.py` — `ClaudeVisionService`
`perform_ocr(image, page_number)` uses Claude's structured outputs (`output_format=OCRPageExtraction`) to guarantee a schema-conformant response — `extracted_text`, `confidence`, `handwriting_detected`, `handwriting_percentage`, `unclear_sections`, `requires_review` are never missing, eliminating the old Gemini confidence-defaulting failure mode.

### `app/ocr/providers/claude.py` — `ClaudeVisionOCR`
Primary OCR provider (`OCR_PRIMARY_PROVIDER=claude`). Supports JPEG/PNG/WEBP (via `app.config.ALLOWED_EXTENSIONS`). On success, returns an `OCRResult` with `metadata.provider="claude"` and records an `ocr` usage event. On failure (after 3 retries on transient errors), returns a zero-confidence `OCRResult` with `requires_manual_review=True` and `review_reason="OCR failed after retries: ..."` — it never raises, so `OCRFallbackEngine` can fall through to EasyOCR/Tesseract.

### `app/claude/cache.py` — `ClaudeResponseCache`
File cache at `cache/claude_responses/<sha256(document_text)>.json`. `ClinicalKnowledgeExtractionEngine.extract()` hashes the combined document text; on a hit, the cached structured extraction is returned (`ExtractionResult.from_cache=True`) and Claude is not called again. Disabled via `CLAUDE_RESPONSE_CACHE_ENABLED=false`.

### `app/knowledge/extraction_engine.py` — `ClinicalKnowledgeExtractionEngine`
Single Claude call extracts all 8 clinical categories at once (diagnoses, hospital course/discharge condition, admission/discharge medications, allergies, procedures, lab results, pending results, follow-ups). The 6 extraction tools (diagnosis, medication, allergy, procedure, lab, pending_result) read from this shared, cached result instead of issuing separate LLM calls.

### `app/claude/usage.py` — `ClaudeUsageStats`
Process-lifetime counters (text/vision/ocr requests, errors, cache hits/misses, last request/error timestamps), exposed via `GET /api/v1/system/claude-status` and surfaced in the frontend "Claude Status" panel.

---

## 5. Failure Handling

- **Agent/text calls**: transient errors retried with exponential backoff (`CLAUDE_MAX_RETRIES`, `CLAUDE_RETRY_BASE_DELAY`); exhausted retries or non-transient errors raise `ClaudeUnavailableError`, recorded via `usage.record_error()`.
- **OCR calls**: same retry policy, but failures are absorbed into a degraded `OCRResult` (confidence 0.0, flagged for manual review) rather than propagating, so a single bad page never aborts a document.
- **Extraction parsing**: an unparseable Claude response yields `ExtractionResult.data == {}` rather than raising, so downstream tools see "no data found" instead of crashing.

---

## 6. Testing

New/updated test coverage (`backend/tests/`):

- `test_claude/test_agent_client.py` — singleton init, text/vision model selection, retry/backoff config, `ClaudeUnavailableError` on auth/rate-limit failures
- `test_claude/test_cache.py` — SHA256 hashing, get/set, cache hit/miss usage stats, disabled-cache behavior, corrupted-entry handling
- `test_claude/test_extraction_engine.py` — single-call extraction across all 8 categories, cache reuse (second identical call doesn't re-invoke Claude), per-document cache isolation, malformed-response handling
- `test_ocr/test_claude_provider.py` — `ClaudeVisionOCR.process_image()` across JPEG/PNG/WEBP, success/failure paths, review-reason mapping (unclear sections, handwriting, low confidence), usage stat recording, and the `OCRFallbackEngine` scanned-page workflow with Claude as primary provider

Run with:

```
cd backend
./venv/Scripts/python.exe -m pytest -q tests/test_claude/ tests/test_ocr/test_claude_provider.py
```

---

## 7. Frontend

The "Claude Status" panel (replacing the old Gemini status display) calls `GET /api/v1/system/claude-status` and shows: configuration state, text/vision model names, request/error counts, response cache hit/miss counts, and OCR provider status.
