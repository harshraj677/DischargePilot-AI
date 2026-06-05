from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    TOOL_RETRIED = "tool_retried"
    REPLAN_TRIGGERED = "replan_triggered"
    SAFETY_VALIDATION_STARTED = "safety_validation_started"
    SAFETY_VALIDATION_COMPLETED = "safety_validation_completed"
    SUMMARY_GENERATION_STARTED = "summary_generation_started"
    SUMMARY_GENERATION_COMPLETED = "summary_generation_completed"
    ESCALATION_TRIGGERED = "escalation_triggered"
    TERMINATION_CONDITION_MET = "termination_condition_met"


class TimelineEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    run_id: str
    patient_id: str
    tool_name: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: Optional[float] = None


class ToolActivityStats(BaseModel):
    tool_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: float = 0.0
    total_tokens: int = 0
    total_facts_extracted: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    @property
    def avg_duration_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_duration_ms / self.total_calls


class SafetyEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    patient_id: str
    validator_name: str
    severity: str
    finding_count: int
    flag_count: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentDecision(BaseModel):
    """Captures a planning decision made by AgentPlanner."""
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    step: int
    reasoning: str
    selected_tool: Optional[str] = None
    tasks_added: List[str] = Field(default_factory=list)
    tasks_removed: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentTrace(BaseModel):
    """Complete observability record for one agent run."""

    run_id: str
    patient_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    timeline: List[TimelineEvent] = Field(default_factory=list)
    tool_stats: Dict[str, ToolActivityStats] = Field(default_factory=dict)
    safety_events: List[SafetyEvent] = Field(default_factory=list)
    decisions: List[AgentDecision] = Field(default_factory=list)

    total_iterations: int = 0
    total_tokens_used: int = 0
    total_facts_extracted: int = 0
    total_duration_ms: float = 0.0
    termination_reason: Optional[str] = None

    def add_event(self, event: TimelineEvent) -> None:
        self.timeline.append(event)

    def update_tool_stats(
        self,
        tool_name: str,
        success: bool,
        duration_ms: float,
        tokens: int,
        facts: int,
    ) -> None:
        if tool_name not in self.tool_stats:
            self.tool_stats[tool_name] = ToolActivityStats(tool_name=tool_name)
        stats = self.tool_stats[tool_name]
        stats.total_calls += 1
        stats.total_duration_ms += duration_ms
        stats.total_tokens += tokens
        stats.total_facts_extracted += facts
        if success:
            stats.successful_calls += 1
        else:
            stats.failed_calls += 1
