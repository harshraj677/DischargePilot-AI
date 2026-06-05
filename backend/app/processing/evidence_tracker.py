"""
Evidence Tracking System — Module 7
Every extracted clinical entity must retain its source provenance.
No information should ever lose its document source, page number, and excerpt.
"""
import re
from typing import List, Optional

from app.models.document import PageChunk, KnowledgeChunk, EvidenceRef
from app.models.enums import DocumentType
from app.processing.text_cleaner import extract_snippet
from app.utils.logging import get_logger

logger = get_logger(__name__)


def find_evidence_for_term(
    term: str,
    pages: List[PageChunk],
    document_id: str,
    document_name: str,
    document_type: DocumentType,
    context_chars: int = 250,
    search_all_pages: bool = False,
) -> Optional[EvidenceRef]:
    """
    Search for a term across pages and return an EvidenceRef pointing to
    the first (most relevant) occurrence.
    """
    pages_to_search = pages if search_all_pages else pages[:10]

    for page in pages_to_search:
        if not page.text:
            continue
        idx = page.text.lower().find(term.lower())
        if idx == -1:
            # Try partial match (first word of multi-word term)
            first_word = term.split()[0] if " " in term else term
            idx = page.text.lower().find(first_word.lower())

        if idx != -1:
            excerpt = extract_snippet(page.text, term, context_chars)
            return EvidenceRef(
                document_id=document_id,
                document_name=document_name,
                document_type=document_type,
                page_number=page.page_number,
                excerpt=excerpt[:500],
                char_start=idx,
                char_end=min(idx + len(term), len(page.text)),
            )
    return None


def find_evidence_by_pattern(
    pattern: str,
    pages: List[PageChunk],
    document_id: str,
    document_name: str,
    document_type: DocumentType,
    context_chars: int = 250,
) -> Optional[EvidenceRef]:
    """Search using a regex pattern across pages."""
    for page in pages[:10]:
        if not page.text:
            continue
        match = re.search(pattern, page.text, re.IGNORECASE)
        if match:
            excerpt = extract_snippet(page.text, match.group(0), context_chars)
            return EvidenceRef(
                document_id=document_id,
                document_name=document_name,
                document_type=document_type,
                page_number=page.page_number,
                excerpt=excerpt[:500],
                char_start=match.start(),
                char_end=match.end(),
            )
    return None


def build_evidence_ref_from_chunk(
    chunk: KnowledgeChunk,
    term: Optional[str] = None,
    context_chars: int = 200,
) -> EvidenceRef:
    """Build an EvidenceRef from a KnowledgeChunk, optionally narrowed to a term."""
    if term:
        excerpt = extract_snippet(chunk.text, term, context_chars)
    else:
        excerpt = chunk.text[:300]

    return EvidenceRef(
        document_id=chunk.document_id,
        document_name=chunk.document_name,
        document_type=chunk.document_type,
        page_number=chunk.page_number,
        excerpt=excerpt[:500],
    )


def build_evidence_ref_from_page(
    page: PageChunk,
    document_id: str,
    document_name: str,
    document_type: DocumentType,
    term: Optional[str] = None,
    context_chars: int = 200,
) -> EvidenceRef:
    """Build an EvidenceRef from a PageChunk."""
    if term:
        excerpt = extract_snippet(page.text, term, context_chars)
    else:
        excerpt = page.text[:300]

    return EvidenceRef(
        document_id=document_id,
        document_name=document_name,
        document_type=document_type,
        page_number=page.page_number,
        excerpt=excerpt[:500],
    )


def assert_evidence_ref(ref: Optional[EvidenceRef], entity_name: str) -> None:
    """
    Safety check: assert that every extracted entity has an evidence reference.
    Logs a warning if provenance is missing — never silently loses source.
    """
    if ref is None:
        logger.warning(
            "EVIDENCE_MISSING — entity has no source reference",
            entity=entity_name,
        )
    elif not ref.excerpt or len(ref.excerpt.strip()) < 5:
        logger.warning(
            "EVIDENCE_WEAK — entity excerpt is nearly empty",
            entity=entity_name,
            document=ref.document_name,
            page=ref.page_number,
        )


class EvidenceIndex:
    """
    In-memory index of knowledge chunks for a patient encounter.
    Supports searching by term, page, and document type.
    Designed to be loaded once per agent run and queried many times.
    """

    def __init__(self, chunks: List[KnowledgeChunk]):
        self._chunks = chunks
        self._by_doc: dict = {}
        self._by_type: dict = {}

        for chunk in chunks:
            self._by_doc.setdefault(chunk.document_id, []).append(chunk)
            self._by_type.setdefault(chunk.document_type, []).append(chunk)

    def search(self, term: str, doc_type: Optional[DocumentType] = None) -> List[KnowledgeChunk]:
        corpus = self._by_type.get(doc_type, self._chunks) if doc_type else self._chunks
        term_lower = term.lower()
        return [c for c in corpus if term_lower in c.text.lower()]

    def chunks_for_document(self, document_id: str) -> List[KnowledgeChunk]:
        return self._by_doc.get(document_id, [])

    def chunks_for_type(self, doc_type: DocumentType) -> List[KnowledgeChunk]:
        return self._by_type.get(doc_type, [])

    def all_chunks(self) -> List[KnowledgeChunk]:
        return self._chunks

    def find_evidence(
        self,
        term: str,
        doc_type: Optional[DocumentType] = None,
    ) -> Optional[EvidenceRef]:
        results = self.search(term, doc_type)
        if not results:
            return None
        chunk = results[0]
        return build_evidence_ref_from_chunk(chunk, term)

    @property
    def total_chunks(self) -> int:
        return len(self._chunks)

    @property
    def document_count(self) -> int:
        return len(self._by_doc)
