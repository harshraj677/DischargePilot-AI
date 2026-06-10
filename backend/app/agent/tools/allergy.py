from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.agent.models import AgentState, AgentTask, ToolResult
from app.agent.tools.base import BaseTool
from app.claude.agent_client import ClaudeUnavailableError
from app.knowledge.models import Allergy
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AllergyTool(BaseTool):
    name = "allergy_extractor"
    description = "Extracts allergies, reactions, severity, and NKDA status"

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

        # NKDA as explicit allergy record
        if raw.get("nkda"):
            nkda_fact = self._make_evidenced_fact(
                value="NKDA",
                confidence=0.95,
                source_doc_id=default_doc_id,
                source_doc_name=default_doc_name,
                page_number=int(raw.get("nkda_page", 1)),
                evidence=raw.get("nkda_evidence", "No Known Drug Allergies"),
            )
            kb.add_fact("allergy", Allergy(allergen=nkda_fact, severity="none"))
            facts_added += 1

        for a_raw in raw.get("allergies", []):
            try:
                allergen_fact = self._make_evidenced_fact(
                    value=a_raw["allergen"],
                    confidence=float(a_raw.get("confidence", 0.85)),
                    source_doc_id=default_doc_id,
                    source_doc_name=default_doc_name,
                    page_number=int(a_raw.get("page_number", 1)),
                    evidence=a_raw.get("evidence", ""),
                )
                reaction_fact = None
                if a_raw.get("reaction"):
                    reaction_fact = self._make_evidenced_fact(
                        value=a_raw["reaction"],
                        confidence=float(a_raw.get("confidence", 0.80)),
                        source_doc_id=default_doc_id,
                        source_doc_name=default_doc_name,
                        page_number=int(a_raw.get("page_number", 1)),
                        evidence=a_raw.get("evidence", "")[:200],
                    )
                allergy = Allergy(
                    allergen=allergen_fact,
                    reaction=reaction_fact,
                    severity=a_raw.get("severity") or None,
                )
                kb.add_fact("allergy", allergy)
                kb.add_source_document(default_doc_id)
                facts_added += 1
            except Exception as exc:
                logger.warning("Failed to parse allergy", error=str(exc))

        duration_ms = (time.time() - start) * 1000
        state.add_tokens(extraction.input_tokens_used, tokens)

        return self._ok_result(
            task=task,
            facts=facts_added,
            findings={
                "allergies_count": len(raw.get("allergies", [])),
                "nkda": bool(raw.get("nkda")),
            },
            tokens=tokens,
            duration_ms=duration_ms,
            notes=f"Extracted {facts_added} allergy records (NKDA={raw.get('nkda')})",
        )
