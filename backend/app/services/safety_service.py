from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.agent.models import AgentRunResult
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

    def __init__(self, db: Session) -> None:
        self._db = db

    async def validate_agent_run(
        self,
        patient_id: str,
        run_id: str,
        kb: KnowledgeRepository,
        agent_result: Optional[AgentRunResult] = None,
    ) -> SafetyReport:
        """
        Run safety validation on the given knowledge base.

        Returns a SafetyReport. The caller is responsible for deciding
        whether to proceed to summary generation based on `report.can_generate_summary`.
        """
        logger.info("Safety validation requested", patient_id=patient_id, run_id=run_id)
        report = _engine.validate(kb, agent_result)
        audit.log(
            "safety_service_validate",
            patient_id=patient_id,
            run_id=run_id,
            status=report.overall_status.value,
            safety_score=round(report.safety_score, 3),
        )
        return report
