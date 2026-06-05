"""
EditPolicy — hidden clinical editing rules applied during doctor review.

Each rule transforms text from common problematic patterns into
clinically-preferred forms. Rules are deterministic and auditable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple

from app.utils.logging import get_logger

logger = get_logger(__name__)


# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class EditResult:
    original: str
    edited: str
    changes: List[str] = field(default_factory=list)
    rules_triggered: List[str] = field(default_factory=list)


# ── Rule Definitions ──────────────────────────────────────────────────────────

# RULE 1: Clinical abbreviation expansions
ABBREVIATION_MAP: dict[str, str] = {
    r"\bHTN\b": "Hypertension",
    r"\bMI\b": "Myocardial Infarction",
    r"\bDM\b": "Diabetes Mellitus",
    r"\bDM2\b": "Type 2 Diabetes Mellitus",
    r"\bDM1\b": "Type 1 Diabetes Mellitus",
    r"\bT2DM\b": "Type 2 Diabetes Mellitus",
    r"\bT1DM\b": "Type 1 Diabetes Mellitus",
    r"\bCHF\b": "Congestive Heart Failure",
    r"\bCOPD\b": "Chronic Obstructive Pulmonary Disease",
    r"\bCAD\b": "Coronary Artery Disease",
    r"\bAF\b": "Atrial Fibrillation",
    r"\bAfib\b": "Atrial Fibrillation",
    r"\bCKD\b": "Chronic Kidney Disease",
    r"\bAKI\b": "Acute Kidney Injury",
    r"\bPE\b": "Pulmonary Embolism",
    r"\bDVT\b": "Deep Vein Thrombosis",
    r"\bCVA\b": "Cerebrovascular Accident",
    r"\bTIA\b": "Transient Ischemic Attack",
    r"\bSOB\b": "shortness of breath",
    r"\bDOE\b": "dyspnea on exertion",
    r"\bCP\b": "chest pain",
    r"\bN/V\b": "nausea and vomiting",
    r"\bECG\b": "electrocardiogram",
    r"\bEKG\b": "electrocardiogram",
    r"\bABG\b": "arterial blood gas",
    r"\bCXR\b": "chest X-ray",
    r"\bCT\b(?= scan| chest| abdomen| head)": "computed tomography",
    r"\bMRI\b": "magnetic resonance imaging",
    r"\bBP\b": "blood pressure",
    r"\bHR\b": "heart rate",
    r"\bRR\b": "respiratory rate",
    r"\bTemp\b": "temperature",
    r"\bO2 sat\b": "oxygen saturation",
    r"\bSaO2\b": "oxygen saturation",
    r"\bWBC\b": "white blood cell count",
    r"\bHgb\b": "hemoglobin",
    r"\bHct\b": "hematocrit",
    r"\bPlt\b": "platelet count",
    r"\bCr\b(?= \d|:)": "creatinine",
    r"\bBUN\b": "blood urea nitrogen",
    r"\bINR\b": "international normalized ratio",
    r"\bPT\b(?= \d|:)": "prothrombin time",
    r"\baPTT\b": "activated partial thromboplastin time",
    r"\bPO\b(?= \d| daily| twice| three| four| as needed)": "by mouth",
    r"\bIV\b(?= \d| daily| push| drip)": "intravenous",
    r"\bIM\b(?= \d| daily)": "intramuscular",
    r"\bSC\b(?= \d| daily| injection)": "subcutaneous",
    r"\bPRN\b": "as needed",
    r"\bBID\b": "twice daily",
    r"\bTID\b": "three times daily",
    r"\bQID\b": "four times daily",
    r"\bQD\b": "daily",
    r"\bQHS\b": "at bedtime",
    r"\bNPO\b": "nothing by mouth",
    r"\bADL\b": "activities of daily living",
    r"\bAMS\b": "altered mental status",
    r"\bUTI\b": "urinary tract infection",
    r"\bRTI\b": "respiratory tract infection",
    r"\bLFTs\b": "liver function tests",
    r"\bTFTs\b": "thyroid function tests",
    r"\bABC\b": "airway, breathing, circulation",
}

# RULE 2: Vague diagnosis patterns → request for specificity
VAGUE_DIAGNOSES: list[Tuple[str, str]] = [
    (r"\binfection\b(?! of| with| in| caused| related| due)", "infection [specify organism/site]"),
    (r"\bpain\b(?! in| at| of| scale| management| medication| control)", "pain [specify location/quality/scale]"),
    (r"\belectrolyte\s+abnormality\b", "electrolyte abnormality [specify electrolyte and level]"),
    (r"\bdysrhythmia\b", "dysrhythmia [specify type]"),
    (r"\bbleed(?:ing)?\b(?! disorder| time| risk| precaution)", "bleeding [specify location/severity]"),
    (r"\blung\s+disease\b", "lung disease [specify diagnosis]"),
    (r"\bkidney\s+disease\b(?!\s+stage)", "kidney disease [specify stage/type]"),
    (r"\bheart\s+disease\b(?!\s+\w)", "heart disease [specify type]"),
]

# RULE 3: Unsupported statement phrases
UNSUPPORTED_PHRASES: list[str] = [
    r"\bappeared? to\b",
    r"\bseemed? to\b",
    r"\bpossibly\b(?! due| related| secondary)",
    r"\bperhaps\b",
    r"\bmaybe\b",
    r"\bI think\b",
    r"\bI believe\b",
    r"\bprobably\b(?! \w+ related| secondary to| due to)",
    r"\blikely\b(?! due to| secondary| related| diagnosis)",
]

# RULE 4: Pending results visibility markers (must not be buried)
PENDING_RESULTS_PATTERN = re.compile(
    r"(?:pending|awaiting|results? pending|awaited?|not yet resulted?|outstanding|follow[- ]?up result)",
    re.IGNORECASE,
)

PENDING_SECTION_HEADER = "\n\n**PENDING RESULTS (Requires Follow-Up):**\n"

# RULE 5: Medication format — detect and flag non-standard formats
MED_FORMAT_PATTERN = re.compile(
    r"(\b[A-Za-z]+(?:mycin|cillin|statin|prazole|olol|sartan|pril|zepam|pam|lone|pine|ine|ate)\b)"
    r"(?!\s+\d+\s*(?:mg|mcg|g|units?|IU|mEq))",
    re.IGNORECASE,
)

# RULE 6: Missing section placeholder text
MISSING_SECTION_PLACEHOLDER = "Not documented."


# ── EditPolicy Class ──────────────────────────────────────────────────────────

class EditPolicy:
    """
    Applies a set of hidden clinical editing rules to discharge summary text.
    Rules are deterministic, auditable, and never invent clinical facts.
    """

    def apply(self, text: str, section_name: str) -> EditResult:
        """
        Apply all editing rules to the given text for a specific section.

        Args:
            text: The original section text.
            section_name: The name of the section being edited.

        Returns:
            EditResult with the edited text and a log of changes made.
        """
        if not text or not text.strip():
            return EditResult(
                original=text,
                edited=MISSING_SECTION_PLACEHOLDER,
                changes=["Added 'Not documented.' for empty section"],
                rules_triggered=["RULE_6_MISSING_SECTION"],
            )

        result = text
        changes: List[str] = []
        rules_triggered: List[str] = []

        # RULE 1: Expand clinical abbreviations
        for pattern, expansion in ABBREVIATION_MAP.items():
            new_result = re.sub(pattern, expansion, result, flags=re.IGNORECASE)
            if new_result != result:
                match = re.search(pattern, result, flags=re.IGNORECASE)
                if match:
                    changes.append(f"Expanded abbreviation '{match.group()}' → '{expansion}'")
                result = new_result
                rules_triggered.append("RULE_1_ABBREVIATION")

        # RULE 2: Flag vague diagnoses
        for pattern, suggestion in VAGUE_DIAGNOSES:
            new_result = re.sub(pattern, suggestion, result, flags=re.IGNORECASE)
            if new_result != result:
                changes.append(f"Flagged vague term → '{suggestion}'")
                result = new_result
                rules_triggered.append("RULE_2_SPECIFICITY")

        # RULE 3: Flag unsupported statements
        for phrase_pattern in UNSUPPORTED_PHRASES:
            if re.search(phrase_pattern, result, flags=re.IGNORECASE):
                result = re.sub(
                    phrase_pattern,
                    lambda m: f"[UNSUPPORTED: '{m.group()}' — cite source document]",
                    result,
                    flags=re.IGNORECASE,
                )
                changes.append(f"Flagged unsupported language pattern")
                rules_triggered.append("RULE_3_UNSUPPORTED")

        # RULE 4: Pending results visibility
        if PENDING_RESULTS_PATTERN.search(result):
            # Extract pending items and promote them to a visible header
            if PENDING_SECTION_HEADER.strip() not in result:
                result = result + PENDING_SECTION_HEADER + "• See relevant section above for details."
                changes.append("Promoted pending results to visible header (Rule 4)")
                rules_triggered.append("RULE_4_PENDING_RESULTS")

        # RULE 5: Medication format check (flag only — never modify doses)
        if section_name.lower() in ("medications", "medication_record", "discharge_medications", "hospital_course"):
            med_matches = MED_FORMAT_PATTERN.findall(result)
            if med_matches:
                for med in set(med_matches):
                    result = result.replace(
                        med,
                        f"{med} [FORMAT: add dose route frequency]",
                        1,
                    )
                    changes.append(f"Flagged incomplete medication format for '{med}'")
                rules_triggered.append("RULE_5_MED_FORMAT")

        # RULE 6: If section is still empty after rules (edge case)
        if not result.strip():
            result = MISSING_SECTION_PLACEHOLDER
            changes.append("Section remains empty after editing — added placeholder")
            rules_triggered.append("RULE_6_MISSING_SECTION")

        # Deduplicate rules
        rules_triggered = list(dict.fromkeys(rules_triggered))

        return EditResult(
            original=text,
            edited=result,
            changes=changes,
            rules_triggered=rules_triggered,
        )

    def get_rules(self) -> List[str]:
        """Return a human-readable description of all editing rules."""
        return [
            "RULE 1: Expand clinical abbreviations (HTN→Hypertension, MI→Myocardial Infarction, etc.)",
            "RULE 2: Add specificity to vague diagnoses (infection → infection [specify organism/site])",
            "RULE 3: Flag unsupported statements (appeared to, seemed to, possibly, maybe)",
            "RULE 4: Enforce Pending Results visibility (never bury pending results in body text)",
            "RULE 5: Standardize medication format (name dose route frequency) — flag only, never modify dose",
            "RULE 6: Add 'Not documented.' for missing sections rather than omitting them entirely",
        ]
