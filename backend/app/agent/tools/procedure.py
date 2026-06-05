from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.agent.models import AgentState, AgentTask, ToolResult
from app.agent.tools.base import BaseTool
from app.knowledge.models import Procedure
from app.knowledge.prompts import EXTRACTION_SYSTEM_PROMPT, PROCEDURE_EXTRACTION_PROMPT
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

_TOOL_SCHEMA = {
    "name": "extract_procedures",
    "description": "Extract clinical procedures and interventions",
    "input_schema": {
        "type": "object",
        "properties": {
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
        },
        "required": ["procedures"],
    },
}


class ProcedureTool(BaseTool):
    name = "procedure_extractor"
    description = "Extracts clinical procedures, interventions, and their outcomes"

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

        sections = [f"=== Document: {n} (type: {t}) ===\n{text}" for _, n, t, text in doc_list]
        combined = "\n\n".join(sections)

        prompt = PROCEDURE_EXTRACTION_PROMPT.format(document_text=combined)

        try:
            response = await self.client.messages.create(
                model=self.settings.CLAUDE_MODEL,
                max_tokens=2048,
                system=EXTRACTION_SYSTEM_PROMPT,
                tools=[_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": "extract_procedures"},
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            logger.error("ProcedureTool API error", error=str(exc))
            return self._empty_result(task, f"Claude API error: {exc}")

        raw = self._extract_tool_use(response, "extract_procedures") or {}
        tokens = self._count_tokens(response)
        facts_added = 0

        default_doc_id, default_doc_name = doc_list[0][0], doc_list[0][1]

        for p_raw in raw.get("procedures", []):
            try:
                name_fact = self._make_evidenced_fact(
                    value=p_raw["name"],
                    confidence=float(p_raw.get("confidence", 0.8)),
                    source_doc_id=default_doc_id,
                    source_doc_name=default_doc_name,
                    page_number=int(p_raw.get("page_number", 1)),
                    evidence=p_raw.get("evidence", ""),
                )
                date_fact = None
                if p_raw.get("date"):
                    date_fact = self._make_evidenced_fact(
                        value=p_raw["date"],
                        confidence=float(p_raw.get("confidence", 0.8)),
                        source_doc_id=default_doc_id,
                        source_doc_name=default_doc_name,
                        page_number=int(p_raw.get("page_number", 1)),
                        evidence=p_raw.get("evidence", "")[:200],
                    )
                outcome_fact = None
                if p_raw.get("outcome"):
                    outcome_fact = self._make_evidenced_fact(
                        value=p_raw["outcome"],
                        confidence=float(p_raw.get("confidence", 0.75)),
                        source_doc_id=default_doc_id,
                        source_doc_name=default_doc_name,
                        page_number=int(p_raw.get("page_number", 1)),
                        evidence=p_raw.get("evidence", "")[:200],
                    )
                proc = Procedure(name=name_fact, date=date_fact, outcome=outcome_fact)
                kb.add_fact("procedure", proc)
                kb.add_source_document(default_doc_id)
                facts_added += 1
            except Exception as exc:
                logger.warning("Failed to parse procedure", error=str(exc))

        duration_ms = (time.time() - start) * 1000
        state.add_tokens(response.usage.input_tokens, response.usage.output_tokens)

        return self._ok_result(
            task=task,
            facts=facts_added,
            findings={"procedures_count": facts_added},
            tokens=tokens,
            duration_ms=duration_ms,
            notes=f"Extracted {facts_added} procedures",
        )
