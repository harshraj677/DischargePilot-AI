from __future__ import annotations

import time
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.agent.models import AgentState, AgentTask, ToolResult
from app.agent.tools.base import BaseTool
from app.knowledge.models import Diagnosis, EvidencedFact
from app.knowledge.prompts import DIAGNOSIS_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

_TOOL_SCHEMA = {
    "name": "extract_diagnoses",
    "description": "Extract all clinical diagnoses from the patient documents",
    "input_schema": {
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
        },
        "required": ["diagnoses"],
    },
}


class DiagnosisTool(BaseTool):
    name = "diagnosis_extractor"
    description = "Extracts principal and secondary diagnoses, hospital course, and discharge condition"

    async def execute(
        self,
        task: AgentTask,
        state: AgentState,
        kb: KnowledgeRepository,
        db: Session,
    ) -> ToolResult:
        start = time.time()

        doc_list = self._build_combined_text(task.document_ids, db)
        if not doc_list:
            return self._empty_result(task, "No document text available")

        sections = []
        for doc_id, doc_name, doc_type, text in doc_list:
            sections.append(f"=== Document: {doc_name} (type: {doc_type}) ===\n{text}")
        combined = "\n\n".join(sections)

        prompt = DIAGNOSIS_EXTRACTION_PROMPT.format(document_text=combined)

        try:
            response = await self.client.messages.create(
                model=self.settings.CLAUDE_MODEL,
                max_tokens=4096,
                system=EXTRACTION_SYSTEM_PROMPT,
                tools=[_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": "extract_diagnoses"},
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            logger.error("DiagnosisTool API error", error=str(exc))
            return self._empty_result(task, f"Claude API error: {exc}")

        raw = self._extract_tool_use(response, "extract_diagnoses") or {}
        tokens = self._count_tokens(response)
        facts_added = 0

        # Use first document as default provenance source
        default_doc_id, default_doc_name = doc_list[0][0], doc_list[0][1]

        for dx_raw in raw.get("diagnoses", []):
            try:
                fact = self._make_evidenced_fact(
                    value=dx_raw["name"],
                    confidence=float(dx_raw.get("confidence", 0.8)),
                    source_doc_id=default_doc_id,
                    source_doc_name=default_doc_name,
                    page_number=int(dx_raw.get("page_number", 1)),
                    evidence=dx_raw.get("evidence", ""),
                )
                diagnosis = Diagnosis(
                    name=fact,
                    icd_code=dx_raw.get("icd_code") or None,
                    is_principal=bool(dx_raw.get("is_principal", False)),
                )
                kb.add_fact("diagnosis", diagnosis)
                kb.add_source_document(default_doc_id)
                facts_added += 1
            except Exception as exc:
                logger.warning("Failed to parse diagnosis", error=str(exc), raw=dx_raw)

        # Hospital course
        course_text = raw.get("hospital_course", "").strip()
        if course_text:
            course_page = int(raw.get("hospital_course_page", 1))
            course_fact = self._make_evidenced_fact(
                value=course_text[:2000],
                confidence=0.90,
                source_doc_id=default_doc_id,
                source_doc_name=default_doc_name,
                page_number=course_page,
                evidence=course_text[:500],
            )
            kb.add_fact("hospital_course", course_fact)
            facts_added += 1

        # Discharge condition
        condition_text = raw.get("discharge_condition", "").strip()
        if condition_text:
            condition_page = int(raw.get("discharge_condition_page", 1))
            condition_fact = self._make_evidenced_fact(
                value=condition_text,
                confidence=0.90,
                source_doc_id=default_doc_id,
                source_doc_name=default_doc_name,
                page_number=condition_page,
                evidence=condition_text[:300],
            )
            kb.add_fact("discharge_condition", condition_fact)
            facts_added += 1

        duration_ms = (time.time() - start) * 1000
        dx_count = len(raw.get("diagnoses", []))
        principal_count = sum(1 for d in raw.get("diagnoses", []) if d.get("is_principal"))

        state.add_tokens(
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        return self._ok_result(
            task=task,
            facts=facts_added,
            findings={
                "diagnoses_count": dx_count,
                "principal_diagnoses": principal_count,
                "hospital_course_found": bool(course_text),
                "discharge_condition_found": bool(condition_text),
            },
            tokens=tokens,
            duration_ms=duration_ms,
            notes=f"Extracted {dx_count} diagnoses from {len(doc_list)} documents",
        )
