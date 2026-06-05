"""
LearningService — Orchestrates the full learning cycle:
  1. Load summary from DB
  2. Select prompt strategy (epsilon-greedy)
  3. Run DoctorReviewerAgent
  4. Compute RewardScore for each section
  5. Store corrections in CorrectionMemory
  6. Update strategy rewards
  7. Persist LearningRun to DB
  8. Return DoctorReview
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from anthropic import AsyncAnthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import DischargeReport, LearningRun as LearningRunORM
from app.learning.memory import CorrectionMemory
from app.learning.models import DoctorReview, LearningMetrics, LearningMetricsDateEntry, RewardScore
from app.learning.reviewer import DoctorReviewerAgent
from app.learning.reward import RewardFunction
from app.learning.strategy import PromptStrategyEngine
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LearningService:
    """
    High-level service that coordinates the entire learning cycle
    for a given agent run.
    """

    def __init__(self, db: Session, client: Optional[AsyncAnthropic] = None) -> None:
        self._db = db
        self._client = client or AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._reward_fn = RewardFunction()
        self._strategy_engine = PromptStrategyEngine(db)
        self._memory = CorrectionMemory(db)
        self._reviewer = DoctorReviewerAgent(self._client)

    async def run_review_cycle(self, run_id: str) -> DoctorReview:
        """
        Execute a full doctor review cycle for the given agent run.

        Args:
            run_id: The agent run ID (must have an associated DischargeReport).

        Returns:
            DoctorReview with edited sections, notes, and reward scores.

        Raises:
            ValueError: If the run has no associated discharge report.
        """
        # 1. Load the discharge report (summary)
        report = (
            self._db.query(DischargeReport)
            .filter(DischargeReport.agent_run_id == run_id)
            .order_by(DischargeReport.created_at.desc())
            .first()
        )

        if not report:
            raise ValueError(f"No discharge report found for run_id={run_id}")

        # Extract sections from summary JSON
        sections: Dict[str, str] = {}
        if report.summary_json:
            try:
                summary_data = json.loads(report.summary_json)
                raw_sections = summary_data.get("sections", [])
                for s in raw_sections:
                    if isinstance(s, dict):
                        sections[s.get("name", "unknown")] = s.get("content", "")
            except Exception as exc:
                logger.warning("Failed to parse summary JSON", run_id=run_id, error=str(exc))

        if not sections:
            sections = {"hospital_course": "No summary content available."}

        # 2. Select strategy (epsilon-greedy)
        strategy = self._strategy_engine.select_strategy(epsilon=0.20)
        logger.info("Strategy selected", strategy=strategy.name, run_id=run_id)

        # 3. Get correction hints from memory for each section
        all_hints = []
        for section_name in sections.keys():
            hint = self._memory.get_prompt_hints(section_name)
            if hint:
                all_hints.append(hint)
        combined_hint = "\n".join(all_hints[:3]) if all_hints else ""

        # 4. Run the doctor reviewer
        doctor_review = await self._reviewer.review_summary(
            run_id=run_id,
            sections=sections,
            strategy_name=strategy.name,
            prompt_hint=combined_hint,
        )

        # 5. Compute reward scores per section
        section_rewards: List[RewardScore] = []
        for section_name, edited_content in doctor_review.edited_sections.items():
            original_content = sections.get(section_name, "")
            reward = self._reward_fn.compute(original_content, edited_content, section_name)
            section_rewards.append(reward)

            # Store corrections in memory
            if reward.edit_distance_score < 0.9:  # Significant edits were made
                self._memory.store_correction(
                    pattern=f"Section {section_name} quality below threshold",
                    correction=f"Applied {strategy.name} strategy improvements",
                    section=section_name,
                    frequency_increment=1,
                )

        # 6. Aggregate reward
        aggregate = self._reward_fn.aggregate_reward(section_rewards)
        if section_rewards:
            avg_reward_score = section_rewards[0]
            avg_reward_score.total = aggregate
            doctor_review.reward_score = avg_reward_score
        else:
            doctor_review.reward_score = RewardScore(
                total=aggregate,
                edit_distance_score=1.0,
                section_accuracy_score=0.5,
                review_burden_score=1.0,
                breakdown={},
            )

        # 7. Update strategy rewards
        self._strategy_engine.update_strategy_reward(strategy.strategy_id, aggregate)

        # 8. Persist LearningRun to DB
        learning_run = LearningRunORM(
            id=doctor_review.review_id,
            run_id=run_id,
            strategy_id=strategy.strategy_id,
            reward_total=aggregate,
            edit_distance_score=doctor_review.reward_score.edit_distance_score,
            section_accuracy_score=doctor_review.reward_score.section_accuracy_score,
            review_burden_score=doctor_review.reward_score.review_burden_score,
            review_notes=doctor_review.review_notes[:2000],
            created_at=datetime.utcnow(),
        )
        try:
            self._db.add(learning_run)
            self._db.commit()
        except Exception as exc:
            self._db.rollback()
            logger.error("Failed to persist learning run", error=str(exc), run_id=run_id)

        logger.info(
            "Review cycle complete",
            run_id=run_id,
            strategy=strategy.name,
            reward=aggregate,
        )

        return doctor_review

    def get_metrics(self) -> LearningMetrics:
        """
        Compute aggregate learning metrics from all stored LearningRun records.

        Returns:
            LearningMetrics with totals, averages, and session-by-date data.
        """
        runs = self._db.query(LearningRunORM).order_by(LearningRunORM.created_at).all()

        if not runs:
            return LearningMetrics(total_reviews=0)

        total = len(runs)
        avg_reward = sum(r.reward_total for r in runs) / total
        avg_edit_dist = sum(r.edit_distance_score for r in runs) / total

        # Improvement rate: compare first third vs last third
        third = max(1, total // 3)
        early_avg = sum(r.reward_total for r in runs[:third]) / third
        late_avg = sum(r.reward_total for r in runs[-third:]) / third
        improvement_rate = max(0.0, late_avg - early_avg)

        # Best strategy
        strategies = self._strategy_engine.list_strategies()
        best_strategy = None
        if strategies:
            used = [s for s in strategies if s.total_uses > 0]
            if used:
                best_strategy = max(used, key=lambda s: s.avg_reward).strategy_id

        # Sessions by date
        date_map: dict = {}
        for run in runs:
            date_key = run.created_at.strftime("%b %d")
            if date_key not in date_map:
                date_map[date_key] = {"rewards": [], "count": 0}
            date_map[date_key]["rewards"].append(run.reward_total)
            date_map[date_key]["count"] += 1

        sessions_by_date = [
            LearningMetricsDateEntry(
                date=date,
                avg_reward=round(sum(data["rewards"]) / len(data["rewards"]), 4),
                count=data["count"],
            )
            for date, data in date_map.items()
        ]

        return LearningMetrics(
            total_reviews=total,
            avg_reward=round(avg_reward, 4),
            avg_edit_distance=round(avg_edit_dist, 4),
            improvement_rate=round(improvement_rate, 4),
            best_strategy=best_strategy,
            sessions_by_date=sessions_by_date,
        )

    def get_strategies(self):
        """Return all prompt strategies with performance stats."""
        return self._strategy_engine.list_strategies()

    def list_reviews(self, limit: int = 50) -> List[dict]:
        """Return recent learning run records as dicts."""
        runs = (
            self._db.query(LearningRunORM)
            .order_by(LearningRunORM.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "review_id": r.id,
                "run_id": r.run_id,
                "strategy_used": r.strategy_id,
                "reward_score": {
                    "total": r.reward_total,
                    "edit_distance_score": r.edit_distance_score,
                    "section_accuracy_score": r.section_accuracy_score,
                    "review_burden_score": r.review_burden_score,
                    "breakdown": {},
                },
                "review_notes": r.review_notes or "",
                "edited_sections": {},
                "draft_summary_id": None,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ]
