"""
DoctorReviewerAgent — AI simulation of a senior hospitalist physician
reviewing discharge summaries for completeness, clarity, and safety.

Uses AsyncAnthropic with tool_use for structured output.
Never invents clinical facts — focuses on language quality only.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic

from app.config import settings
from app.learning.edit_policy import EditPolicy
from app.learning.models import DoctorReview, EditRecord, RewardScore
from app.utils.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a senior hospitalist physician with 20 years of clinical experience.
Your role is to review AI-generated discharge summaries and improve their quality.

CRITICAL CONSTRAINTS:
- You MUST NEVER invent, fabricate, or assume any clinical facts not present in the summary
- You focus ONLY on language quality: clarity, completeness of documentation, formatting, and professional tone
- You expand abbreviations, add specificity to vague diagnoses, flag unsupported statements
- You never modify medication doses, diagnoses, or lab values — only flag formatting issues
- You identify pending results and ensure they are prominently documented
- You use "Not documented." for sections that are missing content

YOUR EDITING PHILOSOPHY:
1. A good discharge summary is factual, complete, and requires no guesswork from the reader
2. Every clinical claim should be attributable to a source document
3. Abbreviations are barriers to communication — expand them
4. Vague terms create medico-legal risk — add specificity markers
5. Pending results must be prominently visible to the receiving physician

When reviewing, you will:
- Edit each section to meet these standards
- Provide brief review notes explaining your reasoning
- Never add clinical content that wasn't in the original
"""

REVIEW_TOOL = {
    "name": "submit_review",
    "description": "Submit the completed discharge summary review with edited sections and notes",
    "input_schema": {
        "type": "object",
        "properties": {
            "edited_sections": {
                "type": "object",
                "description": "Map of section_name -> edited content. Include only sections you changed.",
                "additionalProperties": {"type": "string"},
            },
            "review_notes": {
                "type": "string",
                "description": "Brief overall review notes (2-4 sentences). What was improved and why.",
            },
            "edit_rationale": {
                "type": "array",
                "description": "List of specific edits made and the rule/reason for each.",
                "items": {"type": "string"},
            },
        },
        "required": ["edited_sections", "review_notes", "edit_rationale"],
    },
}


class DoctorReviewerAgent:
    """
    AI doctor reviewer that simulates a senior hospitalist reviewing
    a discharge summary and applying clinical editing standards.
    """

    def __init__(self, client: Optional[AsyncAnthropic] = None) -> None:
        self._client = client or AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._edit_policy = EditPolicy()

    async def review_summary(
        self,
        run_id: str,
        sections: Dict[str, str],
        strategy_name: str = "structured",
        prompt_hint: str = "",
    ) -> DoctorReview:
        """
        Review a discharge summary and return a DoctorReview with edited sections.

        Args:
            run_id: The agent run ID this review applies to.
            sections: Dict of section_name -> section_content.
            strategy_name: The prompt strategy variant used for this generation.
            prompt_hint: Optional correction hints from CorrectionMemory.

        Returns:
            DoctorReview with edited_sections, review_notes, and reward scores.
        """
        # First apply deterministic edit policy rules
        pre_edited: Dict[str, str] = {}
        all_edit_records: List[EditRecord] = []

        for section_name, content in sections.items():
            edit_result = self._edit_policy.apply(content, section_name)
            pre_edited[section_name] = edit_result.edited
            if edit_result.changes:
                for change in edit_result.changes:
                    all_edit_records.append(
                        EditRecord(
                            original_text=content[:500],
                            edited_text=edit_result.edited[:500],
                            section_name=section_name,
                            edit_type="policy_rule",
                            edit_distance=self._compute_distance(content, edit_result.edited),
                        )
                    )

        # Build review prompt
        sections_text = "\n\n".join(
            f"=== {name.upper().replace('_', ' ')} ===\n{content}"
            for name, content in pre_edited.items()
        )

        user_message = f"""Please review this discharge summary and submit your edits using the submit_review tool.

{f"CORRECTION HINTS FROM MEMORY:\\n{prompt_hint}\\n\\n" if prompt_hint else ""}
DISCHARGE SUMMARY TO REVIEW:
{sections_text}

Focus on:
1. Any remaining abbreviations that should be expanded
2. Any vague or unsupported statements
3. Missing required elements for each section
4. Overall clarity and completeness
"""

        # Call Claude with tool_use
        edited_sections: Dict[str, str] = dict(pre_edited)
        review_notes = "Review completed using policy rules."
        edit_rationale: List[str] = [r.edit_type for r in all_edit_records]

        try:
            response = await self._client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
                tools=[REVIEW_TOOL],
                tool_choice={"type": "auto"},
            )

            # Extract tool use result
            for block in response.content:
                if block.type == "tool_use" and block.name == "submit_review":
                    tool_input: Dict[str, Any] = block.input
                    ai_edits = tool_input.get("edited_sections", {})
                    if ai_edits:
                        edited_sections.update(ai_edits)
                    review_notes = tool_input.get("review_notes", review_notes)
                    ai_rationale = tool_input.get("edit_rationale", [])
                    edit_rationale.extend(ai_rationale)
                    break

        except Exception as exc:
            logger.warning(
                "LLM reviewer call failed — using policy-only edits",
                run_id=run_id,
                error=str(exc),
            )

        return DoctorReview(
            run_id=run_id,
            edited_sections=edited_sections,
            review_notes=review_notes,
            strategy_used=strategy_name,
        )

    def _compute_distance(self, original: str, edited: str) -> float:
        """Compute normalized Levenshtein distance between two strings."""
        if not original and not edited:
            return 0.0
        if not original or not edited:
            return 1.0

        # Truncate to prevent O(n²) on very long strings
        max_len = 500
        a = original[:max_len]
        b = edited[:max_len]

        len_a, len_b = len(a), len(b)
        if len_a == 0:
            return 1.0
        if len_b == 0:
            return 1.0

        matrix = [[0] * (len_b + 1) for _ in range(len_a + 1)]
        for i in range(len_a + 1):
            matrix[i][0] = i
        for j in range(len_b + 1):
            matrix[0][j] = j

        for i in range(1, len_a + 1):
            for j in range(1, len_b + 1):
                cost = 0 if a[i - 1] == b[j - 1] else 1
                matrix[i][j] = min(
                    matrix[i - 1][j] + 1,
                    matrix[i][j - 1] + 1,
                    matrix[i - 1][j - 1] + cost,
                )

        lev = matrix[len_a][len_b]
        return lev / max(len_a, len_b)
