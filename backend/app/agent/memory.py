from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.agent.models import AgentState, TraceStep
from app.knowledge.models import PatientKnowledgeBase
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ShortTermMemory:
    """
    Volatile memory for the current agent run.

    Stores:
    - Working notes the agent has generated during the run
    - Intermediate reasoning steps
    - Tool call summaries (ring buffer, last 10)
    """

    MAX_WORKING_NOTES = 50
    MAX_TOOL_SUMMARIES = 10

    def __init__(self) -> None:
        self._working_notes: List[Dict[str, Any]] = []
        self._tool_summaries: List[Dict[str, Any]] = []
        self._flags: Dict[str, Any] = {}

    def add_note(self, category: str, content: str) -> None:
        entry = {"category": category, "content": content, "ts": datetime.utcnow().isoformat()}
        self._working_notes.append(entry)
        if len(self._working_notes) > self.MAX_WORKING_NOTES:
            self._working_notes.pop(0)

    def add_tool_summary(self, tool_name: str, summary: str, success: bool) -> None:
        entry = {
            "tool": tool_name,
            "summary": summary,
            "success": success,
            "ts": datetime.utcnow().isoformat(),
        }
        self._tool_summaries.append(entry)
        if len(self._tool_summaries) > self.MAX_TOOL_SUMMARIES:
            self._tool_summaries.pop(0)

    def set_flag(self, key: str, value: Any) -> None:
        self._flags[key] = value

    def get_flag(self, key: str, default: Any = None) -> Any:
        return self._flags.get(key, default)

    def get_notes(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        if category:
            return [n for n in self._working_notes if n["category"] == category]
        return list(self._working_notes)

    def get_recent_tool_summaries(self) -> List[Dict[str, Any]]:
        return list(self._tool_summaries)

    def to_context_string(self) -> str:
        """Compact representation for injection into Claude prompts."""
        parts = []
        recent = self._tool_summaries[-5:]
        if recent:
            parts.append("Recent tool results:")
            for s in recent:
                status = "✓" if s["success"] else "✗"
                parts.append(f"  {status} {s['tool']}: {s['summary']}")
        if self._flags:
            parts.append("Active flags: " + ", ".join(f"{k}={v}" for k, v in self._flags.items()))
        return "\n".join(parts) if parts else "(empty)"


class LongTermMemory:
    """
    Durable memory persisted to the AgentRun.memory_snapshot column.

    Stores:
    - Patient knowledge base snapshot
    - Tool findings by category
    - Safety findings
    - Evidence references
    """

    def __init__(self) -> None:
        self._knowledge_snapshot: Optional[Dict[str, Any]] = None
        self._tool_findings: Dict[str, Any] = {}
        self._safety_findings: List[Dict[str, Any]] = []
        self._evidence_index: Dict[str, str] = {}  # fact_id -> evidence excerpt

    def snapshot_knowledge_base(self, kb: PatientKnowledgeBase) -> None:
        self._knowledge_snapshot = kb.model_dump(mode="json")
        logger.debug("Knowledge base snapshotted to long-term memory")

    def store_tool_finding(self, tool_name: str, findings: Dict[str, Any]) -> None:
        if tool_name not in self._tool_findings:
            self._tool_findings[tool_name] = []
        self._tool_findings[tool_name].append(
            {"findings": findings, "ts": datetime.utcnow().isoformat()}
        )

    def store_safety_finding(self, severity: str, description: str, details: Dict[str, Any]) -> None:
        self._safety_findings.append(
            {
                "severity": severity,
                "description": description,
                "details": details,
                "ts": datetime.utcnow().isoformat(),
            }
        )
        logger.warning("Safety finding stored", severity=severity, description=description)

    def index_evidence(self, fact_id: str, excerpt: str) -> None:
        self._evidence_index[fact_id] = excerpt

    def retrieve_evidence(self, fact_id: str) -> Optional[str]:
        return self._evidence_index.get(fact_id)

    def get_tool_findings(self, tool_name: str) -> List[Dict[str, Any]]:
        return self._tool_findings.get(tool_name, [])

    def get_critical_safety_findings(self) -> List[Dict[str, Any]]:
        return [f for f in self._safety_findings if f["severity"] == "critical"]

    def has_critical_safety_issue(self) -> bool:
        return any(f["severity"] == "critical" for f in self._safety_findings)

    def to_json(self) -> str:
        payload = {
            "knowledge_snapshot": self._knowledge_snapshot,
            "tool_findings": self._tool_findings,
            "safety_findings": self._safety_findings,
            "evidence_count": len(self._evidence_index),
        }
        return json.dumps(payload, default=str)

    @classmethod
    def from_json(cls, raw: str) -> "LongTermMemory":
        mem = cls()
        try:
            data = json.loads(raw)
            mem._knowledge_snapshot = data.get("knowledge_snapshot")
            mem._tool_findings = data.get("tool_findings", {})
            mem._safety_findings = data.get("safety_findings", [])
        except Exception:
            logger.warning("Failed to deserialize long-term memory — starting fresh")
        return mem


class MemoryManager:
    """
    Unified interface for both memory tiers.
    The agent loop interacts only through this class.
    """

    def __init__(self) -> None:
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()

    def record_tool_result(self, tool_name: str, success: bool, summary: str, findings: Dict[str, Any]) -> None:
        self.short_term.add_tool_summary(tool_name, summary, success)
        self.long_term.store_tool_finding(tool_name, findings)

    def record_safety_issue(self, severity: str, description: str, details: Dict[str, Any]) -> None:
        self.long_term.store_safety_finding(severity, description, details)
        self.short_term.add_note("safety", f"[{severity.upper()}] {description}")

    def get_prompt_context(self) -> str:
        return self.short_term.to_context_string()

    def persist_snapshot(self, kb: PatientKnowledgeBase) -> str:
        self.long_term.snapshot_knowledge_base(kb)
        return self.long_term.to_json()
