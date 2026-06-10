from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.agent.models import AgentState, AgentTask, ToolResult
from app.agent.prompts import MEDICATION_RECONCILIATION_PROMPT
from app.agent.tools.base import BaseTool
from app.claude.agent_client import ClaudeUnavailableError
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

_TOOL_SCHEMA = {
    "name": "reconcile_medications",
    "description": "Compare admission and discharge medications and identify changes",
    "input_schema": {
        "type": "object",
        "properties": {
            "reconciliation": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "medication_name": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["CONTINUED", "DOSE_CHANGED", "DISCONTINUED", "NEW", "ROUTE_CHANGED"],
                        },
                        "admission_details": {"type": "string"},
                        "discharge_details": {"type": "string"},
                        "change_reason": {"type": "string"},
                        "requires_patient_education": {"type": "boolean"},
                    },
                    "required": ["medication_name", "status", "requires_patient_education"],
                },
            },
            "high_risk_changes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Medication names with concerning changes requiring clinician attention",
            },
            "summary": {"type": "string"},
        },
        "required": ["reconciliation", "high_risk_changes", "summary"],
    },
}


def _format_med_list(meds: list) -> str:
    lines = []
    for m in meds:
        parts = [m.name.value]
        if m.dose:
            parts.append(m.dose.value)
        if m.route:
            parts.append(m.route.value)
        if m.frequency:
            parts.append(m.frequency.value)
        if m.indication:
            parts.append(f"(for {m.indication})")
        lines.append("- " + " ".join(parts))
    return "\n".join(lines) if lines else "None documented"


class MedicationReconciliationTool(BaseTool):
    name = "medication_reconciler"
    description = "Reconciles admission vs discharge medications and identifies high-risk changes"

    async def execute(
        self,
        task: AgentTask,
        state: AgentState,
        kb: KnowledgeRepository,
        db: Session,
    ) -> ToolResult:
        start = time.time()

        adm_meds = kb.kb.medications_admission
        dis_meds = kb.kb.medications_discharge

        if not adm_meds and not dis_meds:
            return self._empty_result(task, "No medications in knowledge base to reconcile")

        diagnoses_text = ", ".join(d.name.value for d in kb.kb.diagnoses[:5]) or "Not yet extracted"

        prompt = MEDICATION_RECONCILIATION_PROMPT.format(
            admission_meds=_format_med_list(adm_meds),
            discharge_meds=_format_med_list(dis_meds),
        )

        try:
            import json
            prompt_with_schema = f"""{prompt}

Please output ONLY valid JSON matching the following schema:
{json.dumps(_TOOL_SCHEMA['input_schema'])}"""
            response_text = await self.client.generate_content(
                prompt=prompt_with_schema,
                model_type="text",
            )
        except ClaudeUnavailableError as exc:
            logger.error(f"{self.name} Claude unavailable", error=str(exc))
            return self._claude_unavailable_result(task, state, exc)
        except Exception as exc:
            logger.error(f"{self.name} API error", error=str(exc))
            return self._empty_result(task, f"Claude API error: {exc}")

        raw = self._parse_json_response(response_text) or {}
        tokens = self._count_tokens(response_text)

        reconciled = raw.get("reconciliation", [])
        high_risk = raw.get("high_risk_changes", [])
        summary = raw.get("summary", "")

        changed = [r for r in reconciled if r.get("status") != "CONTINUED"]
        discontinued = [r for r in reconciled if r.get("status") == "DISCONTINUED"]
        new_meds = [r for r in reconciled if r.get("status") == "NEW"]

        # Flag high-risk changes for escalation
        if high_risk:
            state.escalation_reasons.append(
                f"High-risk medication changes: {', '.join(high_risk[:3])}"
            )

        # Update change_reason on discharge meds in KB
        for rec in reconciled:
            med_name = rec.get("medication_name", "").lower()
            for med in kb.kb.medications_discharge:
                if med.name.value.lower() == med_name:
                    med.is_changed_at_discharge = rec["status"] in ("DOSE_CHANGED", "ROUTE_CHANGED")
                    med.change_reason = rec.get("change_reason")

        duration_ms = (time.time() - start) * 1000
        state.add_tokens(len(prompt) // 4, tokens)

        return self._ok_result(
            task=task,
            facts=len(reconciled),
            findings={
                "total_reconciled": len(reconciled),
                "changed": len(changed),
                "discontinued": len(discontinued),
                "new_at_discharge": len(new_meds),
                "high_risk_changes": high_risk,
                "reconciliation_summary": summary,
            },
            tokens=tokens,
            duration_ms=duration_ms,
            notes=f"Reconciled {len(reconciled)} medications. {len(changed)} changed. "
                  f"High-risk: {len(high_risk)}",
        )
