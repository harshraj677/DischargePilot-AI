from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.agent.models import AgentState, AgentTask, ToolResult
from app.agent.tools.base import BaseTool
from app.groq_provider.agent_client import GroqUnavailableError
from app.knowledge.repository import KnowledgeRepository
from app.safety.engine import SafetyValidationEngine
from app.services.summary_service import SummaryService
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SummaryGeneratorTool(BaseTool):
    name = "summary_generator"
    description = "Generates and persists the structured discharge summary from the clinical knowledge base"

    async def execute(
        self,
        task: AgentTask,
        state: AgentState,
        kb: KnowledgeRepository,
        db: Session,
    ) -> ToolResult:
        start = time.time()
        patient_id = state.patient_id
        run_id = state.run_id

        print(f"SUMMARY_GENERATOR_STARTED patient_id={patient_id} run_id={run_id}", flush=True)
        logger.info("SUMMARY_GENERATOR_STARTED", patient_id=patient_id, run_id=run_id)

        try:
            # Safety findings are still computed and attached to the summary
            # (review_flags, blocking_issues) for clinician visibility, but
            # never block generation outright — escalation must never
            # bypass SummaryGenerator. validate() defaults run_id to
            # "no-run" without an AgentRunResult, so set the real one.
            safety_report = SafetyValidationEngine().validate(kb)
            safety_report.run_id = run_id

            summary_service = SummaryService(db, self.client, self.settings)
            summary = await summary_service.generate_and_persist(patient_id, run_id, kb, safety_report)
        except GroqUnavailableError as exc:
            logger.error(f"{self.name} Groq unavailable", error=str(exc))
            return self._groq_unavailable_result(task, state, exc)
        except Exception as exc:
            logger.error("SUMMARY_GENERATOR_FAILED", patient_id=patient_id, run_id=run_id, error=str(exc))
            return self._empty_result(task, f"Summary generation failed: {exc}")

        duration_ms = (time.time() - start) * 1000
        print(
            f"SUMMARY_GENERATOR_COMPLETED patient_id={patient_id} run_id={run_id} summary_id={summary.summary_id}",
            flush=True,
        )
        logger.info(
            "SUMMARY_GENERATOR_COMPLETED",
            patient_id=patient_id,
            run_id=run_id,
            summary_id=summary.summary_id,
            duration_ms=round(duration_ms),
        )

        return self._ok_result(
            task=task,
            facts=summary.populated_section_count,
            findings={
                "summary_id": summary.summary_id,
                "completeness_score": summary.completeness_score,
                "safety_score": summary.safety_score,
                "review_flag_count": len(summary.review_flags),
                "persisted": True,
            },
            tokens=0,
            duration_ms=duration_ms,
            notes=f"Discharge summary generated and saved for patient {patient_id}",
        )
