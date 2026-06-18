from __future__ import annotations

from typing import Dict, Optional, Type

from app.groq_provider.agent_client import GroqAgentClient

from app.agent.tools.allergy import AllergyTool
from app.agent.tools.base import BaseTool
from app.agent.tools.conflict_detection import ConflictDetectionTool
from app.agent.tools.diagnosis import DiagnosisTool
from app.agent.tools.drug_interaction import DrugInteractionTool
from app.agent.tools.escalation import EscalationTool
from app.agent.tools.lab import LabTool
from app.agent.tools.medication import MedicationTool
from app.agent.tools.medication_reconciliation import MedicationReconciliationTool
from app.agent.tools.pending_result import PendingResultTool
from app.agent.tools.procedure import ProcedureTool
from app.agent.tools.summary_generator import SummaryGeneratorTool
from app.config import Settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

_REGISTRY: Dict[str, Type[BaseTool]] = {
    "diagnosis_extractor": DiagnosisTool,
    "medication_extractor": MedicationTool,
    "allergy_extractor": AllergyTool,
    "procedure_extractor": ProcedureTool,
    "lab_extractor": LabTool,
    "pending_result_extractor": PendingResultTool,
    "conflict_detector": ConflictDetectionTool,
    # NOTE: "medication_reconciler" is the single canonical name. Do not add
    # an alias (e.g. "medication_reconciliation") here — the replanner's
    # duplicate-task guard matches on tool_name string equality, so a second
    # key pointing at the same tool lets it be scheduled twice and run twice.
    "medication_reconciler": MedicationReconciliationTool,
    "drug_interaction_checker": DrugInteractionTool,
    "escalation_manager": EscalationTool,
    "summary_generator": SummaryGeneratorTool,
}


def known_tool_names() -> set[str]:
    """
    Module-level (instance-free) view of every registered tool name. Used by
    AgentPlanner.replan() to reject hallucinated/misspelled tool_names from
    the LLM before they become permanently-stuck pending tasks.
    """
    return set(_REGISTRY.keys())


class ToolRegistry:
    """
    Instantiates and caches tool instances for the duration of an agent run.
    All tools share the same Groq client and settings.
    """

    def __init__(self, client: GroqAgentClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        self._instances: Dict[str, BaseTool] = {}
        
        # Task 5: Print registered tools during startup
        tools_list = list(_REGISTRY.keys())
        print(f"Registered Tools: {', '.join(tools_list)}")
        logger.info(f"Tool registry initialized with tools: {tools_list}")


    def get(self, tool_name: str) -> Optional[BaseTool]:
        if tool_name not in _REGISTRY:
            return None
        if tool_name not in self._instances:
            cls = _REGISTRY[tool_name]
            self._instances[tool_name] = cls(self._client, self._settings)
        return self._instances[tool_name]

    def all_tool_names(self) -> list[str]:
        return list(_REGISTRY.keys())

    @staticmethod
    def tool_descriptions() -> Dict[str, str]:
        return {
            "diagnosis_extractor": "Extracts principal and secondary diagnoses, hospital course, discharge condition",
            "medication_extractor": "Extracts admission and discharge medications with dose/route/frequency",
            "allergy_extractor": "Extracts allergens, reactions, severity, and NKDA status",
            "procedure_extractor": "Extracts clinical procedures and interventions",
            "lab_extractor": "Extracts lab results, flags abnormal and critical values",
            "pending_result_extractor": "Identifies pending tests and outstanding results at discharge",
            "conflict_detector": "Detects medication-allergy conflicts, contraindications, missing meds",
            "medication_reconciler": "Reconciles admission vs discharge medications, identifies high-risk changes",
            "drug_interaction_checker": "Checks drug-drug interactions in discharge medication list",
            "escalation_manager": "Evaluates escalation criteria and creates structured escalation records",
        }
