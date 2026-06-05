from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.agent.models import AgentState, AgentTask, ToolResult
from app.agent.tools.base import BaseTool
from app.knowledge.models import PendingResult
from app.knowledge.prompts import EXTRACTION_SYSTEM_PROMPT, PENDING_RESULT_EXTRACTION_PROMPT
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

_TOOL_SCHEMA = {
    "name": "extract_pending_results",
    "description": "Identify tests, cultures, or results pending at discharge",
    "input_schema": {
        "type": "object",
        "properties": {
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
        },
        "required": ["pending_results"],
    },
}


class PendingResultTool(BaseTool):
    name = "pending_result_extractor"
    description = "Identifies pending tests and outstanding results at discharge"

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

        prompt = PENDING_RESULT_EXTRACTION_PROMPT.format(document_text=combined)

        try:
            response = await self.client.messages.create(
                model=self.settings.CLAUDE_MODEL,
                max_tokens=2048,
                system=EXTRACTION_SYSTEM_PROMPT,
                tools=[_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": "extract_pending_results"},
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            logger.error("PendingResultTool API error", error=str(exc))
            return self._empty_result(task, f"Claude API error: {exc}")

        raw = self._extract_tool_use(response, "extract_pending_results") or {}
        tokens = self._count_tokens(response)
        facts_added = 0

        default_doc_id, default_doc_name = doc_list[0][0], doc_list[0][1]

        for pr_raw in raw.get("pending_results", []):
            try:
                desc_fact = self._make_evidenced_fact(
                    value=pr_raw["description"],
                    confidence=float(pr_raw.get("confidence", 0.85)),
                    source_doc_id=default_doc_id,
                    source_doc_name=default_doc_name,
                    page_number=int(pr_raw.get("page_number", 1)),
                    evidence=pr_raw.get("evidence", ""),
                )
                pr = PendingResult(
                    description=desc_fact,
                    expected_by=pr_raw.get("expected_by") or None,
                    action_if_abnormal=pr_raw.get("action_if_abnormal") or None,
                )
                kb.add_fact("pending_result", pr)
                kb.add_source_document(default_doc_id)
                facts_added += 1
            except Exception as exc:
                logger.warning("Failed to parse pending result", error=str(exc))

        duration_ms = (time.time() - start) * 1000
        state.add_tokens(response.usage.input_tokens, response.usage.output_tokens)

        return self._ok_result(
            task=task,
            facts=facts_added,
            findings={"pending_results_count": facts_added},
            tokens=tokens,
            duration_ms=duration_ms,
            notes=f"Identified {facts_added} pending results",
        )
