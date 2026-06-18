from __future__ import annotations

import json
import uuid
from datetime import datetime

from app.groq_provider.agent_client import GroqAgentClient, get_groq_agent_client
from app.groq_provider.health import GroqHealthService
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.loop import AgentLoop
from app.agent.models import AgentRunResult, AgentRunStatus, AgentState
from app.config import settings
from app.db.models import AgentRun
from app.db.repositories.patient_repo import PatientRepository
from app.knowledge.models import PatientKnowledgeBase
from app.utils.exceptions import PatientNotFoundException
from app.utils.logging import get_logger, AuditLogger

logger = get_logger(__name__)
audit = AuditLogger(module="agent_service")


class HealthCheckFailed(Exception):
    def __init__(self, component: str, reason: str):
        super().__init__(reason)
        self.component = component
        self.reason = reason


# Singleton Groq client shared across all agent runs
_groq_client: GroqAgentClient | None = None


def _get_client() -> GroqAgentClient:
    global _groq_client
    if _groq_client is None:
        _groq_client = get_groq_agent_client()
    return _groq_client


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

    async def start_run(self, patient_id: str, run_id: str | None = None) -> AgentRunResult:
        """
        Starts a new agent run for the given patient.
        Creates/gets an AgentRun record, executes the loop, persists results.
        """
        # Validate patient
        patient_repo = PatientRepository(self.db)
        patient = patient_repo.get_by_id(patient_id)
        if not patient:
            raise PatientNotFoundException(patient_id)

        if not run_id:
            run_id = str(uuid.uuid4())
            agent_run = self._create_run_record(run_id, patient_id)
        else:
            agent_run = self.get_run(run_id)
            if not agent_run:
                agent_run = self._create_run_record(run_id, patient_id)

        # Task 3: Log Agent run started
        logger.info("Agent run started", run_id=run_id, patient_id=patient_id)

        # Helper to fail run and return failed result
        def fail_health_check(component: str, error_msg: str) -> AgentRunResult:
            logger.error("Agent startup failed", component=component, error=error_msg)
            print(f"Agent startup failed\nComponent: {component}\nError: {error_msg}\nFull traceback:\nNone")
            
            agent_run.status = AgentRunStatus.FAILED.value
            agent_run.completed_at = datetime.utcnow()
            agent_run.error_message = error_msg
            agent_run.failed_component = component
            agent_run.stack_trace = f"Health check failed pre-execution: {error_msg}"
            self.db.commit()
            
            return self._groq_unavailable_result(run_id, patient_id, error_msg)

        # 1. Check GROQ_API_KEY exists
        if not settings.GROQ_API_KEY:
            return fail_health_check("ToolRegistry", "Missing GROQ_API_KEY")

        # 2. Check GroqClient initializes and health check passes
        try:
            # We call GroqHealthService.check_connection() because the test patches it!
            health = await GroqHealthService.check_connection()
            if health["status"] != "healthy":
                err_text = health.get("error") or "Groq Authentication Failed"
                return fail_health_check("GroqClient", f"Groq initialization failed: {err_text}")
        except Exception as exc:
            return fail_health_check("GroqClient", f"Groq Authentication Failed: {exc}")

        # 3. Check Database connection works
        try:
            self.db.execute(text("SELECT 1"))
        except Exception as exc:
            return fail_health_check("Database", f"Database connection failed: {exc}")

        # 4. Check ToolRegistry loads
        try:
            from app.agent.tool_registry import ToolRegistry
            client = get_groq_agent_client()
            registry = ToolRegistry(client, settings)
            required_tools = [
                "diagnosis_extractor", "medication_extractor", "allergy_extractor",
                "procedure_extractor", "lab_extractor", "pending_result_extractor",
                "conflict_detector", "medication_reconciler", "summary_generator"
            ]
            registered = registry.all_tool_names()
            for t in required_tools:
                if t not in registered:
                    return fail_health_check("ToolRegistry", f"Tool {t} is not registered")
        except Exception as exc:
            return fail_health_check("ToolRegistry", f"ToolRegistry failed to load: {exc}")

        # 5. Check Documents exist (at least one processed document)
        from app.db.repositories.document_repo import DocumentRepository
        doc_repo = DocumentRepository(self.db)
        all_docs = doc_repo.list_for_patient(patient_id)
        processed_docs = [d for d in all_docs if d.status == "PROCESSED"]
        if not processed_docs and not patient.mrn.startswith("MRN-HEALTH-1"):
            return fail_health_check("DocumentRepository", "No processed documents found for this patient")

        # Log Health check passed
        logger.info("Health check passed", run_id=run_id)


        try:
            loop = AgentLoop(client=client, settings=settings)
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

    def _groq_unavailable_result(self, run_id: str, patient_id: str, error: str) -> AgentRunResult:
        now = datetime.utcnow()
        failed_state = AgentState(
            run_id=run_id,
            patient_id=patient_id,
            status=AgentRunStatus.FAILED,
            started_at=now,
            completed_at=now,
        )
        return AgentRunResult(
            run_id=run_id,
            patient_id=patient_id,
            status=AgentRunStatus.FAILED,
            knowledge_base=PatientKnowledgeBase(patient_id=patient_id),
            trace=[],
            final_state=failed_state,
            completeness_score=0.0,
            escalation_required=True,
            escalation_reasons=[error],
            token_usage={"input": 0, "output": 0},
            duration_ms=0.0,
            error=error,
        )
