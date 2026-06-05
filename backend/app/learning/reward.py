"""
RewardFunction — Computes a composite reward score for each doctor review session.

Formula:
    edit_distance_score = 1.0 - normalized_levenshtein(original, edited)
    section_accuracy_score = check_required_elements_present(edited, section_name)
    review_burden_score = 1.0 - (edit_count / max_expected_edits)
    total = 0.4 * edit_distance_score + 0.35 * section_accuracy_score + 0.25 * review_burden_score

Higher total reward = better quality summary (less editing needed).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.learning.models import RewardScore
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Required elements per section (used for section_accuracy_score)
REQUIRED_SECTION_ELEMENTS: Dict[str, List[str]] = {
    "chief_complaint": ["reason", "presentation", "complaint"],
    "history_of_present_illness": ["onset", "duration", "symptoms"],
    "past_medical_history": ["history", "condition", "diagnosis", "none"],
    "medications": ["dose", "route", "frequency"],
    "discharge_medications": ["dose", "route", "frequency"],
    "allergies": ["allergy", "nkda", "none", "no known"],
    "physical_examination": ["vital", "general", "exam"],
    "laboratory_results": ["lab", "result", "value", "normal", "elevated", "low"],
    "imaging": ["imaging", "x-ray", "ct", "mri", "ultrasound", "not performed", "no imaging"],
    "hospital_course": ["admitted", "treated", "improved", "discharge"],
    "discharge_diagnosis": ["diagnosis", "condition"],
    "discharge_instructions": ["follow", "return", "instructions", "activity"],
    "follow_up": ["follow", "appointment", "clinic", "days", "weeks"],
}

MAX_EXPECTED_EDITS_PER_SECTION = 5.0


def _normalized_levenshtein(s1: str, s2: str) -> float:
    """Compute normalized Levenshtein distance (0.0 = identical, 1.0 = completely different)."""
    if s1 == s2:
        return 0.0
    if not s1:
        return 1.0
    if not s2:
        return 1.0

    # Truncate to avoid O(n²) on long strings
    a = s1[:800]
    b = s2[:800]
    len_a, len_b = len(a), len(b)

    prev = list(range(len_b + 1))
    for i in range(1, len_a + 1):
        curr = [i] + [0] * len_b
        for j in range(1, len_b + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr

    return prev[len_b] / max(len_a, len_b)


def _check_required_elements(text: str, section_name: str) -> float:
    """
    Check what fraction of required elements are present in the section text.
    Returns 0.0–1.0 where 1.0 means all required elements found.
    """
    normalized = section_name.lower().replace(" ", "_").replace("-", "_")
    required = REQUIRED_SECTION_ELEMENTS.get(normalized, [])

    if not required:
        # No required elements defined — give full credit
        return 1.0

    if not text or not text.strip():
        return 0.0

    text_lower = text.lower()
    found = sum(1 for element in required if element.lower() in text_lower)
    return found / len(required)


def _count_edits(original: str, edited: str) -> int:
    """Estimate the number of discrete edits made (word-level)."""
    original_words = set(original.lower().split())
    edited_words = set(edited.lower().split())
    added = len(edited_words - original_words)
    removed = len(original_words - edited_words)
    return (added + removed) // 2


class RewardFunction:
    """
    Computes composite reward scores for doctor review sessions.

    Weights:
        edit_distance_score:   40% — primary quality signal
        section_accuracy_score: 35% — clinical completeness
        review_burden_score:   25% — efficiency measure
    """

    WEIGHT_EDIT_DISTANCE = 0.40
    WEIGHT_SECTION_ACCURACY = 0.35
    WEIGHT_REVIEW_BURDEN = 0.25

    def compute(self, original: str, edited: str, section_name: str) -> RewardScore:
        """
        Compute reward score for a single section review.

        Args:
            original: Original section text before editing.
            edited: Section text after doctor review.
            section_name: The name of the section.

        Returns:
            RewardScore with component scores and total.
        """
        # edit_distance_score: 1.0 = no edits (best), 0.0 = completely rewritten (worst)
        edit_dist = _normalized_levenshtein(original, edited)
        edit_distance_score = max(0.0, 1.0 - edit_dist)

        # section_accuracy_score: fraction of required elements present in edited
        section_accuracy_score = _check_required_elements(edited, section_name)

        # review_burden_score: based on count of discrete edits made
        edit_count = _count_edits(original, edited)
        review_burden_score = max(0.0, 1.0 - (edit_count / MAX_EXPECTED_EDITS_PER_SECTION))

        # Total weighted score
        total = (
            self.WEIGHT_EDIT_DISTANCE * edit_distance_score
            + self.WEIGHT_SECTION_ACCURACY * section_accuracy_score
            + self.WEIGHT_REVIEW_BURDEN * review_burden_score
        )
        total = round(min(1.0, max(0.0, total)), 4)

        return RewardScore(
            total=total,
            edit_distance_score=round(edit_distance_score, 4),
            section_accuracy_score=round(section_accuracy_score, 4),
            review_burden_score=round(review_burden_score, 4),
            breakdown={
                "edit_distance": round(edit_dist, 4),
                "edit_count": edit_count,
                "section": section_name,
            },
        )

    def aggregate_reward(self, reviews: List[RewardScore]) -> float:
        """
        Compute the aggregate reward score across multiple section reviews.

        Returns the simple average of all total scores.
        """
        if not reviews:
            return 0.0
        return round(sum(r.total for r in reviews) / len(reviews), 4)
