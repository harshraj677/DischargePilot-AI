"""
Document Processing Service — orchestrates the full pipeline:
Extract → Clean → Classify → Extract Metadata → Chunk → Save
"""
import asyncio
import time
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

import fitz
from app.ocr.integration import OCREnhancedExtractor
from app.processing.pdf_extractor import ExtractionResult

from app.config import settings
from app.db.repositories.document_repo import DocumentRepository
from app.models.document import PageChunk, ProcessingLog
from app.models.enums import DocumentStatus, DocumentType
from app.processing.pdf_extractor import extract_pdf_with_retry
from app.processing.text_cleaner import clean_page_text, clean_document_text
from app.processing.document_classifier import classify_document
from app.processing.metadata_extractor import extract_metadata
from app.processing.chunker import page_chunks_to_knowledge_chunks
from app.utils.exceptions import PDFCorruptedException, PDFEmptyException, PDFExtractionException
from app.utils.file_utils import compute_file_hash
from app.utils.logging import get_logger, AuditLogger

logger = get_logger(__name__)
audit = AuditLogger(__name__)


def _make_log(event: str, message: str, details: dict = None, is_error: bool = False) -> ProcessingLog:
    return ProcessingLog(
        event=event,
        timestamp=datetime.utcnow(),
        message=message,
        details=details or {},
        is_error=is_error,
    )


async def process_document(document_id: str, db: Session) -> None:
    """
    Full async processing pipeline for a single document.
    Called as a FastAPI BackgroundTask after upload.
    Never raises — all failures produce structured error records.
    """
    repo = DocumentRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        logger.error("Document not found for processing", document_id=document_id)
        return

    repo.set_processing(document_id)
    audit.log_extraction_start(document_id, doc.file_name)
    pipeline_logs: list[ProcessingLog] = []
    start_time = time.perf_counter()

    try:
        # ── Step 1: PDF Extraction ────────────────────────────────────────
        pipeline_logs.append(_make_log("STEP_1", "Starting PDF extraction"))
        extraction = extract_pdf_with_retry(
            file_path=doc.file_path,
            document_id=document_id,
            document_name=doc.file_name,
            document_type=DocumentType(doc.document_type),
        )
        pipeline_logs.extend(extraction.processing_logs)

        # ── Step 1b: Claude Vision OCR fallback for scanned/image pages ──
        # Native extraction returns empty text for scanned/image-only PDFs —
        # that is NOT a failure. Run OCR on those pages instead of rejecting.
        ocr_metadata: Optional[dict] = None
        if settings.OCR_ENABLED and extraction.empty_page_count > 0:
            extraction, ocr_metadata = await _run_ocr_fallback(
                doc=doc,
                extraction=extraction,
                document_id=document_id,
                pipeline_logs=pipeline_logs,
            )

        # If, even after OCR, there's still no usable text, don't fail the
        # document outright — flag it for manual review instead.
        usable_text = clean_document_text(extraction.full_text)
        if len(usable_text.strip()) < settings.MIN_PAGE_TEXT_LENGTH * 2:
            ocr_attempted = bool(ocr_metadata and ocr_metadata.get("ocr_enabled"))
            reason = (
                "Scanned/image-only document — Vision OCR could not extract usable text. "
                "Flagged for manual review."
                if ocr_attempted
                else "Document contains no extractable text and is not a scanned PDF eligible for OCR. "
                "Flagged for manual review."
            )
            _handle_review_required(repo, document_id, doc.file_name, reason, pipeline_logs)
            return

        # ── Step 2: Text Cleaning ─────────────────────────────────────────
        pipeline_logs.append(_make_log("STEP_2", "Cleaning extracted text"))
        cleaned_chunks: list[PageChunk] = []
        for chunk in extraction.page_chunks:
            cleaned_text = clean_page_text(chunk.text)
            cleaned_chunks.append(
                chunk.model_copy(update={"text": cleaned_text, "char_count": len(cleaned_text)})
            )

        full_text_cleaned = clean_document_text(extraction.full_text)

        # ── Step 3: Document Classification ──────────────────────────────
        pipeline_logs.append(_make_log("STEP_3", "Classifying document type"))
        declared = DocumentType(doc.declared_type) if doc.declared_type else None
        classification = await classify_document(
            text=full_text_cleaned,
            filename=doc.file_name,
            declared_type=declared,
        )
        audit.log_classification(
            document_id,
            classification.document_type.value,
            classification.confidence,
            classification.method.value,
        )
        pipeline_logs.append(
            _make_log(
                "CLASSIFICATION_DONE",
                f"Classified as {classification.document_type.value} "
                f"(confidence={classification.confidence:.2f}, method={classification.method.value})",
                {
                    "document_type": classification.document_type.value,
                    "confidence": classification.confidence,
                    "method": classification.method.value,
                    "scores": classification.scores,
                },
            )
        )

        # Update chunks with the determined document type
        typed_chunks = [
            c.model_copy(update={"document_type": classification.document_type})
            for c in cleaned_chunks
        ]

        # ── Step 4: Metadata Extraction ───────────────────────────────────
        pipeline_logs.append(_make_log("STEP_4", "Extracting clinical metadata"))
        metadata = extract_metadata(
            pages=typed_chunks,
            document_id=document_id,
            document_name=doc.file_name,
            document_type=classification.document_type,
        )
        pipeline_logs.append(
            _make_log(
                "METADATA_DONE",
                "Metadata extraction complete",
                {
                    "patient_name": metadata.patient_name,
                    "mrn": metadata.mrn,
                    "admission_date": metadata.admission_date,
                    "provider": metadata.provider_name,
                },
            )
        )

        # ── Step 5: Chunking (for agent use) ─────────────────────────────
        pipeline_logs.append(_make_log("STEP_5", "Creating knowledge chunks"))
        knowledge_chunks = page_chunks_to_knowledge_chunks(
            page_chunks=typed_chunks,
            patient_id=doc.patient_id,
            document_type=classification.document_type,
        )
        pipeline_logs.append(
            _make_log(
                "CHUNKING_DONE",
                f"Created {len(knowledge_chunks)} knowledge chunks",
                {"chunk_count": len(knowledge_chunks)},
            )
        )

        # ── Step 6: File Hash ─────────────────────────────────────────────
        file_hash = compute_file_hash(doc.file_path)

        # ── Step 7: Persist Results ───────────────────────────────────────
        total_duration = (time.perf_counter() - start_time) * 1000
        pipeline_logs.append(
            _make_log(
                "PIPELINE_COMPLETE",
                f"Full pipeline completed in {total_duration:.1f}ms",
                {"total_duration_ms": round(total_duration, 2)},
            )
        )

        repo.save_extraction_results(
            document_id=document_id,
            page_chunks=typed_chunks,
            page_count=extraction.page_count,
            full_text=full_text_cleaned,
            metadata=metadata,
            doc_type=classification.document_type.value,
            confidence=classification.confidence,
            method=classification.method.value,
            processing_logs=pipeline_logs,
            file_hash=file_hash,
        )

        audit.log_extraction_complete(
            document_id, doc.file_name, extraction.page_count, total_duration
        )
        logger.info(
            "Document processing complete",
            document_id=document_id,
            filename=doc.file_name,
            pages=extraction.page_count,
            doc_type=classification.document_type.value,
            total_ms=round(total_duration, 2),
        )

    except (PDFCorruptedException, PDFEmptyException) as e:
        _handle_failure(repo, document_id, doc.file_name, str(e), pipeline_logs, is_critical=True)
    except PDFExtractionException as e:
        _handle_failure(repo, document_id, doc.file_name, str(e), pipeline_logs, is_critical=False)
    except Exception as e:
        logger.error("Unexpected error during document processing", document_id=document_id, error=str(e), exc_info=True)
        _handle_failure(repo, document_id, doc.file_name, f"Unexpected error: {e}", pipeline_logs, is_critical=True)


def _handle_failure(
    repo: DocumentRepository,
    document_id: str,
    filename: str,
    error: str,
    logs: list,
    is_critical: bool,
) -> None:
    logs.append(
        _make_log("PIPELINE_FAILED", f"Processing failed: {error}", {"error": error}, is_error=True)
    )
    repo.set_failed(document_id, error)
    audit.log_extraction_failure(document_id, filename, error)
    logger.error(
        "Document processing failed",
        document_id=document_id,
        filename=filename,
        error=error,
        critical=is_critical,
    )


def _handle_review_required(
    repo: DocumentRepository,
    document_id: str,
    filename: str,
    reason: str,
    logs: list,
) -> None:
    """
    Flag a document for manual review instead of failing it outright.
    The document and any partial extraction results are preserved.
    """
    logs.append(
        _make_log("REVIEW_REQUIRED", f"Flagged for manual review: {reason}", {"reason": reason})
    )
    repo.set_review_required(document_id, reason)
    logger.warning(
        "Document flagged for manual review",
        document_id=document_id,
        filename=filename,
        reason=reason,
    )


async def _run_ocr_fallback(
    doc,
    extraction: ExtractionResult,
    document_id: str,
    pipeline_logs: list,
) -> tuple[ExtractionResult, dict]:
    """
    Run Vision OCR (Claude by default, see settings.OCR_PRIMARY_PROVIDER) over
    pages with no native text and merge the results into the extraction. Never
    raises — on any failure, the original native-text extraction is returned
    unchanged so the pipeline can continue (and, if needed, fall through to
    manual review).
    """
    pipeline_logs.append(
        _make_log(
            "OCR_FALLBACK_TRIGGERED",
            f"{extraction.empty_page_count} of {extraction.page_count} page(s) have no "
            f"extractable native text — running Vision OCR ({settings.OCR_PRIMARY_PROVIDER})",
            {"empty_pages": extraction.empty_page_count, "page_count": extraction.page_count},
        )
    )
    logger.info(
        "Triggering Vision OCR fallback",
        document_id=document_id,
        provider=settings.OCR_PRIMARY_PROVIDER,
        empty_pages=extraction.empty_page_count,
        page_count=extraction.page_count,
    )

    pdf_doc = None
    try:
        pdf_doc = fitz.open(doc.file_path)
        extractor = OCREnhancedExtractor(
            enable_ocr=True,
            primary_ocr_provider=settings.OCR_PRIMARY_PROVIDER or "groq",
        )
        # enhance_extraction_result is sync and blocks on Vision OCR calls —
        # run it in a worker thread so it never blocks the event loop (and so
        # its internal asyncio.run_until_complete has no running loop to fight).
        enhanced_result, ocr_metadata = await asyncio.to_thread(
            extractor.enhance_extraction_result,
            original_result=extraction,
            doc=pdf_doc,
            document_id=document_id,
            document_name=doc.file_name,
        )

        pipeline_logs.append(
            _make_log(
                "OCR_FALLBACK_COMPLETE",
                f"Vision OCR enhanced {ocr_metadata.get('pages_enhanced_with_ocr', 0)} page(s)",
                ocr_metadata,
            )
        )
        logger.info(
            "OCR fallback complete",
            document_id=document_id,
            pages_enhanced=ocr_metadata.get("pages_enhanced_with_ocr", 0),
        )
        return enhanced_result, ocr_metadata

    except Exception as exc:
        pipeline_logs.append(
            _make_log(
                "OCR_FALLBACK_FAILED",
                f"Vision OCR fallback failed: {exc}",
                {"error": str(exc)},
                is_error=True,
            )
        )
        logger.error(
            "OCR fallback failed — continuing with native extraction",
            document_id=document_id,
            error=str(exc),
            exc_info=True,
        )
        return extraction, {"ocr_enabled": True, "ocr_failed": True, "error": str(exc)}

    finally:
        if pdf_doc is not None:
            pdf_doc.close()
