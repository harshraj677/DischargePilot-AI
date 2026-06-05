from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.agent.models import AgentRunStatus, AgentState, AgentTask, ToolResult
from app.agent.tools.base import BaseTool
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EscalationTool(BaseTool):
    name = "escalation_manager"
    description = "Evaluates escalation criteria and creates structured escalation records"

    async def execute(
        self,
        task: AgentTask,
        state: AgentState,
        kb: KnowledgeRepository,
        db: Session,
    ) -> ToolResult:
        start = time.time()

        escalation_triggers = []
        severity = "none"

        # 1. Critical conflicts in KB
        critical_conflicts = [c for c in kb.kb.conflicts if c.severity == "critical" and not c.resolved]
        if critical_conflicts:
            severity = "critical"
            for c in critical_conflicts:
                escalation_triggers.append(
                    f"[CRITICAL CONFLICT] {c.conflict_type}: {c.description[:120]}"
                )

        # 2. Missing critical fields
        missing = kb.get_missing_critical_fields()
        if missing:
            severity = severity if severity == "critical" else "warning"
            escalation_triggers.append(
                f"[MISSING CRITICAL DATA] {', '.join(missing)}"
            )

        # 3. Agent state escalation reasons
        for reason in state.escalation_reasons:
            if reason not in escalation_triggers:
                escalation_triggers.append(f"[AGENT FLAG] {reason}")

        # 4. Critical lab values
        critical_labs = [l for l in kb.kb.lab_results if l.is_critical]
        if critical_labs:
            severity = "critical"
            lab_names = ", ".join(l.test_name.value for l in critical_labs[:5])
            escalation_triggers.append(f"[CRITICAL LABS] {lab_names}")

        # 5. Mark missing info in KB
        for field in missing:
            kb.mark_missing(field)

        requires_escalation = len(escalation_triggers) > 0

        if requires_escalation:
            state.escalation_required = True
            state.status = AgentRunStatus.ESCALATED
            for trigger in escalation_triggers:
                if trigger not in state.escalation_reasons:
                    state.escalation_reasons.append(trigger)
            logger.warning(
                "Agent escalation triggered",
                severity=severity,
                triggers=len(escalation_triggers),
                patient_id=state.patient_id,
            )
        else:
            logger.info("Escalation evaluation: no escalation required", patient_id=state.patient_id)

        duration_ms = (time.time() - start) * 1000
        completeness = kb.completeness_score()

        return self._ok_result(
            task=task,
            facts=0,
            findings={
                "escalation_required": requires_escalation,
                "severity": severity,
                "trigger_count": len(escalation_triggers),
                "triggers": escalation_triggers,
                "completeness_score": round(completeness, 3),
                "missing_critical_fields": missing,
            },
            tokens=0,
            duration_ms=duration_ms,
            notes=(
                f"Escalation {'REQUIRED' if requires_escalation else 'not required'}. "
                f"Severity: {severity}. KB completeness: {completeness:.0%}"
            ),
        )
