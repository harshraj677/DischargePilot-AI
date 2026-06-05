"""
Pydantic v2 models for the Phase 8 Learning System.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.utcnow()


# ── Edit Record ───────────────────────────────────────────────────────────────

class EditRecord(BaseModel):
    """Represents a single edit made by the AI doctor reviewer."""
    original_text: str
    edited_text: str
    section_name: str
    edit_type: str  # "abbreviation_expansion" | "specificity" | "formatting" | "completeness" | "flagged_phrase"
    edit_distance: float  # Normalized Levenshtein distance 0.0–1.0


# ── Reward Score ──────────────────────────────────────────────────────────────

class RewardScore(BaseModel):
    """Composite reward score for a doctor review session."""
    total: float = Field(ge=0.0, le=1.0)
    edit_distance_score: float = Field(ge=0.0, le=1.0, description="1.0 = no edits needed")
    section_accuracy_score: float = Field(ge=0.0, le=1.0, description="Required elements present")
    review_burden_score: float = Field(ge=0.0, le=1.0, description="1.0 = minimal burden")
    breakdown: Dict[str, float] = Field(default_factory=dict)


# ── Doctor Review ─────────────────────────────────────────────────────────────

class DoctorReview(BaseModel):
    """Output of a complete doctor review cycle."""
    review_id: str = Field(default_factory=_new_id)
    run_id: str
    draft_summary_id: Optional[str] = None
    edited_sections: Dict[str, str] = Field(default_factory=dict)
    review_notes: str = ""
    reward_score: Optional[RewardScore] = None
    strategy_used: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)


# ── Correction Memory Entry ───────────────────────────────────────────────────

class CorrectionMemoryEntry(BaseModel):
    """A stored correction pattern for future use as a prompt hint."""
    id: Optional[str] = Field(default_factory=_new_id)
    pattern: str                    # The phrase/abbreviation to correct
    correction: str                 # The corrected form
    section_name: str               # Which section this applies to
    frequency: int = 1              # How often this correction has been applied
    last_seen: datetime = Field(default_factory=_utcnow)


# ── Prompt Strategy ───────────────────────────────────────────────────────────

class PromptStrategy(BaseModel):
    """A prompt variant used by the strategy engine."""
    strategy_id: str = Field(default_factory=_new_id)
    name: str
    prompt_template: str
    variant: str  # "conservative" | "structured" | "evidence_first"
    total_uses: int = 0
    avg_reward: float = 0.0
    description: str = ""


# ── Learning Session ──────────────────────────────────────────────────────────

class LearningSession(BaseModel):
    """A single learning run record."""
    session_id: str = Field(default_factory=_new_id)
    run_id: str
    strategy_used: str
    reward: float
    created_at: datetime = Field(default_factory=_utcnow)


# ── Learning Metrics ──────────────────────────────────────────────────────────

class LearningMetricsDateEntry(BaseModel):
    date: str
    avg_reward: float
    count: int


class LearningMetrics(BaseModel):
    """Aggregated learning system performance metrics."""
    total_reviews: int = 0
    avg_reward: float = 0.0
    avg_edit_distance: float = 0.0
    improvement_rate: float = 0.0
    best_strategy: Optional[str] = None
    sessions_by_date: List[LearningMetricsDateEntry] = Field(default_factory=list)
