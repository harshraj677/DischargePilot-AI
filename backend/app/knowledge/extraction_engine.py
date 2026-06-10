"""
Clinical Knowledge Extraction Engine

STEP 3 of the Claude migration: a single consolidated Claude call extracts
every clinical category (diagnoses, medications, allergies, procedures,
pending results, labs, follow-ups, hospital course, discharge condition)
from a patient's documents in one pass.

Results are cached by SHA256(document_text) via ClaudeResponseCache, so
repeated extraction tools (and repeated agent runs over the same documents)
reuse the same structured result instead of calling Claude again.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.claude.agent_client import ClaudeAgentClient
from app.claude.cache import get_claude_response_cache
from app.knowledge.prompts import EXTRACTION_SYSTEM_PROMPT
from app.utils.json_parsing import parse_json_response

logger = logging.getLogger(__name__)

CONSOLIDATED_EXTRACTION_PROMPT = """\
Extract ALL of the following clinical information from the document(s) below \
in a single pass. Documents may be separated by === dividers.

{document_text}

1. DIAGNOSES
- Identify the PRINCIPAL (primary/admitting) diagnosis and all SECONDARY diagnoses
- Extract ICD-10 codes if explicitly listed
- Do NOT create diagnoses that are not explicitly documented

2. HOSPITAL COURSE & DISCHARGE CONDITION
- Extract the hospital course summary as a single narrative paragraph if present
- Extract the discharge condition if stated (stable / fair / guarded / critical / expired)

3. MEDICATIONS
- Separate ADMISSION medications (home/current medications on arrival) from \
DISCHARGE medications (prescribed at discharge)
- For each medication extract: name, dose, route, frequency, and indication if stated
- Note any medications that were CHANGED or DISCONTINUED at discharge, with the reason if documented

4. ALLERGIES
- Extract each allergen (medication, food, environmental), the reaction if documented, \
and severity if stated (mild / moderate / severe / life-threatening)
- Note "NKDA" / "No Known Drug Allergies" as a specific finding

5. PROCEDURES
- Include surgical, diagnostic, and therapeutic procedures and interventions
- Extract the procedure date and outcome/result if documented

6. LAB RESULTS
- Extract test name, result value, unit, and reference range
- Flag ABNORMAL results (outside reference range) and CRITICAL values (H/L/HH/LL or asterisks)
- Include panels (CBC, CMP, etc.) broken into individual tests

7. PENDING RESULTS
- Identify tests, cultures, biopsies, or consultations ordered but not yet resulted
- Extract expected timeframe and instructions for abnormal results if documented

8. FOLLOW-UPS
- Extract each follow-up appointment or instruction as a separate item
- Include specialist/department, timeframe (e.g. "in 1 week"), and contact info if provided\
"""

CONSOLIDATED_SCHEMA = {
    "type": "object",
    "properties": {
        "diagnoses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full diagnosis name"},
                    "icd_code": {"type": "string", "description": "ICD-10 code if explicitly listed"},
                    "is_principal": {"type": "boolean", "description": "True for primary/admitting diagnosis"},
                    "confidence": {"type": "number", "description": "0.5-1.0"},
                    "page_number": {"type": "integer"},
                    "evidence": {"type": "string", "description": "Verbatim text excerpt, max 300 chars"},
                },
                "required": ["name", "is_principal", "confidence", "page_number", "evidence"],
            },
        },
        "hospital_course": {
            "type": "string",
            "description": "Hospital course summary paragraph if found, else empty string",
        },
        "hospital_course_page": {"type": "integer", "description": "Page where hospital course was found"},
        "discharge_condition": {
            "type": "string",
            "description": "Discharge condition (stable/fair/guarded/critical) if stated, else empty string",
        },
        "discharge_condition_page": {"type": "integer"},
        "admission_medications": {
            "type": "array",
            "description": "Medications the patient was taking before admission",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "dose": {"type": "string"},
                    "route": {"type": "string"},
                    "frequency": {"type": "string"},
                    "indication": {"type": "string"},
                    "confidence": {"type": "number"},
                    "page_number": {"type": "integer"},
                    "evidence": {"type": "string"},
                },
                "required": ["name", "confidence", "page_number", "evidence"],
            },
        },
        "discharge_medications": {
            "type": "array",
            "description": "Medications prescribed at discharge",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "dose": {"type": "string"},
                    "route": {"type": "string"},
                    "frequency": {"type": "string"},
                    "indication": {"type": "string"},
                    "is_changed_at_discharge": {"type": "boolean"},
                    "change_reason": {"type": "string"},
                    "is_discontinued": {"type": "boolean"},
                    "confidence": {"type": "number"},
                    "page_number": {"type": "integer"},
                    "evidence": {"type": "string"},
                },
                "required": ["name", "confidence", "page_number", "evidence"],
            },
        },
        "allergies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "allergen": {"type": "string", "description": "Name of allergen"},
                    "reaction": {"type": "string", "description": "Specific reaction or empty string"},
                    "severity": {
                        "type": "string",
                        "enum": ["mild", "moderate", "severe", "life-threatening", "unknown", ""],
                    },
                    "confidence": {"type": "number"},
                    "page_number": {"type": "integer"},
                    "evidence": {"type": "string"},
                },
                "required": ["allergen", "confidence", "page_number", "evidence"],
            },
        },
        "nkda": {
            "type": "boolean",
            "description": "True if document explicitly states No Known Drug Allergies",
        },
        "nkda_page": {"type": "integer"},
        "nkda_evidence": {"type": "string"},
        "procedures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "date": {"type": "string", "description": "Procedure date if stated, else empty"},
                    "outcome": {"type": "string", "description": "Outcome or result if stated, else empty"},
                    "confidence": {"type": "number"},
                    "page_number": {"type": "integer"},
                    "evidence": {"type": "string"},
                },
                "required": ["name", "confidence", "page_number", "evidence"],
            },
        },
        "lab_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "test_name": {"type": "string"},
                    "value": {"type": "string", "description": "Result value as string"},
                    "unit": {"type": "string", "description": "Unit of measurement, or empty"},
                    "reference_range": {"type": "string", "description": "Normal range if stated"},
                    "collection_date": {"type": "string", "description": "Date collected, or empty"},
                    "is_abnormal": {"type": "boolean", "description": "True if outside reference range"},
                    "is_critical": {"type": "boolean", "description": "True if critically abnormal (HH/LL/*)"},
                    "confidence": {"type": "number"},
                    "page_number": {"type": "integer"},
                    "evidence": {"type": "string"},
                },
                "required": ["test_name", "value", "is_abnormal", "is_critical", "confidence", "page_number", "evidence"],
            },
        },
        "pending_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "What is pending"},
                    "expected_by": {"type": "string", "description": "Expected timeline or date, or empty"},
                    "action_if_abnormal": {"type": "string", "description": "Recommended action if result is abnormal, or empty"},
                    "confidence": {"type": "number"},
                    "page_number": {"type": "integer"},
                    "evidence": {"type": "string"},
                },
                "required": ["description", "confidence", "page_number", "evidence"],
            },
        },
        "followups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "instruction": {"type": "string", "description": "The follow-up instruction or appointment"},
                    "specialist": {"type": "string", "description": "Specialist or department, or empty"},
                    "timeframe": {"type": "string", "description": "e.g. 'in 1 week', or empty"},
                    "contact": {"type": "string", "description": "Contact info if provided, or empty"},
                    "confidence": {"type": "number"},
                    "page_number": {"type": "integer"},
                    "evidence": {"type": "string"},
                },
                "required": ["instruction", "confidence", "page_number", "evidence"],
            },
        },
    },
    "required": [
        "diagnoses",
        "admission_medications",
        "discharge_medications",
        "allergies",
        "nkda",
        "procedures",
        "lab_results",
        "pending_results",
        "followups",
    ],
}


@dataclass
class ExtractionResult:
    """Result of a consolidated clinical extraction."""

    data: Dict[str, Any]
    input_tokens_used: int
    tokens_used: int
    from_cache: bool


class ClinicalKnowledgeExtractionEngine:
    """
    Runs ONE Claude call to extract every clinical category from a document
    set, caching the structured result by SHA256(document_text).
    """

    def __init__(self) -> None:
        self._cache = get_claude_response_cache()

    async def extract(self, document_text: str, client: ClaudeAgentClient) -> ExtractionResult:
        content_hash = self._cache.hash_content(document_text)

        cached = self._cache.get(content_hash)
        if cached is not None:
            logger.info(f"Clinical extraction cache hit ({content_hash[:12]})")
            return ExtractionResult(data=cached, input_tokens_used=0, tokens_used=0, from_cache=True)

        prompt = CONSOLIDATED_EXTRACTION_PROMPT.format(document_text=document_text)
        prompt_with_schema = (
            f"{EXTRACTION_SYSTEM_PROMPT}\n\n{prompt}\n\n"
            f"Please output ONLY valid JSON matching the following schema:\n"
            f"{json.dumps(CONSOLIDATED_SCHEMA)}"
        )

        response_text = await client.generate_content(prompt=prompt_with_schema, model_type="text")
        data = parse_json_response(response_text) or {}
        input_tokens_used = len(prompt_with_schema) // 4
        tokens_used = len(response_text) // 4

        self._cache.set(content_hash, data)
        logger.info(f"Clinical extraction completed and cached ({content_hash[:12]})")
        return ExtractionResult(data=data, input_tokens_used=input_tokens_used, tokens_used=tokens_used, from_cache=False)


_engine_instance: Optional[ClinicalKnowledgeExtractionEngine] = None


def get_extraction_engine() -> ClinicalKnowledgeExtractionEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ClinicalKnowledgeExtractionEngine()
    return _engine_instance
