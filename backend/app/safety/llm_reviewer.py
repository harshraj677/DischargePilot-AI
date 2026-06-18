from __future__ import annotations

import time
from typing import List

from app.groq_provider.agent_client import GroqAgentClient, GroqUnavailableError
from app.knowledge.repository import KnowledgeRepository
from app.models.enums import SafetySeverity
from app.safety.llm_review_prompt import CLINICAL_SAFETY_REVIEW_PROMPT
from app.safety.models import (
    ReviewFlag,
    ReviewFlagCategory,
    SafetyFinding,
    SectionName,
    ValidationResult,
)
from app.utils.json_parsing import parse_json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)

_GROQ_MAX_TOKENS = 2000

_SEVERITY_MAP = {
    "HIGH": SafetySeverity.HIGH,
    "MEDIUM": SafetySeverity.MEDIUM,
    "LOW": SafetySeverity.LOW,
    "INFO": SafetySeverity.INFO,
}

# Matches the category vocabulary in the JSON output contract in
# llm_review_prompt.py exactly: conflict|missing_data|pending_result|
# medication|lab|guideline|other.
_CATEGORY_MAP = {
    "conflict": ReviewFlagCategory.CONFLICT,
    "missing_data": ReviewFlagCategory.MISSING_DATA,
    "pending_result": ReviewFlagCategory.PENDING_RESULT,
    "medication": ReviewFlagCategory.MEDICATION,
    "lab": ReviewFlagCategory.LAB,
    "guideline": ReviewFlagCategory.GUIDELINE,
    "other": ReviewFlagCategory.OTHER,
}
_DEFAULT_CATEGORY = ReviewFlagCategory.OTHER

_CATEGORY_TO_SECTION = {
    ReviewFlagCategory.CONFLICT: SectionName.DISCHARGE_MEDICATIONS,
    ReviewFlagCategory.MISSING_DATA: SectionName.GLOBAL,
    ReviewFlagCategory.PENDING_RESULT: SectionName.PENDING_RESULTS,
    ReviewFlagCategory.MEDICATION: SectionName.DISCHARGE_MEDICATIONS,
    ReviewFlagCategory.LAB: SectionName.LAB_RESULTS,
    ReviewFlagCategory.GUIDELINE: SectionName.GLOBAL,
    ReviewFlagCategory.OTHER: SectionName.GLOBAL,
}


class LLMClinicalSafetyReviewer:
    """
    LLM-driven clinical documentation QA pass, run alongside (not instead
    of) the deterministic validators in app/safety/validators/. Implements
    the spec in llm_review_prompt.py: minimize false positives, never
    invent conflicts, never flag guideline-concordant therapy, group
    related findings, and only let HIGH severity + High confidence
    findings require clinician acknowledgment.

    Never raises — Groq failures or unparseable output degrade to an
    empty (passed) result so this is always safe to run alongside the
    deterministic validators without risking the rest of the safety pass.
    """

    name = "llm_clinical_reviewer"

    def __init__(self, client: GroqAgentClient) -> None:
        self._client = client

    async def review(self, kb: KnowledgeRepository) -> ValidationResult:
        start = time.time()
        prompt = CLINICAL_SAFETY_REVIEW_PROMPT.format(kb_context=kb.to_agent_context())

        try:
            raw = await self._client.generate_content(
                prompt=prompt,
                model_type="text",
                config={"max_output_tokens": _GROQ_MAX_TOKENS},
            )
        except GroqUnavailableError as exc:
            logger.error("LLM clinical reviewer: Groq unavailable", error=str(exc))
            return self._empty_result(start, f"LLM reviewer unavailable: {exc}")
        except Exception as exc:
            logger.error("LLM clinical reviewer: API error", error=str(exc))
            return self._empty_result(start, f"LLM reviewer error: {exc}")

        parsed = parse_json_response(raw)
        if not parsed:
            logger.warning("LLM clinical reviewer: could not parse response")
            return self._empty_result(start, "LLM reviewer returned unparseable output")

        findings: List[SafetyFinding] = []
        flags: List[ReviewFlag] = []
        worst = SafetySeverity.INFO

        for raw_finding in parsed.get("findings", []):
            try:
                # Spec: "Never generate findings without evidence" / "If
                # evidence is insufficient, generate no finding." Enforced
                # here too (not just in the prompt) so a finding is always
                # dropped if the model didn't cite anything, regardless of
                # whether it complied with the instruction.
                evidence = [str(e).strip() for e in (raw_finding.get("evidence") or []) if str(e).strip()]
                if not evidence:
                    logger.debug("LLM clinical reviewer: dropping finding with no evidence", title=raw_finding.get("title"))
                    continue

                sev = _SEVERITY_MAP.get(str(raw_finding.get("severity", "INFO")).upper(), SafetySeverity.INFO)
                category = _CATEGORY_MAP.get(
                    str(raw_finding.get("category", "other")).lower(),
                    _DEFAULT_CATEGORY,
                )
                confidence = str(raw_finding.get("confidence", "Moderate")).strip().title()
                if confidence not in ("High", "Moderate", "Low"):
                    confidence = "Moderate"

                title = (raw_finding.get("title") or "").strip()
                explanation = (raw_finding.get("explanation") or "").strip()
                recommendation = (raw_finding.get("recommendation") or "").strip()
                description = f"{title}: {explanation}" if title else explanation
                section = _CATEGORY_TO_SECTION.get(category, SectionName.GLOBAL)

                findings.append(SafetyFinding(
                    validator=self.name,
                    severity=sev,
                    description=description,
                    affected_section=section,
                    confidence=confidence,
                    evidence=evidence,
                ))

                # Spec: "Only HIGH severity AND High confidence should
                # require acknowledgment." The model also self-reports a
                # requires_acknowledgment field, but it's not trusted as
                # authoritative — this invariant is recomputed here so it
                # holds even if the model's own field is wrong.
                requires_ack = sev == SafetySeverity.HIGH and confidence == "High"
                flags.append(ReviewFlag(
                    category=category,
                    severity=sev,
                    description=description,
                    affected_section=section,
                    recommendation=recommendation or "Review this finding before approving the summary.",
                    requires_acknowledgment=requires_ack,
                    source_documents=[],
                ))

                if sev == SafetySeverity.HIGH:
                    worst = SafetySeverity.HIGH
                elif sev == SafetySeverity.MEDIUM and worst != SafetySeverity.HIGH:
                    worst = SafetySeverity.MEDIUM
            except Exception as exc:
                logger.warning("LLM clinical reviewer: skipping malformed finding", error=str(exc))

        duration_ms = (time.time() - start) * 1000
        logger.info(
            "LLM clinical review complete",
            findings=len(findings),
            llm_safety_score=parsed.get("overall_safety_score"),
            llm_completeness_score=parsed.get("completeness_score"),
            llm_high_count=parsed.get("high_findings_count"),
            llm_medium_count=parsed.get("medium_findings_count"),
            llm_low_count=parsed.get("low_findings_count"),
            llm_info_count=parsed.get("info_findings_count"),
            duration_ms=round(duration_ms),
        )

        return ValidationResult(
            validator_name=self.name,
            passed=worst != SafetySeverity.HIGH,
            severity=worst,
            findings=findings,
            review_flags=flags,
            execution_time_ms=duration_ms,
        )

    def _empty_result(self, start: float, error: str) -> ValidationResult:
        return ValidationResult(
            validator_name=self.name,
            passed=True,
            severity=SafetySeverity.INFO,
            execution_time_ms=(time.time() - start) * 1000,
            error=error,
        )
