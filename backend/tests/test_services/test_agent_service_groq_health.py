"""
Tests that AgentService.start_run fails fast on a broken Groq connection
instead of running the full extraction pipeline (which would otherwise
produce an identical 403 from every one of the ~10 clinical tools).
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.models import AgentRunStatus
from app.config import settings
from app.db.repositories.patient_repo import PatientRepository
from app.groq_provider.agent_client import GroqAgentClient
from app.groq_provider.config import GroqConfig
from app.models.patient import PatientCreate
from app.services.agent_service import AgentService


@pytest.fixture
def patient(db):
    repo = PatientRepository(db)
    return repo.create(PatientCreate(mrn="MRN-HEALTH-1", first_name="Test", last_name="Patient"))


@pytest.fixture(autouse=True)
def _require_groq_api_key(monkeypatch):
    """The pre-flight key check in start_run reads settings.GROQ_API_KEY
    directly, and ToolRegistry/GroqAgentClient construction reads the
    GroqConfig.API_KEY class attribute (resolved once at import time) — so
    these tests must not depend on whatever (if anything) is in the local
    .env. Patch both, and reset the GroqAgentClient singleton so a fresh
    instance is built with the patched key instead of a previously cached
    instance from another test."""
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-groq-key")
    monkeypatch.setattr(GroqConfig, "API_KEY", "test-groq-key")
    GroqAgentClient._instance = None
    yield
    GroqAgentClient._instance = None


class TestGroqHealthGate:
    @pytest.mark.asyncio
    async def test_unhealthy_groq_short_circuits_without_running_loop(self, db, patient):
        unhealthy = {
            "provider": "groq",
            "status": "failed",
            "authenticated": False,
            "model": "groq-4",
            "error": "403 PERMISSION_DENIED",
        }
        with patch(
            "app.services.agent_service.GroqHealthService.check_connection",
            new=AsyncMock(return_value=unhealthy),
        ), patch("app.services.agent_service.AgentLoop") as mock_loop_cls:
            service = AgentService(db)
            result = await service.start_run(patient.id)

        mock_loop_cls.assert_not_called()
        assert result.status == AgentRunStatus.FAILED
        assert "Groq initialization failed" in result.error
        assert "403 PERMISSION_DENIED" in result.error
        assert result.escalation_required is True

        run = service.get_run(result.run_id)
        assert run.status == AgentRunStatus.FAILED.value
        assert "Groq initialization failed" in run.error_message

    @pytest.mark.asyncio
    async def test_healthy_groq_proceeds_to_loop(self, db, patient):
        healthy = {
            "provider": "groq",
            "status": "healthy",
            "authenticated": True,
            "model": "groq-4",
        }
        with patch(
            "app.services.agent_service.GroqHealthService.check_connection",
            new=AsyncMock(return_value=healthy),
        ), patch("app.services.agent_service.AgentLoop") as mock_loop_cls:
            mock_loop = mock_loop_cls.return_value

            from datetime import datetime

            from app.agent.models import AgentRunResult, AgentState
            from app.knowledge.models import PatientKnowledgeBase

            now = datetime.utcnow()
            state = AgentState(
                run_id="run-1",
                patient_id=patient.id,
                status=AgentRunStatus.COMPLETED,
                started_at=now,
                completed_at=now,
            )
            mock_loop.run = AsyncMock(
                return_value=AgentRunResult(
                    run_id="run-1",
                    patient_id=patient.id,
                    status=AgentRunStatus.COMPLETED,
                    knowledge_base=PatientKnowledgeBase(patient_id=patient.id),
                    trace=[],
                    final_state=state,
                    completeness_score=1.0,
                    escalation_required=False,
                    escalation_reasons=[],
                    token_usage={"input": 0, "output": 0},
                    duration_ms=0.0,
                )
            )

            service = AgentService(db)
            result = await service.start_run(patient.id)

        mock_loop_cls.assert_called_once()
        assert result.status == AgentRunStatus.COMPLETED
        assert result.error is None
