"""
Clinical Text Cleaning Engine — Module 5
Multi-stage pipeline that normalizes extracted PDF text while preserving
medical terminology, medication names, lab values, and numeric data.
"""
import re
from typing import List

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Medical abbreviations that must NOT be altered
PROTECTED_ABBREVIATIONS = {
    "BID", "TID", "QID", "QD", "PRN", "SQ", "IV", "IM", "PO", "SL",
    "NPO", "AC", "PC", "HS", "STAT", "ASAP", "HPI", "PMH", "FHx",
    "SOB", "CP", "HTN", "DM", "CAD", "CHF", "COPD", "CVA", "TIA",
    "MI", "PE", "DVT", "UTI", "URI", "BP", "HR", "RR", "SpO2", "O2",
    "CBC", "BMP", "CMP", "LFT", "PT", "PTT", "INR", "WBC", "RBC",
    "Hgb", "Hct", "MCV", "MCH", "PLT", "BUN", "Cr", "Na", "K", "Cl",
    "CO2", "Mg", "Ca", "Phos", "ALT", "AST", "ALP", "GGT", "LDH",
    "ECG", "EKG", "CXR", "CT", "MRI", "US", "ABG", "EEG", "EMG",
    "HEENT", "CV", "RESP", "ABD", "GU", "MSK", "NEURO", "DERM",
    "mg", "mcg", "mEq", "mmol", "mL", "L", "dL", "g", "kg",
}


def _remove_control_characters(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    text = re.sub(r"�", " ", text)
    return text


def _normalize_unicode(text: str) -> str:
    replacements = {
        "–": "-", "—": "-", "’": "'", "‘": "'",
        "“": '"', "”": '"', "°": " degrees ",
        "µ": "u", "α": "alpha", "β": "beta",
        "≥": ">=", "≤": "<=", "×": "x",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def _fix_ocr_artifacts(text: str) -> str:
    # Fix common OCR digit/letter confusions only in clear numeric contexts
    text = re.sub(r"(?<!\w)l(?=\d)", "1", text)  # leading l before digit → 1
    text = re.sub(r"(?<=\d)l(?!\w)", "1", text)  # trailing l after digit → 1
    # Fix broken hyphenated words at line ends
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
    return text


def _normalize_whitespace(text: str) -> str:
    # Normalize tabs to spaces
    text = text.replace("\t", " ")
    # Collapse multiple spaces (but not newlines)
    text = re.sub(r"[  ]{2,}", " ", text)
    # Collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove trailing whitespace on each line
    text = re.sub(r" +\n", "\n", text)
    return text.strip()


def _detect_and_remove_repeated_header_footer(text: str, min_frequency: int = 3) -> str:
    lines = text.split("\n")
    if len(lines) < 10:
        return text

    # Count line frequency — lines appearing too many times are likely headers/footers
    from collections import Counter
    line_counts = Counter(line.strip() for line in lines if line.strip())
    repeated = {
        line
        for line, count in line_counts.items()
        if count >= min_frequency and len(line) < 120 and len(line) > 3
    }

    if not repeated:
        return text

    # Filter repeated lines but keep at most one occurrence
    seen: set = set()
    filtered: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped in repeated:
            if stripped not in seen:
                seen.add(stripped)
                filtered.append(line)
            # else: skip the duplicate
        else:
            filtered.append(line)

    return "\n".join(filtered)


def _fix_broken_sentences(text: str) -> str:
    # Join lines that are clearly continuations (lowercase letter at line start)
    text = re.sub(r"(?<=[a-z,;])\n(?=[a-z])", " ", text)
    return text


def _preserve_structured_data(text: str) -> str:
    # Ensure lab values with units stay on one line
    # e.g., "Hemoglobin\n12.4 g/dL" → "Hemoglobin: 12.4 g/dL"
    text = re.sub(
        r"(Hemoglobin|Hematocrit|Platelets?|WBC|BUN|Creatinine|Sodium|Potassium|Glucose|HbA1c)\n(\d+\.?\d*)",
        r"\1: \2",
        text,
        flags=re.IGNORECASE,
    )
    return text


def clean_page_text(text: str) -> str:
    if not text or not text.strip():
        return ""

    pipeline = [
        _remove_control_characters,
        _normalize_unicode,
        _fix_ocr_artifacts,
        _normalize_whitespace,
        _fix_broken_sentences,
        _preserve_structured_data,
    ]

    result = text
    for stage in pipeline:
        result = stage(result)

    return result


def clean_document_text(full_text: str) -> str:
    if not full_text or not full_text.strip():
        return ""

    result = full_text
    pipeline = [
        _remove_control_characters,
        _normalize_unicode,
        _fix_ocr_artifacts,
        _normalize_whitespace,
        _detect_and_remove_repeated_header_footer,
        _fix_broken_sentences,
        _preserve_structured_data,
    ]
    for stage in pipeline:
        result = stage(result)

    return result


def extract_snippet(text: str, keyword: str, context_chars: int = 200) -> str:
    """Extract a snippet of text around a keyword for evidence references."""
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return text[:context_chars] if len(text) > context_chars else text

    start = max(0, idx - context_chars // 2)
    end = min(len(text), idx + len(keyword) + context_chars // 2)
    snippet = text[start:end].strip()

    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"

    return snippet
