from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.knowledge.models import PatientKnowledgeBase


class AgentRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"
    TIMED_OUT = "TIMED_OUT"


# Hard cap on how many times the loop will invoke AgentPlanner.replan() in a
# single run — without this, a tool that keeps reporting the same findings
# (or an LLM replanner that keeps proposing tasks) can re-trigger replanning
# every iteration and never reach termination.
MAX_REPLAN_ATTEMPTS = 5


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    tool_name: str
    description: str = ""
    priority: int = Field(default=5, ge=1, le=12)
    status: TaskStatus = TaskStatus.PENDING
    depends_on: List[str] = Field(default_factory=list)
    document_ids: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AgentState(BaseModel):
    """Complete mutable state of one agent run — the single source of truth."""

    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    patient_id: str
    current_goal: str = "Generate a clinically accurate, evidence-grounded discharge summary"
    iteration_count: int = 0
    max_iterations: int = 15

    available_document_ids: List[str] = Field(default_factory=list)
    available_document_types: List[str] = Field(default_factory=list)

    completed_tasks: List[AgentTask] = Field(default_factory=list)
    pending_tasks: List[AgentTask] = Field(default_factory=list)
    failed_tasks: List[AgentTask] = Field(default_factory=list)
    skipped_tasks: List[AgentTask] = Field(default_factory=list)

    identified_conflicts: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    tool_history: List[str] = Field(default_factory=list)

    escalation_required: bool = False
    escalation_reasons: List[str] = Field(default_factory=list)

    # Replan-loop guards (see MAX_REPLAN_ATTEMPTS)
    replan_count: int = 0
    replanned_triggers: List[str] = Field(default_factory=list)

    status: AgentRunStatus = AgentRunStatus.RUNNING
    termination_reason: Optional[str] = None

    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    token_usage: Dict[str, int] = Field(default_factory=lambda: {"input": 0, "output": 0})

    def mark_task_in_progress(self, task: AgentTask) -> None:
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()
        task.attempts += 1

    def mark_task_completed(self, task: AgentTask, result: Dict[str, Any]) -> None:
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.result = result
        self.pending_tasks = [t for t in self.pending_tasks if t.task_id != task.task_id]
        self.completed_tasks.append(task)
        self.tool_history.append(task.tool_name)

    def mark_task_failed(self, task: AgentTask, error: str) -> None:
        # ExecutionEngine.execute() already retries internally up to
        # task.max_attempts times (with backoff) inside a single execute()
        # call, and only calls mark_task_failed() once those retries are
        # exhausted — but it only calls mark_task_in_progress() (which
        # increments task.attempts) once per execute() call. So
        # task.attempts is always 1 here, never >= max_attempts, and the
        # old `if task.attempts >= task.max_attempts` guard silently left
        # every permanently-failed task sitting in pending_tasks forever —
        # which then blocks anything depending on it from ever becoming
        # ready. By the time this method runs, the task is always done
        # (no further automatic retries are coming), so always remove it.
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.utcnow()
        task.error = error
        self.pending_tasks = [t for t in self.pending_tasks if t.task_id != task.task_id]
        self.failed_tasks.append(task)

    def completed_task_names(self) -> List[str]:
        return [t.tool_name for t in self.completed_tasks]

    def has_completed(self, tool_name: str) -> bool:
        return tool_name in self.completed_task_names()

    def has_task(self, tool_name: str) -> bool:
        """
        True if a task for this tool already exists anywhere in the run
        (pending, completed, or failed). Centralized duplicate-task guard —
        every code path that adds tasks (initial plan, replanning, forced
        finalization) must check this before scheduling a tool, otherwise
        the same tool can be scheduled twice under independent code paths.
        """
        return (
            any(t.tool_name == tool_name for t in self.pending_tasks)
            or any(t.tool_name == tool_name for t in self.completed_tasks)
            or any(t.tool_name == tool_name for t in self.failed_tasks)
        )

    def is_task_ready(self, task: AgentTask) -> bool:
        """Return True if all dependencies are satisfied."""
        completed_ids = {t.task_id for t in self.completed_tasks}
        return all(dep_id in completed_ids for dep_id in task.depends_on)

    def add_tokens(self, input_tokens: int, output_tokens: int) -> None:
        self.token_usage["input"] += input_tokens
        self.token_usage["output"] += output_tokens


class TraceStep(BaseModel):
    """Immutable record of one agent reasoning step."""

    step: int
    reasoning: str
    selected_tool: str
    tool_input: Dict[str, Any]
    tool_output: Optional[Dict[str, Any]] = None
    state_changes: str
    next_action: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0
    error: Optional[str] = None
    tokens_used: int = 0


class ToolInput(BaseModel):
    task_id: str
    document_ids: List[str]
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    task_id: str
    tool_name: str
    success: bool
    facts_extracted: int = 0
    findings: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0
    tokens_used: int = 0
    trace_notes: str = ""


class AgentRunResult(BaseModel):
    run_id: str
    patient_id: str
    status: AgentRunStatus
    knowledge_base: PatientKnowledgeBase
    trace: List[TraceStep]
    final_state: AgentState
    completeness_score: float
    escalation_required: bool
    escalation_reasons: List[str]
    token_usage: Dict[str, int]
    duration_ms: float
    error: Optional[str] = None
