"""
Clinical Document Classifier — Module 3
Two-stage classification: rule-based keyword scoring first,
LLM-assisted (Claude) fallback when confidence is below threshold.
"""
import re
from typing import Dict, Optional

from app.config import settings
from app.models.document import ClassificationResult, PageChunk
from app.models.enums import DocumentType, ClassificationMethod
from app.utils.logging import get_logger

logger = get_logger(__name__)

KEYWORD_RULES: Dict[DocumentType, list] = {
    DocumentType.ADMISSION_NOTE: [
        r"\badmission\s+note\b", r"\badmitting\s+diagnosis\b",
        r"\bchief\s+complaint\b", r"\bhpi\b",
        r"\bhistory\s+of\s+present\s+illness\b", r"\bpast\s+medical\s+history\b",
        r"\bsocial\s+history\b", r"\bfamily\s+history\b",
        r"\bphysical\s+examination\s+on\s+admission\b", r"\badmitted\s+for\b",
        r"\binitial\s+assessment\b", r"\breason\s+for\s+admission\b",
    ],
    DocumentType.PROGRESS_NOTE: [
        r"\bprogress\s+note\b", r"\bdaily\s+note\b",
        r"\bsoap\s+note\b", r"\bsubjective\b",
        r"\bassessment\s+and\s+plan\b", r"\ba/p\b",
        r"\bclinical\s+note\b", r"\binpatient\s+note\b",
        r"\bday\s+\d+\s+of\s+hospitalization\b", r"\bovernight\s+events\b",
        r"\bteam\s+note\b", r"\brounds\b",
    ],
    DocumentType.LAB_REPORT: [
        r"\blaboratory\s+results?\b", r"\blab\s+report\b",
        r"\bcomplete\s+blood\s+count\b", r"\bcbc\b",
        r"\bbasic\s+metabolic\s+panel\b", r"\bbmp\b",
        r"\bcomprehensive\s+metabolic\s+panel\b", r"\bcmp\b",
        r"\bhemoglobin\b", r"\bplatelet\b", r"\bcreatinine\b",
        r"\bglucose\b", r"\bsodium\b", r"\bpotassium\b",
        r"\bwbc\b", r"\brbc\b", r"\bhematocrit\b",
        r"\breference\s+range\b", r"\bspecimen\b", r"\bcollected\s+on\b",
        r"\bpending\s+results?\b",
    ],
    DocumentType.MEDICATION_RECORD: [
        r"\bmedication\s+administration\s+record\b", r"\bmar\b",
        r"\bprescription\b", r"\bpharmacy\b",
        r"\bmedication\s+list\b", r"\bcurrent\s+medications?\b",
        r"\bdose\b.*\bfrequency\b", r"\bromte\b",
        r"\boral\b.*\bdaily\b", r"\bpills?\b",
        r"\btablets?\b", r"\bcapsules?\b",
        r"\bsig\b", r"\bdispense\b", r"\brefill\b",
        r"\badminister(ed)?\b", r"\bscheduled\s+medication\b",
    ],
    DocumentType.DISCHARGE_INSTRUCTION: [
        r"\bdischarge\s+(instruction|summary|planning)\b",
        r"\bafter.?care\s+instruction\b",
        r"\bfollow.up\s+appointment\b",
        r"\bwhen\s+to\s+call\s+your\s+doctor\b",
        r"\bactivity\s+restriction\b",
        r"\bdiet\s+instruction\b",
        r"\bwound\s+care\b",
        r"\byou\s+are\s+being\s+discharged\b",
        r"\breturn\s+to\s+er\b", r"\breturning\s+to\s+home\b",
        r"\bdischarge\s+condition\b",
    ],
}

NEGATIVE_PATTERNS: Dict[DocumentType, list] = {
    DocumentType.LAB_REPORT: [r"\bprogress\s+note\b", r"\badmission\s+note\b"],
    DocumentType.MEDICATION_RECORD: [r"\bprogress\s+note\b", r"\blab\s+report\b"],
}


def _score_text(text: str, patterns: list) -> int:
    score = 0
    text_lower = text.lower()
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        score += len(matches)
    return score


def _apply_negative_patterns(scores: Dict[DocumentType, float], text: str) -> Dict[DocumentType, float]:
    text_lower = text.lower()
    for doc_type, neg_patterns in NEGATIVE_PATTERNS.items():
        for pattern in neg_patterns:
            if re.search(pattern, text_lower):
                scores[doc_type] *= 0.3
    return scores


def classify_by_rules(text: str) -> ClassificationResult:
    if not text or not text.strip():
        return ClassificationResult(
            document_type=DocumentType.UNKNOWN,
            confidence=0.0,
            method=ClassificationMethod.RULE_BASED,
        )

    sample = text[:5000]  # Use first 5000 chars for classification
    raw_scores: Dict[DocumentType, int] = {}

    for doc_type, patterns in KEYWORD_RULES.items():
        raw_scores[doc_type] = _score_text(sample, patterns)

    total = sum(raw_scores.values())
    if total == 0:
        return ClassificationResult(
            document_type=DocumentType.UNKNOWN,
            confidence=0.0,
            method=ClassificationMethod.RULE_BASED,
            scores={k.value: 0.0 for k in raw_scores},
        )

    float_scores = {k: v / total for k, v in raw_scores.items()}
    float_scores = _apply_negative_patterns(float_scores, sample)

    best_type = max(float_scores, key=float_scores.get)
    best_score = float_scores[best_type]

    # Normalize confidence to [0, 1]
    confidence = min(1.0, best_score * 2)  # 0.5 raw score → 1.0 confidence

    return ClassificationResult(
        document_type=best_type,
        confidence=round(confidence, 3),
        method=ClassificationMethod.RULE_BASED,
        scores={k.value: round(v, 3) for k, v in float_scores.items()},
    )


async def classify_by_llm(text: str, filename: str) -> ClassificationResult:
    try:
        from app.gemini.client import GeminiClient, get_gemini_client
        client = get_gemini_client()

        sample = text[:3000]
        valid_types = [t.value for t in DocumentType if t != DocumentType.UNKNOWN]

        prompt = (
            f"Classify this clinical document. Filename: '{filename}'\n\n"
            f"First 3000 characters:\n{sample}\n\n"
            f"Return JSON only:\n"
            f'{{"document_type": "<one of: {", ".join(valid_types)}>", '
            f'"confidence": <0.0-1.0>, "reasoning": "<one sentence>"}}'
        )
        
        raw_text = await client.generate_content(prompt=prompt, model_type="text")

        import json
        raw = raw_text.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)

        doc_type_str = data.get("document_type", "unknown")
        try:
            doc_type = DocumentType(doc_type_str)
        except ValueError:
            doc_type = DocumentType.UNKNOWN

        return ClassificationResult(
            document_type=doc_type,
            confidence=float(data.get("confidence", 0.5)),
            method=ClassificationMethod.LLM_ASSISTED,
            reasoning=data.get("reasoning"),
        )

    except Exception as e:
        logger.warning("LLM classification failed, defaulting to UNKNOWN", error=str(e))
        return ClassificationResult(
            document_type=DocumentType.UNKNOWN,
            confidence=0.0,
            method=ClassificationMethod.LLM_ASSISTED,
            reasoning=f"LLM call failed: {e}",
        )


async def classify_document(
    text: str,
    filename: str,
    declared_type: Optional[DocumentType] = None,
) -> ClassificationResult:
    # If uploader declared the type explicitly — trust it with max confidence
    if declared_type and declared_type != DocumentType.UNKNOWN:
        logger.info("Using user-declared document type", doc_type=declared_type.value)
        return ClassificationResult(
            document_type=declared_type,
            confidence=1.0,
            method=ClassificationMethod.USER_DECLARED,
        )

    # Stage 1: rule-based
    rule_result = classify_by_rules(text)
    logger.info(
        "Rule-based classification",
        filename=filename,
        doc_type=rule_result.document_type.value,
        confidence=rule_result.confidence,
    )

    # Stage 2: LLM fallback if confidence is low
    if rule_result.confidence < settings.GEMINI_CLASSIFICATION_THRESHOLD and settings.GEMINI_API_KEY:
        logger.info("Low confidence — falling back to LLM classification", confidence=rule_result.confidence)
        llm_result = await classify_by_llm(text, filename)
        if llm_result.confidence >= rule_result.confidence:
            return llm_result

    return rule_result
