from __future__ import annotations

import json
import time
from typing import List

from sqlalchemy.orm import Session

from app.agent.models import AgentState, AgentTask, ToolResult
from app.agent.prompts import CONFLICT_ANALYSIS_PROMPT
from app.agent.tools.base import BaseTool
from app.knowledge.models import ClinicalConflict
from app.knowledge.repository import KnowledgeRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

_TOOL_SCHEMA = {
    "name": "detect_conflicts",
    "description": "Identify clinical conflicts in extracted patient data",
    "input_schema": {
        "type": "object",
        "properties": {
            "conflicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "conflict_type": {
                            "type": "string",
                            "enum": [
                                "medication_allergy",
                                "drug_interaction",
                                "contraindication",
                                "missing_medication",
                                "critical_lab",
                                "other",
                            ],
                        },
                        "severity": {"type": "string", "enum": ["warning", "critical"]},
                        "description": {"type": "string"},
                        "involved_items": {"type": "array", "items": {"type": "string"}},
                        "recommendation": {"type": "string"},
                    },
                    "required": ["conflict_type", "severity", "description", "involved_items", "recommendation"],
                },
            },
            "overall_safety_assessment": {
                "type": "string",
                "enum": ["safe", "review_recommended", "escalate_immediately"],
            },
        },
        "required": ["conflicts", "overall_safety_assessment"],
    },
}


def _format_diagnoses(kb: KnowledgeRepository) -> str:
    lines = []
    for dx in kb.kb.diagnoses[:10]:
        principal = "(PRINCIPAL)" if dx.is_principal else ""
        icd = f" [{dx.icd_code}]" if dx.icd_code else ""
        lines.append(f"- {dx.name.value}{icd} {principal}")
    return "\n".join(lines) if lines else "None extracted"


def _format_allergies(kb: KnowledgeRepository) -> str:
    lines = []
    for a in kb.kb.allergies[:10]:
        reaction = f" → {a.reaction.value}" if a.reaction else ""
        severity = f" [{a.severity}]" if a.severity else ""
        lines.append(f"- {a.allergen.value}{reaction}{severity}")
    return "\n".join(lines) if lines else "None extracted"


def _format_meds(meds: list) -> str:
    lines = []
    for m in meds[:15]:
        dose = f" {m.dose.value}" if m.dose else ""
        route = f" {m.route.value}" if m.route else ""
        freq = f" {m.frequency.value}" if m.frequency else ""
        lines.append(f"- {m.name.value}{dose}{route}{freq}")
    return "\n".join(lines) if lines else "None extracted"


def _format_abnormal_labs(kb: KnowledgeRepository) -> str:
    abnormal = [l for l in kb.kb.lab_results if l.is_abnormal or l.is_critical][:10]
    lines = []
    for lab in abnormal:
        crit = " [CRITICAL]" if lab.is_critical else " [ABNORMAL]"
        unit = f" {lab.unit}" if lab.unit else ""
        ref = f" (ref: {lab.reference_range})" if lab.reference_range else ""
        lines.append(f"- {lab.test_name.value}: {lab.value.value}{unit}{ref}{crit}")
    return "\n".join(lines) if lines else "None"


class ConflictDetectionTool(BaseTool):
    name = "conflict_detector"
    description = "Detects clinical conflicts: medication-allergy, contraindications, missing meds, critical labs"

    async def execute(
        self,
        task: AgentTask,
        state: AgentState,
        kb: KnowledgeRepository,
        db: Session,
    ) -> ToolResult:
        start = time.time()

        # Conflict detection operates on the already-populated KB, no documents needed
        if not kb.kb.diagnoses and not kb.kb.medications_discharge:
            return self._empty_result(task, "Insufficient KB data for conflict detection")

        prompt = CONFLICT_ANALYSIS_PROMPT.format(
            diagnoses=_format_diagnoses(kb),
            allergies=_format_allergies(kb),
            admission_meds=_format_meds(kb.kb.medications_admission),
            discharge_meds=_format_meds(kb.kb.medications_discharge),
            abnormal_labs=_format_abnormal_labs(kb),
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
        except Exception as exc:
            logger.error(f"{self.name} API error", error=str(exc))
            return self._empty_result(task, f"Gemini API error: {exc}")

        raw = self._parse_json_response(response_text) or {}
        tokens = self._count_tokens(response_text)
        conflicts_found = 0
        critical_count = 0

        for c_raw in raw.get("conflicts", []):
            try:
                conflict = ClinicalConflict(
                    conflict_type=c_raw["conflict_type"],
                    description=c_raw["description"],
                    severity=c_raw["severity"],
                    involved_items=c_raw.get("involved_items", []),
                )
                kb.add_conflict(conflict)
                state.identified_conflicts.append(conflict.conflict_id)
                conflicts_found += 1

                if c_raw["severity"] == "critical":
                    critical_count += 1
                    state.escalation_reasons.append(
                        f"Critical conflict: {c_raw['description'][:100]}"
                    )
            except Exception as exc:
                logger.warning("Failed to parse conflict", error=str(exc))

        safety = raw.get("overall_safety_assessment", "review_recommended")
        if safety == "escalate_immediately" or critical_count > 0:
            state.escalation_required = True

        duration_ms = (time.time() - start) * 1000
        state.add_tokens(len(prompt) // 4, tokens)

        return self._ok_result(
            task=task,
            facts=conflicts_found,
            findings={
                "conflicts_detected": conflicts_found,
                "critical_conflicts": critical_count,
                "safety_assessment": safety,
                "escalation_required": state.escalation_required,
            },
            tokens=tokens,
            duration_ms=duration_ms,
            notes=f"Detected {conflicts_found} conflicts ({critical_count} critical). Safety: {safety}",
        )
