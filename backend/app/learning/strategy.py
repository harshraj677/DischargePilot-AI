"""
PromptStrategyEngine — Epsilon-greedy exploration over prompt variants.

Three strategies for hospital course narrative generation:
  A (conservative):   Concise, factual, 2-paragraph format
  B (structured):     Named sections: Presentation, Course, Discharge
  C (evidence_first): Cites source document evidence for each event

Epsilon-greedy: with probability epsilon, randomly explore a non-best
strategy; with probability 1-epsilon, exploit the best-known strategy.
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models import LearningStrategy as LearningStrategyORM
from app.learning.models import PromptStrategy
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Default epsilon for exploration
DEFAULT_EPSILON = 0.20

# Built-in strategy definitions
_BUILTIN_STRATEGIES: List[Dict] = [
    {
        "strategy_id": "strategy_a",
        "name": "Conservative",
        "variant": "conservative",
        "description": "Concise, factual summaries with minimal elaboration. Best for straightforward cases.",
        "prompt_template": (
            "Write a factual, concise 2-paragraph hospital course for this discharge summary. "
            "Paragraph 1: Reason for admission, key findings, and treatment initiated. "
            "Paragraph 2: Clinical response, complications (if any), and reason for discharge. "
            "Use clear, professional language. Expand all abbreviations. "
            "Do not include information not supported by the provided clinical documents."
        ),
    },
    {
        "strategy_id": "strategy_b",
        "name": "Structured",
        "variant": "structured",
        "description": "Organizes hospital course into named sections. Best for complex multi-problem cases.",
        "prompt_template": (
            "Write the hospital course using the following structured sections:\n"
            "**Presentation:** Chief complaint and reason for admission.\n"
            "**Clinical Course:** Day-by-day key events, treatments, and clinical responses.\n"
            "**Complications:** Any complications encountered (or 'None noted').\n"
            "**Discharge Status:** Patient's condition at discharge and reason for discharge.\n"
            "Expand all abbreviations. Cite source documents for key claims. "
            "Do not fabricate clinical information."
        ),
    },
    {
        "strategy_id": "strategy_c",
        "name": "Evidence First",
        "variant": "evidence_first",
        "description": "Cites source documents for every claim. Best for medico-legal settings.",
        "prompt_template": (
            "Write the hospital course where every clinical statement cites its source document. "
            "Format: [Claim] (Source: [document_name], [date if available]). "
            "Group by clinical problem. For each problem: "
            "(1) Initial presentation evidence, (2) Treatment rationale, (3) Outcome. "
            "If information is missing from source documents, state 'Not documented in available records'. "
            "Expand all abbreviations."
        ),
    },
]


class PromptStrategyEngine:
    """
    Manages prompt strategy selection and reward tracking using epsilon-greedy exploration.
    Strategies are persisted to the LearningStrategy table.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._ensure_strategies_exist()

    def _ensure_strategies_exist(self) -> None:
        """Initialize default strategies if they don't exist in the DB."""
        for s in _BUILTIN_STRATEGIES:
            existing = self._db.get(LearningStrategyORM, s["strategy_id"])
            if not existing:
                row = LearningStrategyORM(
                    id=s["strategy_id"],
                    name=s["name"],
                    description=s["description"],
                    prompt_template=s["prompt_template"],
                    total_uses=0,
                    avg_reward=0.0,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                self._db.add(row)
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()

    def get_best_strategy(self) -> PromptStrategy:
        """
        Return the strategy with the highest average reward.
        Falls back to strategy_b (structured) if no data yet.
        """
        rows = self._db.query(LearningStrategyORM).all()
        if not rows:
            return self._builtin_strategy("strategy_b")

        # Among strategies with at least 1 use, find highest reward
        used = [r for r in rows if r.total_uses > 0]
        if not used:
            return self._orm_to_model(rows[0])

        best = max(used, key=lambda r: r.avg_reward)
        return self._orm_to_model(best)

    def select_strategy(self, epsilon: float = DEFAULT_EPSILON) -> PromptStrategy:
        """
        Epsilon-greedy strategy selection.

        With probability epsilon: randomly select any strategy (exploration).
        With probability 1-epsilon: select the best-known strategy (exploitation).

        Args:
            epsilon: Exploration probability (default 0.20).

        Returns:
            Selected PromptStrategy.
        """
        rows = self._db.query(LearningStrategyORM).all()
        if not rows:
            return self._builtin_strategy("strategy_b")

        if random.random() < epsilon:
            # Explore: pick a random non-best strategy
            best = self.get_best_strategy()
            others = [r for r in rows if r.id != best.strategy_id]
            if others:
                chosen = random.choice(others)
                logger.debug(
                    "Epsilon-greedy: exploring strategy",
                    strategy=chosen.name,
                    epsilon=epsilon,
                )
                return self._orm_to_model(chosen)

        # Exploit: use best strategy
        return self.get_best_strategy()

    def update_strategy_reward(self, strategy_id: str, reward: float) -> None:
        """
        Update the running average reward for a strategy.

        Uses incremental mean: new_avg = old_avg + (reward - old_avg) / new_count

        Args:
            strategy_id: The strategy ID to update.
            reward: The reward score from this run (0.0–1.0).
        """
        row = self._db.get(LearningStrategyORM, strategy_id)
        if not row:
            logger.warning("Strategy not found for reward update", strategy_id=strategy_id)
            return

        new_count = row.total_uses + 1
        # Incremental mean update
        new_avg = row.avg_reward + (reward - row.avg_reward) / new_count

        row.total_uses = new_count
        row.avg_reward = round(new_avg, 4)
        row.updated_at = datetime.utcnow()

        try:
            self._db.commit()
            logger.debug(
                "Strategy reward updated",
                strategy_id=strategy_id,
                new_avg=new_avg,
                total_uses=new_count,
            )
        except Exception as exc:
            self._db.rollback()
            logger.error("Failed to update strategy reward", error=str(exc))

    def list_strategies(self) -> List[PromptStrategy]:
        """Return all strategies with their performance statistics."""
        rows = self._db.query(LearningStrategyORM).all()
        return [self._orm_to_model(r) for r in rows]

    def _orm_to_model(self, row: LearningStrategyORM) -> PromptStrategy:
        return PromptStrategy(
            strategy_id=row.id,
            name=row.name,
            prompt_template=row.prompt_template,
            variant=row.name.lower().replace(" ", "_"),
            total_uses=row.total_uses,
            avg_reward=row.avg_reward,
            description=row.description or "",
        )

    def _builtin_strategy(self, strategy_id: str) -> PromptStrategy:
        for s in _BUILTIN_STRATEGIES:
            if s["strategy_id"] == strategy_id:
                return PromptStrategy(
                    strategy_id=s["strategy_id"],
                    name=s["name"],
                    prompt_template=s["prompt_template"],
                    variant=s["variant"],
                    total_uses=0,
                    avg_reward=0.0,
                    description=s["description"],
                )
        return PromptStrategy(
            strategy_id="strategy_b",
            name="Structured",
            prompt_template=_BUILTIN_STRATEGIES[1]["prompt_template"],
            variant="structured",
            total_uses=0,
            avg_reward=0.0,
            description=_BUILTIN_STRATEGIES[1]["description"],
        )
