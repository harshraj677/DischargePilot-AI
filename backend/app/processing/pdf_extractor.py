"""
PDF Extraction Engine — Module 2
Uses PyMuPDF (fitz) with retry logic, corruption detection, and per-page evidence preservation.
"""
import time
from pathlib import Path
from typing import List, Tuple

import fitz  # PyMuPDF
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.models.document import PageChunk, ProcessingLog
from app.models.enums import DocumentType
from app.utils.exceptions import PDFCorruptedException, PDFEmptyException, PDFExtractionException
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ExtractionResult:
    def __init__(
        self,
        page_chunks: List[PageChunk],
        full_text: str,
        page_count: int,
        processing_logs: List[ProcessingLog],
        empty_page_count: int,
        duration_ms: float,
    ):
        self.page_chunks = page_chunks
        self.full_text = full_text
        self.page_count = page_count
        self.processing_logs = processing_logs
        self.empty_page_count = empty_page_count
        self.duration_ms = duration_ms


def _make_log(event: str, message: str, details: dict = None, is_error: bool = False) -> ProcessingLog:
    from datetime import datetime
    return ProcessingLog(
        event=event,
        timestamp=datetime.utcnow(),
        message=message,
        details=details or {},
        is_error=is_error,
    )


def _open_pdf(file_path: str) -> fitz.Document:
    try:
        doc = fitz.open(file_path)
        if doc.is_encrypted:
            raise PDFCorruptedException(Path(file_path).name)
        return doc
    except fitz.FileDataError:
        raise PDFCorruptedException(Path(file_path).name)
    except Exception as e:
        raise PDFExtractionException(Path(file_path).name, str(e))


def _extract_page_text(page: fitz.Page) -> str:
    try:
        text = page.get_text("text")
        return text or ""
    except Exception:
        try:
            return page.get_text("rawdict").get("blocks", "")
        except Exception:
            return ""


def extract_pdf(
    file_path: str,
    document_id: str,
    document_name: str,
    document_type: DocumentType = DocumentType.UNKNOWN,
) -> ExtractionResult:
    logs: List[ProcessingLog] = []
    start_time = time.perf_counter()
    filename = Path(file_path).name

    logs.append(_make_log("EXTRACTION_STARTED", f"Opening PDF: {filename}"))
    logger.info("Starting PDF extraction", document_id=document_id, filename=filename)

    if not Path(file_path).exists():
        raise PDFExtractionException(filename, "File not found on disk")

    doc = _open_pdf(file_path)
    page_count = len(doc)
    logs.append(_make_log("PDF_OPENED", f"PDF opened successfully", {"page_count": page_count}))

    if page_count == 0:
        doc.close()
        raise PDFEmptyException(filename)

    page_chunks: List[PageChunk] = []
    empty_page_count = 0
    all_text_parts: List[str] = []

    for page_num in range(page_count):
        page = doc[page_num]
        raw_text = _extract_page_text(page)
        cleaned_text = raw_text.strip()

        word_count = len(cleaned_text.split()) if cleaned_text else 0
        is_empty = len(cleaned_text) < settings.MIN_PAGE_TEXT_LENGTH

        if is_empty:
            empty_page_count += 1
            logs.append(
                _make_log(
                    "EMPTY_PAGE",
                    f"Page {page_num + 1} has insufficient text ({len(cleaned_text)} chars)",
                    {"page_number": page_num + 1, "char_count": len(cleaned_text)},
                )
            )

        chunk = PageChunk(
            page_number=page_num + 1,
            text=cleaned_text,
            char_count=len(cleaned_text),
            word_count=word_count,
            is_empty=is_empty,
            document_id=document_id,
            document_name=document_name,
            document_type=document_type,
        )
        page_chunks.append(chunk)

        if cleaned_text:
            all_text_parts.append(f"--- Page {page_num + 1} ---\n{cleaned_text}")

    doc.close()

    full_text = "\n\n".join(all_text_parts)
    non_empty_chars = sum(c.char_count for c in page_chunks if not c.is_empty)

    if non_empty_chars < settings.MIN_PAGE_TEXT_LENGTH * 2:
        raise PDFEmptyException(filename)

    duration_ms = (time.perf_counter() - start_time) * 1000
    logs.append(
        _make_log(
            "EXTRACTION_COMPLETED",
            f"Extracted {page_count} pages ({empty_page_count} empty) in {duration_ms:.1f}ms",
            {
                "page_count": page_count,
                "empty_pages": empty_page_count,
                "total_chars": len(full_text),
                "duration_ms": round(duration_ms, 2),
            },
        )
    )

    logger.info(
        "PDF extraction complete",
        document_id=document_id,
        pages=page_count,
        empty_pages=empty_page_count,
        total_chars=len(full_text),
        duration_ms=round(duration_ms, 2),
    )

    return ExtractionResult(
        page_chunks=page_chunks,
        full_text=full_text,
        page_count=page_count,
        processing_logs=logs,
        empty_page_count=empty_page_count,
        duration_ms=duration_ms,
    )


@retry(
    stop=stop_after_attempt(settings.MAX_EXTRACTION_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(PDFExtractionException),
    reraise=True,
)
def extract_pdf_with_retry(
    file_path: str,
    document_id: str,
    document_name: str,
    document_type: DocumentType = DocumentType.UNKNOWN,
) -> ExtractionResult:
    return extract_pdf(file_path, document_id, document_name, document_type)
