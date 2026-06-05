from __future__ import annotations

import time
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.agent.models import AgentState, AgentTask, ToolResult
from app.agent.tools.base import BaseTool
from app.knowledge.models import Medication
from app.knowledge.prompts import EXTRACTION_SYSTEM_PROMPT, MEDICATION_EXTRACTION_PROMPT
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

_TOOL_SCHEMA = {
    "name": "extract_medications",
    "description": "Extract all admission and discharge medications with dose, route, frequency",
    "input_schema": {
        "type": "object",
        "properties": {
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
        },
        "required": ["admission_medications", "discharge_medications"],
    },
}


def _parse_med_raw(
    raw: Dict,
    is_admission: bool,
    doc_id: str,
    doc_name: str,
    make_fact,
) -> Optional[Medication]:
    try:
        name_fact = make_fact(
            value=raw["name"],
            confidence=float(raw.get("confidence", 0.8)),
            source_doc_id=doc_id,
            source_doc_name=doc_name,
            page_number=int(raw.get("page_number", 1)),
            evidence=raw.get("evidence", ""),
        )

        def opt_fact(field: str, default_evidence: str = "") -> Optional[object]:
            val = raw.get(field, "").strip()
            if not val:
                return None
            return make_fact(
                value=val,
                confidence=float(raw.get("confidence", 0.8)),
                source_doc_id=doc_id,
                source_doc_name=doc_name,
                page_number=int(raw.get("page_number", 1)),
                evidence=raw.get("evidence", default_evidence)[:200],
            )

        return Medication(
            name=name_fact,
            dose=opt_fact("dose"),
            route=opt_fact("route"),
            frequency=opt_fact("frequency"),
            indication=raw.get("indication") or None,
            is_admission=is_admission,
            is_changed_at_discharge=bool(raw.get("is_changed_at_discharge", False)),
            change_reason=raw.get("change_reason") or None,
            is_discontinued=bool(raw.get("is_discontinued", False)),
        )
    except Exception as exc:
        logger.warning("Failed to parse medication", error=str(exc), raw=raw)
        return None


class MedicationTool(BaseTool):
    name = "medication_extractor"
    description = "Extracts admission medications and discharge medications with full details"

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
        for _, doc_name, doc_type, text in doc_list:
            sections.append(f"=== Document: {doc_name} (type: {doc_type}) ===\n{text}")
        combined = "\n\n".join(sections)

        prompt = MEDICATION_EXTRACTION_PROMPT.format(document_text=combined)

        try:
            response = await self.client.messages.create(
                model=self.settings.CLAUDE_MODEL,
                max_tokens=4096,
                system=EXTRACTION_SYSTEM_PROMPT,
                tools=[_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": "extract_medications"},
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            logger.error("MedicationTool API error", error=str(exc))
            return self._empty_result(task, f"Claude API error: {exc}")

        raw = self._extract_tool_use(response, "extract_medications") or {}
        tokens = self._count_tokens(response)
        facts_added = 0

        default_doc_id, default_doc_name = doc_list[0][0], doc_list[0][1]

        for med_raw in raw.get("admission_medications", []):
            med = _parse_med_raw(
                med_raw, is_admission=True,
                doc_id=default_doc_id, doc_name=default_doc_name,
                make_fact=self._make_evidenced_fact,
            )
            if med:
                kb.add_fact("medication_admission", med)
                kb.add_source_document(default_doc_id)
                facts_added += 1

        for med_raw in raw.get("discharge_medications", []):
            med = _parse_med_raw(
                med_raw, is_admission=False,
                doc_id=default_doc_id, doc_name=default_doc_name,
                make_fact=self._make_evidenced_fact,
            )
            if med:
                kb.add_fact("medication_discharge", med)
                kb.add_source_document(default_doc_id)
                facts_added += 1

        duration_ms = (time.time() - start) * 1000
        adm_count = len(raw.get("admission_medications", []))
        dis_count = len(raw.get("discharge_medications", []))

        state.add_tokens(response.usage.input_tokens, response.usage.output_tokens)

        return self._ok_result(
            task=task,
            facts=facts_added,
            findings={
                "admission_medications": adm_count,
                "discharge_medications": dis_count,
                "total_medications": adm_count + dis_count,
            },
            tokens=tokens,
            duration_ms=duration_ms,
            notes=f"Extracted {adm_count} admission + {dis_count} discharge medications",
        )
