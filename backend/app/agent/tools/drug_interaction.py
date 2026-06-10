from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.agent.models import AgentState, AgentTask, ToolResult
from app.agent.prompts import DRUG_INTERACTION_PROMPT
from app.agent.tools.base import BaseTool
from app.claude.agent_client import ClaudeUnavailableError
from app.knowledge.models import ClinicalConflict
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

_TOOL_SCHEMA = {
    "name": "check_drug_interactions",
    "description": "Identify significant drug-drug interactions in discharge medications",
    "input_schema": {
        "type": "object",
        "properties": {
            "interactions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "drugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Names of interacting drugs",
                        },
                        "severity": {"type": "string", "enum": ["critical", "warning"]},
                        "mechanism": {"type": "string"},
                        "consequence": {"type": "string"},
                        "recommendation": {"type": "string"},
                    },
                    "required": ["drugs", "severity", "mechanism", "consequence", "recommendation"],
                },
            },
            "interaction_free": {
                "type": "boolean",
                "description": "True if no significant interactions found",
            },
        },
        "required": ["interactions", "interaction_free"],
    },
}


class DrugInteractionTool(BaseTool):
    name = "drug_interaction_checker"
    description = "Checks drug-drug interactions in the discharge medication list using Claude"

    async def execute(
        self,
        task: AgentTask,
        state: AgentState,
        kb: KnowledgeRepository,
        db: Session,
    ) -> ToolResult:
        start = time.time()

        dis_meds = kb.kb.medications_discharge
        if len(dis_meds) < 2:
            return self._ok_result(
                task=task,
                facts=0,
                findings={"interaction_free": True, "reason": "Fewer than 2 discharge medications"},
                tokens=0,
                duration_ms=0.0,
                notes="Insufficient medications for interaction check",
            )

        med_list = []
        for m in dis_meds:
            parts = [m.name.value]
            if m.dose:
                parts.append(m.dose.value)
            if m.route:
                parts.append(m.route.value)
            if m.frequency:
                parts.append(m.frequency.value)
            med_list.append(" ".join(parts))

        diagnoses_text = ", ".join(d.name.value for d in kb.kb.diagnoses[:5]) or "Not extracted"

        prompt = DRUG_INTERACTION_PROMPT.format(
            medications="\n".join(f"- {m}" for m in med_list),
            diagnoses=diagnoses_text,
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
        interactions_found = 0
        critical_count = 0

        for ix in raw.get("interactions", []):
            try:
                severity = ix.get("severity", "warning")
                description = (
                    f"Drug interaction: {' + '.join(ix['drugs'])} — {ix['consequence']}"
                )
                conflict = ClinicalConflict(
                    conflict_type="drug_interaction",
                    description=description,
                    severity=severity,
                    involved_items=ix.get("drugs", []),
                )
                kb.add_conflict(conflict)
                state.identified_conflicts.append(conflict.conflict_id)
                interactions_found += 1

                if severity == "critical":
                    critical_count += 1
                    state.escalation_reasons.append(
                        f"Critical drug interaction: {ix['drugs']} — {ix['consequence'][:80]}"
                    )
            except Exception as exc:
                logger.warning("Failed to parse drug interaction", error=str(exc))

        if critical_count > 0:
            state.escalation_required = True

        duration_ms = (time.time() - start) * 1000
        state.add_tokens(len(prompt) // 4, tokens)

        return self._ok_result(
            task=task,
            facts=interactions_found,
            findings={
                "interactions_found": interactions_found,
                "critical_interactions": critical_count,
                "interaction_free": bool(raw.get("interaction_free", False)),
            },
            tokens=tokens,
            duration_ms=duration_ms,
            notes=f"Found {interactions_found} drug interactions ({critical_count} critical)",
        )
