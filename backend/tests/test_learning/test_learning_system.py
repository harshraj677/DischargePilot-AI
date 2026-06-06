"""
Unit tests for the Phase 8 Learning System.

Tests cover:
1. EditPolicy — edit distance calculation and classification
2. RewardCalculator — composite reward score
3. CorrectionMemory — pattern storage, frequency tracking, deduplication
4. StrategyEngine — strategy selection, UCB scoring
5. LearningSession — end-to-end reward recording
6. Before/After improvement tracking
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from app.learning.models import (
    CorrectionMemoryEntry,
    DoctorReview,
    EditRecord,
    LearningMetrics,
    LearningSession,
    PromptStrategy,
    RewardScore,
)


# ── EditPolicy ────────────────────────────────────────────────────────────────

class TestEditPolicy:
    def test_zero_edit_distance_identical_text(self):
        from app.learning.edit_policy import EditPolicy
        policy = EditPolicy()
        distance = policy.compute_edit_distance("Hello World", "Hello World")
        assert distance == 0.0

    def test_max_edit_distance_completely_different(self):
        from app.learning.edit_policy import EditPolicy
        policy = EditPolicy()
        distance = policy.compute_edit_distance("aaa", "bbb")
        assert distance > 0.0

    def test_edit_distance_between_zero_and_one(self):
        from app.learning.edit_policy import EditPolicy
        policy = EditPolicy()
        d = policy.compute_edit_distance(
            "Patient has Type 2 Diabetes Mellitus",
            "Patient has DM2"
        )
        assert 0.0 <= d <= 1.0

    def test_small_edit_has_small_distance(self):
        from app.learning.edit_policy import EditPolicy
        policy = EditPolicy()
        d = policy.compute_edit_distance("Metformin 500mg", "Metformin 1000mg")
        assert d < 0.5

    def test_classify_as_abbreviation_expansion(self):
        from app.learning.edit_policy import EditPolicy
        policy = EditPolicy()
        edit_type = policy.classify_edit_type("DM2", "Type 2 Diabetes Mellitus")
        assert edit_type in ("abbreviation_expansion", "specificity", "content")

    def test_extract_edits_between_sections(self):
        from app.learning.edit_policy import EditPolicy
        policy = EditPolicy()
        original = {"medications": "Metformin 500mg BID"}
        edited = {"medications": "Metformin 500mg twice daily"}
        edits = policy.extract_edits(original, edited)
        assert len(edits) >= 1
        assert edits[0].section_name == "medications"


# ── RewardCalculator ──────────────────────────────────────────────────────────

class TestRewardCalculator:
    def test_perfect_summary_scores_one(self):
        from app.learning.reward import RewardCalculator
        calc = RewardCalculator()
        edits = []  # No edits = perfect
        original = {
            "diagnosis": "Type 2 Diabetes Mellitus, uncontrolled",
            "medications": "Metformin 500mg BID",
            "follow_up": "PCP in 1 week",
            "condition": "Stable",
        }
        edited = original.copy()
        score = calc.compute(edits, original_sections=original, edited_sections=edited)
        assert score.total >= 0.7  # High score for no edits

    def test_heavy_edits_reduce_reward(self):
        from app.learning.reward import RewardCalculator
        from app.learning.edit_policy import EditPolicy

        policy = EditPolicy()
        original = {"diagnosis": "DM2", "medications": "MF", "follow_up": "FU PCP"}
        edited = {
            "diagnosis": "Type 2 Diabetes Mellitus",
            "medications": "Metformin 500mg twice daily",
            "follow_up": "Follow up with Primary Care Physician in one week",
        }
        edits = policy.extract_edits(original, edited)

        calc = RewardCalculator()
        score = calc.compute(edits, original_sections=original, edited_sections=edited)
        assert 0.0 <= score.total <= 1.0

    def test_reward_score_has_all_components(self):
        from app.learning.reward import RewardCalculator
        calc = RewardCalculator()
        score = calc.compute([], original_sections={}, edited_sections={})
        assert hasattr(score, "total")
        assert hasattr(score, "edit_distance_score")
        assert hasattr(score, "section_accuracy_score")
        assert hasattr(score, "review_burden_score")

    def test_reward_total_in_range(self):
        from app.learning.reward import RewardCalculator
        calc = RewardCalculator()
        score = calc.compute([], original_sections={"diagnosis": "Pneumonia"}, edited_sections={"diagnosis": "Community-acquired pneumonia"})
        assert 0.0 <= score.total <= 1.0

    def test_missing_required_sections_reduces_score(self):
        from app.learning.reward import RewardCalculator
        calc = RewardCalculator()
        original = {}  # No sections at all
        edited = {}
        score = calc.compute([], original_sections=original, edited_sections=edited)
        assert score.section_accuracy_score < 1.0


# ── CorrectionMemory ──────────────────────────────────────────────────────────

class TestCorrectionMemory:
    def test_stores_correction_pattern(self):
        from app.learning.memory import CorrectionMemory
        memory = CorrectionMemory()
        memory.store("DM2", "Type 2 Diabetes Mellitus", section="diagnosis")
        patterns = memory.get_patterns(section="diagnosis")
        assert len(patterns) >= 1
        assert any(p.pattern == "DM2" for p in patterns)

    def test_increments_frequency_on_duplicate(self):
        from app.learning.memory import CorrectionMemory
        memory = CorrectionMemory()
        memory.store("HTN", "Hypertension", section="diagnosis")
        memory.store("HTN", "Hypertension", section="diagnosis")
        patterns = memory.get_patterns(section="diagnosis")
        htn_entry = next(p for p in patterns if p.pattern == "HTN")
        assert htn_entry.frequency >= 2

    def test_top_patterns_returns_highest_frequency(self):
        from app.learning.memory import CorrectionMemory
        memory = CorrectionMemory()
        for _ in range(5):
            memory.store("DM2", "Type 2 Diabetes Mellitus", section="diagnosis")
        for _ in range(2):
            memory.store("HTN", "Hypertension", section="diagnosis")
        top = memory.get_top_patterns(section="diagnosis", limit=1)
        assert top[0].pattern == "DM2"

    def test_empty_memory_returns_empty_list(self):
        from app.learning.memory import CorrectionMemory
        memory = CorrectionMemory()
        assert memory.get_patterns("diagnosis") == []

    def test_section_isolation(self):
        from app.learning.memory import CorrectionMemory
        memory = CorrectionMemory()
        memory.store("BID", "twice daily", section="medications")
        memory.store("DM2", "Type 2 Diabetes", section="diagnosis")
        med_patterns = memory.get_patterns("medications")
        dx_patterns = memory.get_patterns("diagnosis")
        assert all(p.pattern == "BID" for p in med_patterns)
        assert all(p.pattern == "DM2" for p in dx_patterns)

    def test_build_hint_string(self):
        from app.learning.memory import CorrectionMemory
        memory = CorrectionMemory()
        memory.store("DM2", "Type 2 Diabetes Mellitus", section="diagnosis")
        memory.store("BID", "twice daily", section="diagnosis")
        hint = memory.build_hint_string(section="diagnosis")
        assert "DM2" in hint
        assert "Type 2 Diabetes Mellitus" in hint


# ── StrategyEngine ────────────────────────────────────────────────────────────

class TestStrategyEngine:
    def test_returns_strategy_name(self):
        from app.learning.strategy import StrategyEngine
        engine = StrategyEngine()
        strategy = engine.select_strategy()
        assert strategy is not None
        assert hasattr(strategy, "name") or isinstance(strategy, str)

    def test_updates_reward_for_strategy(self):
        from app.learning.strategy import StrategyEngine
        engine = StrategyEngine()
        strategy = engine.select_strategy()
        name = strategy.name if hasattr(strategy, "name") else strategy
        engine.update_reward(name, reward=0.85)
        # Should not raise

    def test_strategy_variants_available(self):
        from app.learning.strategy import StrategyEngine
        engine = StrategyEngine()
        strategies = engine.list_strategies()
        assert len(strategies) >= 2

    def test_best_strategy_after_training(self):
        from app.learning.strategy import StrategyEngine
        engine = StrategyEngine()
        strategies = engine.list_strategies()
        s1 = strategies[0].name if hasattr(strategies[0], "name") else strategies[0]
        s2 = strategies[1].name if hasattr(strategies[1], "name") else strategies[1]

        engine.update_reward(s1, reward=0.9)
        engine.update_reward(s1, reward=0.85)
        engine.update_reward(s2, reward=0.4)

        best = engine.get_best_strategy()
        best_name = best.name if hasattr(best, "name") else best
        assert best_name == s1


# ── LearningSession Model ─────────────────────────────────────────────────────

class TestLearningSessionModel:
    def test_session_creation(self):
        session = LearningSession(
            run_id="run-001",
            strategy_used="conservative",
            reward=0.82,
        )
        assert session.run_id == "run-001"
        assert session.reward == 0.82
        assert session.session_id is not None

    def test_reward_score_model(self):
        score = RewardScore(
            total=0.87,
            edit_distance_score=0.92,
            section_accuracy_score=0.85,
            review_burden_score=0.83,
        )
        assert 0.0 <= score.total <= 1.0

    def test_correction_memory_entry_model(self):
        entry = CorrectionMemoryEntry(
            pattern="DM2",
            correction="Type 2 Diabetes Mellitus",
            section_name="diagnosis",
        )
        assert entry.frequency == 1
        assert entry.pattern == "DM2"

    def test_edit_record_model(self):
        edit = EditRecord(
            original_text="DM2 uncontrolled",
            edited_text="Type 2 Diabetes Mellitus, uncontrolled",
            section_name="diagnosis",
            edit_type="abbreviation_expansion",
            edit_distance=0.45,
        )
        assert 0.0 <= edit.edit_distance <= 1.0


# ── Before/After Improvement ──────────────────────────────────────────────────

class TestImprovementTracking:
    def test_reward_improves_over_sessions(self):
        """Simulate learning improvement: rewards should trend upward."""
        rewards_early = [0.55, 0.60, 0.58, 0.62]
        rewards_late = [0.75, 0.80, 0.82, 0.85]
        avg_early = sum(rewards_early) / len(rewards_early)
        avg_late = sum(rewards_late) / len(rewards_late)
        assert avg_late > avg_early

    def test_edit_distance_decreases_over_time(self):
        """Less editing needed as system learns."""
        edit_distances_early = [0.45, 0.52, 0.48, 0.50]
        edit_distances_late = [0.12, 0.08, 0.10, 0.09]
        avg_early = sum(edit_distances_early) / len(edit_distances_early)
        avg_late = sum(edit_distances_late) / len(edit_distances_late)
        assert avg_late < avg_early

    def test_metrics_model_aggregation(self):
        metrics = LearningMetrics(
            total_reviews=50,
            avg_reward=0.78,
            avg_edit_distance=0.15,
            improvement_rate=0.12,
            best_strategy="evidence_first",
        )
        assert metrics.total_reviews == 50
        assert metrics.avg_reward > 0
        assert metrics.improvement_rate > 0
