from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.agent.models import AgentState, AgentTask, ToolResult
from app.agent.tools.base import BaseTool
from app.claude.agent_client import ClaudeUnavailableError
from app.knowledge.models import LabResult
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LabTool(BaseTool):
    name = "lab_extractor"
    description = "Extracts laboratory results, flags abnormal and critical values"

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
            return self._empty_result(task, "No lab report documents available")

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
        abnormal_count = 0
        critical_count = 0

        default_doc_id, default_doc_name = doc_list[0][0], doc_list[0][1]

        for lab_raw in raw.get("lab_results", []):
            try:
                test_fact = self._make_evidenced_fact(
                    value=lab_raw["test_name"],
                    confidence=float(lab_raw.get("confidence", 0.9)),
                    source_doc_id=default_doc_id,
                    source_doc_name=default_doc_name,
                    page_number=int(lab_raw.get("page_number", 1)),
                    evidence=lab_raw.get("evidence", ""),
                )
                value_fact = self._make_evidenced_fact(
                    value=lab_raw["value"],
                    confidence=float(lab_raw.get("confidence", 0.9)),
                    source_doc_id=default_doc_id,
                    source_doc_name=default_doc_name,
                    page_number=int(lab_raw.get("page_number", 1)),
                    evidence=lab_raw.get("evidence", "")[:200],
                )
                collection_fact = None
                if lab_raw.get("collection_date"):
                    collection_fact = self._make_evidenced_fact(
                        value=lab_raw["collection_date"],
                        confidence=float(lab_raw.get("confidence", 0.85)),
                        source_doc_id=default_doc_id,
                        source_doc_name=default_doc_name,
                        page_number=int(lab_raw.get("page_number", 1)),
                        evidence=lab_raw.get("evidence", "")[:100],
                    )
                is_abnormal = bool(lab_raw.get("is_abnormal", False))
                is_critical = bool(lab_raw.get("is_critical", False))

                lab = LabResult(
                    test_name=test_fact,
                    value=value_fact,
                    unit=lab_raw.get("unit") or None,
                    reference_range=lab_raw.get("reference_range") or None,
                    collection_date=collection_fact,
                    is_abnormal=is_abnormal,
                    is_critical=is_critical,
                )
                kb.add_fact("lab_result", lab)
                kb.add_source_document(default_doc_id)
                facts_added += 1

                if is_abnormal:
                    abnormal_count += 1
                if is_critical:
                    critical_count += 1

            except Exception as exc:
                logger.warning("Failed to parse lab result", error=str(exc))

        duration_ms = (time.time() - start) * 1000
        state.add_tokens(extraction.input_tokens_used, tokens)

        if critical_count > 0:
            state.identified_conflicts.append(f"{critical_count} critical lab value(s) detected")

        return self._ok_result(
            task=task,
            facts=facts_added,
            findings={
                "lab_results": facts_added,
                "abnormal_count": abnormal_count,
                "critical_count": critical_count,
            },
            tokens=tokens,
            duration_ms=duration_ms,
            notes=f"Extracted {facts_added} lab results ({abnormal_count} abnormal, {critical_count} critical)",
        )
