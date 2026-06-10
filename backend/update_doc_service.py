import re

with open('app/services/document_service.py', 'r') as f:
    content = f.read()

imports_to_add = """
from pathlib import Path
import fitz
from PIL import Image
from app.ocr.integration import OCREnhancedExtractor
from app.gemini.vision import GeminiVisionService
from app.processing.pdf_extractor import ExtractionResult
"""
content = content.replace('from sqlalchemy.orm import Session\n', 'from sqlalchemy.orm import Session\n' + imports_to_add)

old_step_1 = """        # ── Step 1: PDF Extraction ────────────────────────────────────────
        pipeline_logs.append(_make_log("STEP_1", "Starting PDF extraction"))
        extraction = extract_pdf_with_retry(
            file_path=doc.file_path,
            document_id=document_id,
            document_name=doc.file_name,
            document_type=DocumentType(doc.document_type),
        )
        pipeline_logs.extend(extraction.processing_logs)"""

new_step_1 = """        # ── Step 1: Multimodal Extraction (PDF or Image) ──────────────────
        ext = Path(doc.file_name).suffix.lower()
        if ext in [".jpg", ".jpeg", ".png", ".webp"]:
            pipeline_logs.append(_make_log("STEP_1", "Starting Image extraction via Gemini Vision"))
            vision_service = GeminiVisionService()
            img = Image.open(doc.file_path)
            vision_service.validate_image(img)
            img = vision_service.convert_to_rgb(img)
            img = vision_service.resize_image_if_needed(img)
            
            # Using synchronous adaptation or we await if process_document allows.
            # perform_ocr is async, we are in an async function (process_document is async).
            ocr_result = await vision_service.perform_ocr(img, page_number=1)
            extracted_text = ocr_result.get("extracted_text", "")
            
            chunk = PageChunk(
                page_number=1,
                text=extracted_text,
                char_count=len(extracted_text),
                word_count=len(extracted_text.split()),
                is_empty=len(extracted_text) < settings.MIN_PAGE_TEXT_LENGTH,
                document_id=document_id,
                document_name=doc.file_name,
                document_type=DocumentType(doc.document_type),
            )
            extraction = ExtractionResult(
                page_chunks=[chunk],
                full_text=extracted_text,
                page_count=1,
                processing_logs=[],
                empty_page_count=0 if extracted_text else 1,
                duration_ms=0,
            )
        else:
            pipeline_logs.append(_make_log("STEP_1", "Starting PDF extraction with OCR fallback"))
            extraction = extract_pdf_with_retry(
                file_path=doc.file_path,
                document_id=document_id,
                document_name=doc.file_name,
                document_type=DocumentType(doc.document_type),
            )
            pipeline_logs.extend(extraction.processing_logs)
            
            # Enhance with OCR for scanned/image PDFs
            extractor = OCREnhancedExtractor(primary_ocr_provider="gemini")
            try:
                doc_fitz = fitz.open(doc.file_path)
                extraction, ocr_meta = extractor.enhance_extraction_result(
                    original_result=extraction,
                    doc=doc_fitz,
                    document_id=document_id,
                    document_name=doc.file_name,
                )
                pipeline_logs.append(_make_log("OCR_ENHANCEMENT", "OCR enhancement completed", details=ocr_meta))
            except Exception as ocr_e:
                logger.warning(f"OCR enhancement failed: {ocr_e}")
                pipeline_logs.append(_make_log("OCR_ENHANCEMENT_FAILED", f"OCR enhancement failed: {ocr_e}", is_error=True))"""

content = content.replace(old_step_1, new_step_1)

with open('app/services/document_service.py', 'w') as f:
    f.write(content)

print("document_service.py updated successfully.")
