from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.dependencies import get_db
from app.config import settings

router = APIRouter(prefix="/debug", tags=["Debug"])


@router.get("/agent")
async def debug_agent(db: Session = Depends(get_db)) -> dict:
    # 1. Database connection check
    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception as exc:
        database_status = f"error: {exc}"

    # 2. Groq client connection check
    try:
        from app.groq_provider.agent_client import get_groq_agent_client
        groq_client = get_groq_agent_client()
        groq_ok = await groq_client.health_check()
        groq_status = "ok" if groq_ok else "error: Groq Authentication Failed"
    except Exception as exc:
        groq_status = f"error: {exc}"

    # 3. Tool registry check
    try:
        from app.agent.tool_registry import ToolRegistry
        from app.groq_provider.agent_client import get_groq_agent_client
        client = get_groq_agent_client()
        registry = ToolRegistry(client, settings)
        required_tools = [
            "diagnosis_extractor", "medication_extractor", "allergy_extractor",
            "procedure_extractor", "lab_extractor", "pending_result_extractor",
            "conflict_detector", "medication_reconciler", "summary_generator"
        ]
        registered = registry.all_tool_names()
        missing = [t for t in required_tools if t not in registered]
        if missing:
            registry_status = f"error: missing registered tools {missing}"
        else:
            registry_status = "ok"
    except Exception as exc:
        registry_status = f"error: {exc}"

    # 4. Documents existence check (verify schema works)
    try:
        from app.db.models import Document
        db.query(Document).first()
        documents_status = "ok"
    except Exception as exc:
        documents_status = f"error: {exc}"

    # 5. Planner initialization check
    try:
        from app.agent.planner import AgentPlanner
        from app.groq_provider.agent_client import get_groq_agent_client
        client = get_groq_agent_client()
        planner = AgentPlanner(client, settings)
        planner_status = "ok"
    except Exception as exc:
        planner_status = f"error: {exc}"

    # Agent is ready only if all services are "ok"
    all_ok = (
        database_status == "ok"
        and groq_status == "ok"
        and registry_status == "ok"
        and documents_status == "ok"
        and planner_status == "ok"
    )

    return {
        "database": database_status,
        "tool_registry": registry_status,
        "groq": groq_status,
        "documents": documents_status,
        "planner": planner_status,
        "agent_ready": all_ok,
    }
