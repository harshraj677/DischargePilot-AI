from __future__ import annotations

import json
import uuid
from datetime import datetime

from app.claude.agent_client import ClaudeAgentClient, get_claude_agent_client
from sqlalchemy.orm import Session

from app.agent.loop import AgentLoop
from app.agent.models import AgentRunResult, AgentRunStatus
from app.config import settings
from app.db.models import AgentRun
from app.db.repositories.patient_repo import PatientRepository
from app.utils.exceptions import PatientNotFoundException
from app.utils.logging import get_logger, AuditLogger

logger = get_logger(__name__)
audit = AuditLogger(module="agent_service")

# Singleton Claude client shared across all agent runs
_claude_client: ClaudeAgentClient | None = None


def _get_client() -> ClaudeAgentClient:
    global _claude_client
    if _claude_client is None:
        _claude_client = get_claude_agent_client()
    return _claude_client


class AgentService:
    """
    High-level orchestration service for agent runs.

    Responsibilities:
    - Validate patient existence
    - Create / update AgentRun DB record
    - Delegate to AgentLoop for actual execution
    - Persist results and memory snapshot
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    async def start_run(self, patient_id: str) -> AgentRunResult:
        """
        Starts a new agent run for the given patient.
        Creates an AgentRun record, executes the loop, persists results.
        """
        # Validate patient
        patient_repo = PatientRepository(self.db)
        patient = patient_repo.get_by_id(patient_id)
        if not patient:
            raise PatientNotFoundException(patient_id)

        run_id = str(uuid.uuid4())
        agent_run = self._create_run_record(run_id, patient_id)

        logger.info("Agent run started", run_id=run_id, patient_id=patient_id)

        try:
            loop = AgentLoop(client=_get_client(), settings=settings)
            result = await loop.run(patient_id=patient_id, run_id=run_id, db=self.db)
        except Exception as exc:
            logger.error("Agent loop raised unexpected error", run_id=run_id, error=str(exc))
            self._fail_run_record(agent_run, str(exc))
            raise

        self._save_run_result(agent_run, result)

        logger.info(
            "Agent run finished",
            run_id=run_id,
            status=result.status.value,
            completeness=f"{result.completeness_score:.0%}",
            tokens=sum(result.token_usage.values()),
        )

        return result

    def get_run(self, run_id: str) -> AgentRun | None:
        return self.db.get(AgentRun, run_id)

    def list_runs_for_patient(self, patient_id: str) -> list[AgentRun]:
        from sqlalchemy import select
        stmt = (
            select(AgentRun)
            .where(AgentRun.patient_id == patient_id)
            .order_by(AgentRun.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars())

    # ── Internal helpers ─────────────────────────────────────────────────────────

    def _create_run_record(self, run_id: str, patient_id: str) -> AgentRun:
        record = AgentRun(
            id=run_id,
            patient_id=patient_id,
            status=AgentRunStatus.RUNNING.value,
            started_at=datetime.utcnow(),
        )
        self.db.add(record)
        self.db.commit()
        return record

    def _save_run_result(self, record: AgentRun, result: AgentRunResult) -> None:
        record.status = result.status.value
        record.completed_at = datetime.utcnow()
        record.iteration_count = result.final_state.iteration_count
        record.total_tokens_in = result.token_usage.get("input", 0)
        record.total_tokens_out = result.token_usage.get("output", 0)

        # Persist knowledge base + trace as memory snapshot
        snapshot = {
            "knowledge_base": result.knowledge_base.model_dump(mode="json"),
            "trace": [s.model_dump(mode="json") for s in result.trace],
            "escalation_required": result.escalation_required,
            "escalation_reasons": result.escalation_reasons,
            "completeness_score": result.completeness_score,
            "missing_information": result.final_state.missing_information,
        }
        record.memory_snapshot = json.dumps(snapshot, default=str)

        # Plan stored as ordered task names
        completed_tools = [t.tool_name for t in result.final_state.completed_tasks]
        record.plan = json.dumps(completed_tools)

        self.db.commit()
        logger.debug("Agent run record saved", run_id=record.id)

    def _fail_run_record(self, record: AgentRun, error: str) -> None:
        record.status = AgentRunStatus.FAILED.value
        record.completed_at = datetime.utcnow()
        record.error_message = error[:1000]
        self.db.commit()
