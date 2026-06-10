from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.agent.models import AgentState, AgentTask, ToolResult
from app.agent.tools.base import BaseTool
from app.claude.agent_client import ClaudeUnavailableError
from app.knowledge.models import Procedure
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


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

        try:
            extraction = await self._get_consolidated_extraction(doc_list)
        except ClaudeUnavailableError as exc:
            logger.error(f"{self.name} Claude unavailable", error=str(exc))
            return self._claude_unavailable_result(task, state, exc)
        except Exception as exc:
            logger.error(f"{self.name} API error", error=str(exc))
            return self._empty_result(task, f"Claude API error: {exc}")

        raw = extraction.data
        tokens = extraction.tokens_used
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
        state.add_tokens(extraction.input_tokens_used, tokens)

        return self._ok_result(
            task=task,
            facts=facts_added,
            findings={"procedures_count": facts_added},
            tokens=tokens,
            duration_ms=duration_ms,
            notes=f"Extracted {facts_added} procedures",
        )
