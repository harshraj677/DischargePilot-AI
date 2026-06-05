"""
Clinical Metadata Extractor — Module 4
Regex-based extraction of patient name, MRN, dates, and provider.
Every extracted value is paired with an EvidenceRef pointing to source page + excerpt.
"""
import re
from typing import Optional, List

from app.models.document import PageChunk, EvidenceRef, ClinicalMetadata
from app.models.enums import DocumentType
from app.processing.text_cleaner import extract_snippet
from app.utils.logging import get_logger

logger = get_logger(__name__)

# ── Regex patterns ──────────────────────────────────────────────────────────

MRN_PATTERNS = [
    r"MRN[:\s#]+([A-Z0-9][A-Z0-9\-]{2,19})",
    r"Medical\s+Record\s+(?:Number|No\.?|#)[:\s]+([A-Z0-9][A-Z0-9\-]{2,19})",
    r"Patient\s+(?:ID|Number|No\.?|#)[:\s]+([A-Z0-9][A-Z0-9\-]{2,19})",
    r"Record\s+(?:Number|No\.?|#)[:\s]+([A-Z0-9][A-Z0-9\-]{2,19})",
]

PATIENT_NAME_PATTERNS = [
    r"Patient(?:\s+Name)?[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
    r"Name[:\s]+([A-Z][a-z]+,\s+[A-Z][a-z]+(?:\s+[A-Z]\.?)?)",
    r"(?:Patient|Pt\.?)[:\s]+([A-Z][a-z]+,\s+[A-Z][a-z]+)",
]

DATE_PATTERNS_LABELED = {
    "admission_date": [
        r"Admission\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"Date\s+of\s+Admission[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"Admitted[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"Admission\s+Date[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
    ],
    "discharge_date": [
        r"Discharge\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"Date\s+of\s+Discharge[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"Discharged[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"Discharge\s+Date[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
    ],
    "dob": [
        r"(?:Date\s+of\s+Birth|DOB|D\.O\.B\.?)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(?:Birthdate|Birth\s+Date)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(?:Date\s+of\s+Birth|DOB)[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
    ],
    "document_date": [
        r"Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"Report\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"Note\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"Authored[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    ],
}

PROVIDER_PATTERNS = [
    r"(?:Attending|Provider|Physician|Doctor|MD|Dr\.?)[:\s]+(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}(?:,?\s+M\.?D\.?)?)",
    r"Signed\s+by[:\s]+(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
    r"Dr\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
]

FACILITY_PATTERNS = [
    r"(?:Hospital|Medical\s+Center|Health\s+System|Clinic)[:\s]+([A-Z][A-Za-z\s]+(?:Hospital|Medical\s+Center|Health))",
    r"^([A-Z][A-Za-z\s]+(?:Hospital|Medical\s+Center|Healthcare|Clinic))",
]


def _first_regex_match(text: str, patterns: List[str], flags: int = re.IGNORECASE) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match.group(1).strip()
    return None


def _find_match_page(
    pages: List[PageChunk],
    patterns: List[str],
    document_id: str,
    document_name: str,
    document_type: DocumentType,
) -> Optional[EvidenceRef]:
    for page in pages[:5]:  # Search first 5 pages for metadata (most likely location)
        if not page.text:
            continue
        for pattern in patterns:
            match = re.search(pattern, page.text, re.IGNORECASE)
            if match:
                excerpt = extract_snippet(page.text, match.group(0), context_chars=200)
                return EvidenceRef(
                    document_id=document_id,
                    document_name=document_name,
                    document_type=document_type,
                    page_number=page.page_number,
                    excerpt=excerpt[:500],
                )
    return None


def extract_metadata(
    pages: List[PageChunk],
    document_id: str,
    document_name: str,
    document_type: DocumentType,
) -> ClinicalMetadata:
    if not pages:
        return ClinicalMetadata()

    # Combine first 5 pages for metadata extraction (metadata is usually at top)
    header_text = "\n".join(p.text for p in pages[:5] if p.text)
    full_text = "\n".join(p.text for p in pages if p.text)

    metadata = ClinicalMetadata()

    # Patient Name
    name = _first_regex_match(header_text, PATIENT_NAME_PATTERNS)
    if name:
        metadata.patient_name = name
        metadata.patient_name_evidence = _find_match_page(
            pages, PATIENT_NAME_PATTERNS, document_id, document_name, document_type
        )

    # MRN
    mrn = _first_regex_match(header_text, MRN_PATTERNS)
    if mrn:
        metadata.mrn = mrn
        metadata.mrn_evidence = _find_match_page(
            pages, MRN_PATTERNS, document_id, document_name, document_type
        )

    # Dates
    for field_name, patterns in DATE_PATTERNS_LABELED.items():
        value = _first_regex_match(header_text, patterns)
        if value:
            evidence = _find_match_page(pages, patterns, document_id, document_name, document_type)
            if field_name == "admission_date":
                metadata.admission_date = value
                metadata.admission_date_evidence = evidence
            elif field_name == "discharge_date":
                metadata.discharge_date = value
                metadata.discharge_date_evidence = evidence
            elif field_name == "dob":
                metadata.date_of_birth = value
                metadata.dob_evidence = evidence
            elif field_name == "document_date":
                if not metadata.admission_date:
                    metadata.document_date = value
                    metadata.document_date_evidence = evidence

    # Provider
    provider = _first_regex_match(header_text, PROVIDER_PATTERNS)
    if provider:
        metadata.provider_name = provider.strip(" ,")
        metadata.provider_evidence = _find_match_page(
            pages, PROVIDER_PATTERNS, document_id, document_name, document_type
        )

    # Facility
    facility = _first_regex_match(header_text, FACILITY_PATTERNS)
    if facility:
        metadata.facility_name = facility.strip()

    extracted_fields = [
        f for f in ["patient_name", "mrn", "admission_date", "discharge_date", "provider_name"]
        if getattr(metadata, f) is not None
    ]
    logger.info(
        "Metadata extraction complete",
        document_id=document_id,
        extracted_fields=extracted_fields,
    )

    return metadata
