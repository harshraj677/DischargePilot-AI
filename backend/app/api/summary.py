from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.gemini.client import GeminiClient, get_gemini_client
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.models import AgentRunStatus
from app.config import Settings, settings
from app.db.models import AgentRun, DischargeReport
from app.dependencies import get_db
from app.knowledge.repository import KnowledgeRepository
from app.safety.engine import SafetyValidationEngine
from app.services.safety_service import SafetyService
from app.services.summary_service import SummaryService
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/summary", tags=["Summary"])

_safety_engine = SafetyValidationEngine()
_anthropic_client: Optional[AsyncAnthropic] = None


def _get_client() -> AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = get_gemini_client()
    return _anthropic_client


def _load_kb_from_run(agent_run: AgentRun) -> KnowledgeRepository:
    """Reconstruct KnowledgeRepository from agent run memory snapshot."""
    if not agent_run.memory_snapshot:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Agent run has no memory snapshot — cannot generate summary",
        )
    try:
        snapshot = json.loads(agent_run.memory_snapshot)
        from app.knowledge.models import PatientKnowledgeBase
        kb_data = snapshot.get("knowledge_base", {})
        kb_model = PatientKnowledgeBase.model_validate(kb_data)
        repo = KnowledgeRepository(patient_id=agent_run.patient_id)
        repo._kb = kb_model
        return repo
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reconstruct knowledge base: {exc}",
        )


# ── Request / Response models ─────────────────────────────────────────────────

class GenerateSummaryRequest(BaseModel):
    run_id: str


class ApproveRequest(BaseModel):
    approved_by: str


class RejectRequest(BaseModel):
    reason: str


class SafetyReportResponse(BaseModel):
    report_id: str
    overall_status: str
    can_generate_summary: bool
    safety_score: float
    completeness_score: float
    blocking_issues: List[str]
    warnings: List[str]
    flag_count: int
    critical_flag_count: int


class SummarySectionResponse(BaseModel):
    name: str
    content: str
    status: str
    flag_count: int


class SummaryResponse(BaseModel):
    summary_id: str
    patient_id: str
    agent_run_id: str
    status: str
    completeness_score: float
    safety_score: float
    generated_at: str
    sections: List[SummarySectionResponse]
    review_flags: List[Dict[str, Any]]
    total_flags: int
    requires_acknowledgment_count: int


# ── Safety endpoints ──────────────────────────────────────────────────────────

@router.get("/patients/{patient_id}/runs/{run_id}/safety", response_model=SafetyReportResponse)
async def get_safety_report(
    patient_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> SafetyReportResponse:
    """Run safety validation on a completed agent run and return the report."""
    agent_run = db.get(AgentRun, run_id)
    if not agent_run or agent_run.patient_id != patient_id:
        raise HTTPException(status_code=404, detail=f"Agent run {run_id} not found")

    if agent_run.status not in (
        AgentRunStatus.COMPLETED.value,
        AgentRunStatus.ESCALATED.value,
    ):
        raise HTTPException(
            status_code=422,
            detail=f"Agent run is not completed (status: {agent_run.status})",
        )

    kb = _load_kb_from_run(agent_run)
    safety_service = SafetyService(db)
    report = await safety_service.validate_agent_run(patient_id, run_id, kb)

    return SafetyReportResponse(
        report_id=report.report_id,
        overall_status=report.overall_status.value,
        can_generate_summary=report.can_generate_summary,
        safety_score=round(report.safety_score, 3),
        completeness_score=round(report.completeness_score, 3),
        blocking_issues=report.blocking_issues,
        warnings=report.warnings,
        flag_count=len(report.review_flags),
        critical_flag_count=len(report.critical_flags),
    )


# ── Summary generation endpoints ──────────────────────────────────────────────

@router.post("/patients/{patient_id}/runs/{run_id}/generate", response_model=SummaryResponse)
async def generate_summary(
    patient_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> SummaryResponse:
    """
    Run safety validation and generate the discharge summary for a completed agent run.

    Returns 422 if the safety gate blocks generation.
    Returns 200 with the full summary and all review flags.
    """
    agent_run = db.get(AgentRun, run_id)
    if not agent_run or agent_run.patient_id != patient_id:
        raise HTTPException(status_code=404, detail=f"Agent run {run_id} not found")

    if agent_run.status not in (
        AgentRunStatus.COMPLETED.value,
        AgentRunStatus.ESCALATED.value,
    ):
        raise HTTPException(
            status_code=422,
            detail=f"Agent run is not completed (status: {agent_run.status})",
        )

    kb = _load_kb_from_run(agent_run)

    # Safety gate
    safety_service = SafetyService(db)
    safety_report = await safety_service.validate_agent_run(patient_id, run_id, kb)

    if not safety_report.can_generate_summary:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Safety validation BLOCKED summary generation",
                "blocking_issues": safety_report.blocking_issues,
                "safety_score": safety_report.safety_score,
            },
        )

    # Generate summary
    summary_service = SummaryService(db, _get_client(), settings)
    summary = await summary_service.generate_and_persist(patient_id, run_id, kb, safety_report)

    return _to_summary_response(summary)


@router.get("/patients/{patient_id}/runs/{run_id}/summary", response_model=SummaryResponse)
async def get_summary(
    patient_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> SummaryResponse:
    """Retrieve the most recent discharge summary for an agent run."""
    summary_service = SummaryService(db, _get_client(), settings)
    summary = summary_service.get_summary_for_run(run_id)
    if not summary:
        raise HTTPException(
            status_code=404,
            detail=f"No discharge summary found for run {run_id}",
        )
    if summary.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Summary not found for this patient")
    return _to_summary_response(summary)


@router.get("/patients/{patient_id}/runs/{run_id}/summary/text")
async def get_summary_text(
    patient_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Return the discharge summary as formatted plain text."""
    from app.summary.formatter import format_as_text
    summary_service = SummaryService(db, _get_client(), settings)
    summary = summary_service.get_summary_for_run(run_id)
    if not summary or summary.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Summary not found")
    return {"text": format_as_text(summary)}


@router.post("/patients/{patient_id}/runs/{run_id}/summary/approve")
async def approve_summary(
    patient_id: str,
    run_id: str,
    body: ApproveRequest,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Mark a discharge summary as approved by a clinician."""
    summary_service = SummaryService(db, _get_client(), settings)
    ok = summary_service.approve_summary(run_id, body.approved_by)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Summary for run {run_id} not found")
    logger.info("Summary approved", run_id=run_id, approved_by=body.approved_by)
    return {"status": "approved", "run_id": run_id}


@router.post("/patients/{patient_id}/runs/{run_id}/summary/reject")
async def reject_summary(
    patient_id: str,
    run_id: str,
    body: RejectRequest,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Reject a discharge summary and log the reason."""
    summary_service = SummaryService(db, _get_client(), settings)
    ok = summary_service.reject_summary(run_id, body.reason)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Summary for run {run_id} not found")
    logger.info("Summary rejected", run_id=run_id, reason=body.reason[:100])
    return {"status": "rejected", "run_id": run_id}


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_summary_response(summary) -> SummaryResponse:
    from app.summary.models import SummaryStatus
    sections = [
        SummarySectionResponse(
            name=s.name,
            content=s.content,
            status=s.status.value,
            flag_count=len(s.section_flags),
        )
        for s in summary.sections
        if s.status != SummaryStatus.MISSING
    ]
    flags = [
        {
            "flag_id": f.flag_id,
            "category": f.category.value,
            "severity": f.severity.value,
            "description": f.description,
            "section": f.affected_section.value,
            "recommendation": f.recommendation,
            "requires_acknowledgment": f.requires_acknowledgment,
        }
        for f in summary.review_flags
    ]
    return SummaryResponse(
        summary_id=summary.summary_id,
        patient_id=summary.patient_id,
        agent_run_id=summary.agent_run_id,
        status=summary.status.value,
        completeness_score=round(summary.completeness_score, 3),
        safety_score=round(summary.safety_score, 3),
        generated_at=summary.generated_at.isoformat(),
        sections=sections,
        review_flags=flags,
        total_flags=len(summary.review_flags),
        requires_acknowledgment_count=len(summary.flags_requiring_acknowledgment),
    )
