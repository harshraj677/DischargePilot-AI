from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.agent.models import AgentState, AgentTask, ToolResult
from app.agent.tools.base import BaseTool
from app.claude.agent_client import ClaudeUnavailableError
from app.knowledge.models import Diagnosis, FollowUp
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


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

        # Follow-ups
        followup_count = 0
        for fu_raw in raw.get("followups", []):
            try:
                instruction_fact = self._make_evidenced_fact(
                    value=fu_raw["instruction"],
                    confidence=float(fu_raw.get("confidence", 0.8)),
                    source_doc_id=default_doc_id,
                    source_doc_name=default_doc_name,
                    page_number=int(fu_raw.get("page_number", 1)),
                    evidence=fu_raw.get("evidence", ""),
                )
                followup = FollowUp(
                    instruction=instruction_fact,
                    specialist=fu_raw.get("specialist") or None,
                    timeframe=fu_raw.get("timeframe") or None,
                    contact=fu_raw.get("contact") or None,
                )
                kb.add_fact("follow_up", followup)
                kb.add_source_document(default_doc_id)
                facts_added += 1
                followup_count += 1
            except Exception as exc:
                logger.warning("Failed to parse follow-up", error=str(exc), raw=fu_raw)

        duration_ms = (time.time() - start) * 1000
        dx_count = len(raw.get("diagnoses", []))
        principal_count = sum(1 for d in raw.get("diagnoses", []) if d.get("is_principal"))

        state.add_tokens(extraction.input_tokens_used, tokens)

        return self._ok_result(
            task=task,
            facts=facts_added,
            findings={
                "diagnoses_count": dx_count,
                "principal_diagnoses": principal_count,
                "hospital_course_found": bool(course_text),
                "discharge_condition_found": bool(condition_text),
                "followups_count": followup_count,
            },
            tokens=tokens,
            duration_ms=duration_ms,
            notes=f"Extracted {dx_count} diagnoses, {followup_count} follow-ups from {len(doc_list)} documents",
        )
