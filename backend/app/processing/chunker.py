"""
Text Chunker — creates semantic chunks from extracted pages.
Primary strategy: page-level chunks (preserves page references for evidence).
Secondary strategy: section-header splitting within long pages.
"""
import re
import uuid
from typing import List

from app.models.document import PageChunk, KnowledgeChunk, EvidenceRef
from app.models.enums import DocumentType
from app.utils.logging import get_logger

logger = get_logger(__name__)

CLINICAL_SECTION_HEADERS = re.compile(
    r"^(?:"
    r"CHIEF COMPLAINT|HISTORY OF PRESENT ILLNESS|HPI|"
    r"PAST MEDICAL HISTORY|PMH|SOCIAL HISTORY|FAMILY HISTORY|"
    r"REVIEW OF SYSTEMS|ROS|PHYSICAL EXAM(?:INATION)?|VITALS?|"
    r"ASSESSMENT(?:\s+AND\s+PLAN)?|A/P|PLAN|"
    r"MEDICATIONS?|ALLERGIES|LABORATORY|LABS?|"
    r"IMPRESSION|FINDINGS?|RESULTS?|DIAGNOSIS|DIAGNOSES|"
    r"PROCEDURES?|HOSPITAL COURSE|DISCHARGE CONDITION|"
    r"FOLLOW.?UP|DISCHARGE MEDICATIONS?|DISCHARGE INSTRUCTIONS?|"
    r"ATTENDING|PROVIDER|SIGNED BY"
    r")[\s:]*$",
    re.IGNORECASE | re.MULTILINE,
)

MAX_CHUNK_CHARS = 4000  # Stay well under token limits for LLM calls
MIN_CHUNK_CHARS = 50


def page_chunks_to_knowledge_chunks(
    page_chunks: List[PageChunk],
    patient_id: str,
    document_type: DocumentType,
) -> List[KnowledgeChunk]:
    knowledge_chunks: List[KnowledgeChunk] = []

    for page in page_chunks:
        if page.is_empty or not page.text.strip():
            continue

        if len(page.text) <= MAX_CHUNK_CHARS:
            # Page fits in a single chunk
            knowledge_chunks.append(
                KnowledgeChunk(
                    chunk_id=str(uuid.uuid4()),
                    document_id=page.document_id,
                    document_name=page.document_name,
                    document_type=document_type,
                    patient_id=patient_id,
                    page_number=page.page_number,
                    text=page.text,
                    char_count=page.char_count,
                    word_count=page.word_count,
                    evidence_ref=EvidenceRef(
                        document_id=page.document_id,
                        document_name=page.document_name,
                        document_type=document_type,
                        page_number=page.page_number,
                        excerpt=page.text[:300],
                    ),
                )
            )
        else:
            # Split long pages by section headers
            sub_chunks = _split_by_sections(page, patient_id, document_type)
            knowledge_chunks.extend(sub_chunks)

    logger.info(
        "Knowledge chunks created",
        total_chunks=len(knowledge_chunks),
        document_id=page_chunks[0].document_id if page_chunks else "unknown",
    )
    return knowledge_chunks


def _split_by_sections(
    page: PageChunk,
    patient_id: str,
    document_type: DocumentType,
) -> List[KnowledgeChunk]:
    chunks: List[KnowledgeChunk] = []
    sections = CLINICAL_SECTION_HEADERS.split(page.text)
    headers = CLINICAL_SECTION_HEADERS.findall(page.text)

    if len(sections) <= 1:
        # No section headers found — split by max char count
        return _split_by_length(page, patient_id, document_type)

    for i, section_text in enumerate(sections):
        if not section_text.strip() or len(section_text.strip()) < MIN_CHUNK_CHARS:
            continue
        header = headers[i - 1].strip() if i > 0 and i - 1 < len(headers) else ""
        full_section = f"{header}\n{section_text}".strip() if header else section_text.strip()

        chunks.append(
            KnowledgeChunk(
                chunk_id=str(uuid.uuid4()),
                document_id=page.document_id,
                document_name=page.document_name,
                document_type=document_type,
                patient_id=patient_id,
                page_number=page.page_number,
                text=full_section[:MAX_CHUNK_CHARS],
                char_count=min(len(full_section), MAX_CHUNK_CHARS),
                word_count=len(full_section.split()),
                evidence_ref=EvidenceRef(
                    document_id=page.document_id,
                    document_name=page.document_name,
                    document_type=document_type,
                    page_number=page.page_number,
                    excerpt=full_section[:300],
                ),
            )
        )
    return chunks


def _split_by_length(
    page: PageChunk,
    patient_id: str,
    document_type: DocumentType,
) -> List[KnowledgeChunk]:
    chunks = []
    text = page.text
    start = 0
    while start < len(text):
        end = min(start + MAX_CHUNK_CHARS, len(text))
        # Try to break at a newline
        if end < len(text):
            nl = text.rfind("\n", start, end)
            if nl > start + MIN_CHUNK_CHARS:
                end = nl

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                KnowledgeChunk(
                    chunk_id=str(uuid.uuid4()),
                    document_id=page.document_id,
                    document_name=page.document_name,
                    document_type=document_type,
                    patient_id=patient_id,
                    page_number=page.page_number,
                    text=chunk_text,
                    char_count=len(chunk_text),
                    word_count=len(chunk_text.split()),
                    evidence_ref=EvidenceRef(
                        document_id=page.document_id,
                        document_name=page.document_name,
                        document_type=document_type,
                        page_number=page.page_number,
                        excerpt=chunk_text[:300],
                    ),
                )
            )
        start = end
    return chunks
