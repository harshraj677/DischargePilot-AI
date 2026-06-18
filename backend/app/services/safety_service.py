from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.agent.models import AgentRunResult
from app.groq_provider.agent_client import GroqAgentClient
from app.knowledge.repository import KnowledgeRepository
from app.safety.engine import SafetyValidationEngine
from app.safety.models import SafetyReport
from app.utils.logging import AuditLogger, get_logger

logger = get_logger(__name__)
audit = AuditLogger(module="safety_service")

_engine = SafetyValidationEngine()


class SafetyService:
    """
    Service layer for safety validation.

    Validates the knowledge base produced by an agent run and persists
    the result in the DischargeReport table.
    """

    def __init__(self, db: Session, client: Optional[GroqAgentClient] = None) -> None:
        self._db = db
        self._client = client

    async def validate_agent_run(
        self,
        patient_id: str,
        run_id: str,
        kb: KnowledgeRepository,
        agent_result: Optional[AgentRunResult] = None,
    ) -> SafetyReport:
        """
        Run safety validation on the given knowledge base.

        When a Groq client was provided at construction, this also runs
        the LLM-driven clinical documentation QA pass (see
        app/safety/llm_reviewer.py) alongside the deterministic
        validators. Without a client, falls back to deterministic-only
        validation (e.g. for callers that don't have a client handy).

        Returns a SafetyReport. The caller is responsible for deciding
        whether to proceed to summary generation based on `report.can_generate_summary`.
        """
        logger.info("Safety validation requested", patient_id=patient_id, run_id=run_id)
        if self._client is not None:
            report = await _engine.validate_with_llm_review(kb, self._client, agent_result)
        else:
            report = _engine.validate(kb, agent_result)
        audit.log(
            "safety_service_validate",
            patient_id=patient_id,
            run_id=run_id,
            status=report.overall_status.value,
            safety_score=round(report.safety_score, 3),
        )
        return report
