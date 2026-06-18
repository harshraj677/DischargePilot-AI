from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.models import AgentRunStatus
from app.dependencies import get_db
from app.services.agent_service import AgentService
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])


# ── Response schemas ──────────────────────────────────────────────────────────

class AgentRunSummary(BaseModel):
    run_id: str
    patient_id: str
    status: str
    iteration_count: int
    total_tokens: int
    completeness_score: Optional[float] = None
    escalation_required: bool = False
    created_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    failed_component: Optional[str] = None


class AgentRunDetail(AgentRunSummary):
    knowledge_base: Optional[Dict[str, Any]] = None
    trace: Optional[List[Dict[str, Any]]] = None
    escalation_reasons: List[str] = []
    missing_information: List[str] = []


class StartRunResponse(BaseModel):
    run_id: str
    patient_id: str
    status: str
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/patients/{patient_id}/runs",
    response_model=StartRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a new agent run",
    description=(
        "Launches the clinical agent loop for the given patient. "
        "All documents must be in PROCESSED status before calling this endpoint. "
        "The agent run is executed synchronously — the response returns when complete."
    ),
)
async def start_agent_run(
    patient_id: str,
    db: Session = Depends(get_db),
) -> StartRunResponse:
    import traceback
    import uuid
    from datetime import datetime
    from app.db.models import AgentRun

    # Create the run record first so it is available even if startup fails
    run_id = str(uuid.uuid4())
    run_record = AgentRun(
        id=run_id,
        patient_id=patient_id,
        status=AgentRunStatus.RUNNING.value,
        started_at=datetime.utcnow(),
    )
    db.add(run_record)
    db.commit()

    service = AgentService(db)
    try:
        result = await service.start_run(patient_id, run_id=run_id)
        if result.status == AgentRunStatus.FAILED:
            return StartRunResponse(
                run_id=run_id,
                patient_id=patient_id,
                status=AgentRunStatus.FAILED.value,
                message=f"Agent run failed: {result.error}",
            )
    except Exception as exc:
        tb = traceback.format_exc()
        failed_component = "AgentExecutor"
        if "Groq" in str(exc) or "groq" in str(exc).lower():
            failed_component = "GroqClient"
        elif "db" in str(exc).lower() or "database" in str(exc).lower():
            failed_component = "Database"
        elif "tool" in str(exc).lower() or "registry" in str(exc).lower():
            failed_component = "ToolRegistry"

        logger.error(
            "Agent startup failed",
            component=failed_component,
            error=str(exc),
            traceback=tb
        )
        print(f"Agent startup failed\nComponent: {failed_component}\nError: {exc}\nFull traceback:\n{tb}")

        run_record.status = AgentRunStatus.FAILED.value
        run_record.completed_at = datetime.utcnow()
        run_record.error_message = str(exc)
        run_record.failed_component = failed_component
        run_record.stack_trace = tb
        db.commit()

        return StartRunResponse(
            run_id=run_id,
            patient_id=patient_id,
            status=AgentRunStatus.FAILED.value,
            message=f"Agent run failed: {exc}",
        )

    return StartRunResponse(
        run_id=result.run_id,
        patient_id=patient_id,
        status=result.status.value,
        message=_run_message(result.status, result.escalation_required),
    )


@router.get(
    "/patients/{patient_id}/runs",
    response_model=List[AgentRunSummary],
    summary="List agent runs for a patient",
)
def list_runs(
    patient_id: str,
    db: Session = Depends(get_db),
) -> List[AgentRunSummary]:
    service = AgentService(db)
    runs = service.list_runs_for_patient(patient_id)
    return [_run_to_summary(r) for r in runs]


@router.get(
    "/runs/{run_id}",
    response_model=AgentRunDetail,
    summary="Get full agent run detail including knowledge base and trace",
)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> AgentRunDetail:
    service = AgentService(db)
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Agent run {run_id} not found")
    return _run_to_detail(run)


@router.get(
    "/runs/{run_id}/knowledge-base",
    response_model=Dict[str, Any],
    summary="Return the extracted knowledge base from an agent run",
)
def get_knowledge_base(
    run_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    service = AgentService(db)
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Agent run {run_id} not found")
    if not run.memory_snapshot:
        raise HTTPException(status_code=404, detail="Knowledge base not yet available")
    snapshot = json.loads(run.memory_snapshot)
    return snapshot.get("knowledge_base", {})


@router.get(
    "/runs/{run_id}/trace",
    response_model=List[Dict[str, Any]],
    summary="Return the full agent reasoning trace",
)
def get_trace(
    run_id: str,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    service = AgentService(db)
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Agent run {run_id} not found")
    if not run.memory_snapshot:
        return []
    snapshot = json.loads(run.memory_snapshot)
    return snapshot.get("trace", [])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_message(status: AgentRunStatus, escalation_required: bool) -> str:
    if status == AgentRunStatus.COMPLETED:
        if escalation_required:
            return "Agent run completed with escalation flag — clinician review required"
        return "Agent run completed successfully — knowledge base ready for summary generation"
    if status == AgentRunStatus.ESCALATED:
        return "Agent run escalated — critical clinical conflicts require clinician review"
    if status == AgentRunStatus.TIMED_OUT:
        return "Agent run timed out — partial knowledge base available"
    return f"Agent run finished with status: {status.value}"


def _run_to_summary(run: Any) -> AgentRunSummary:
    snapshot = {}
    if run.memory_snapshot:
        try:
            snapshot = json.loads(run.memory_snapshot)
        except Exception:
            pass

    return AgentRunSummary(
        run_id=run.id,
        patient_id=run.patient_id,
        status=run.status,
        iteration_count=run.iteration_count,
        total_tokens=run.total_tokens_in + run.total_tokens_out,
        completeness_score=snapshot.get("completeness_score"),
        escalation_required=snapshot.get("escalation_required", False),
        created_at=run.created_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        error_message=run.error_message,
        stack_trace=run.stack_trace,
        failed_component=run.failed_component,
    )


def _run_to_detail(run: Any) -> AgentRunDetail:
    summary = _run_to_summary(run)
    snapshot = {}
    if run.memory_snapshot:
        try:
            snapshot = json.loads(run.memory_snapshot)
        except Exception:
            pass

    return AgentRunDetail(
        **summary.model_dump(),
        knowledge_base=snapshot.get("knowledge_base"),
        trace=snapshot.get("trace"),
        escalation_reasons=snapshot.get("escalation_reasons", []),
        missing_information=snapshot.get("missing_information", []),
    )
