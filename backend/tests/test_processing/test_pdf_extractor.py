import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock

from app.processing.pdf_extractor import extract_pdf, ExtractionResult
from app.processing.text_cleaner import clean_page_text, clean_document_text, extract_snippet
from app.processing.document_classifier import classify_by_rules
from app.processing.metadata_extractor import extract_metadata
from app.models.enums import DocumentType
from app.models.document import PageChunk


class TestTextCleaner:
    def test_removes_control_characters(self):
        dirty = "Hello\x00World\x1fTest"
        cleaned = clean_page_text(dirty)
        assert "\x00" not in cleaned
        assert "\x1f" not in cleaned
        assert "Hello" in cleaned

    def test_normalizes_whitespace(self):
        dirty = "Hello    World\n\n\n\nTest"
        cleaned = clean_page_text(dirty)
        assert "    " not in cleaned
        assert "\n\n\n" not in cleaned

    def test_preserves_medical_values(self):
        text = "HbA1c: 9.2%    Creatinine: 1.8 mg/dL"
        cleaned = clean_page_text(text)
        assert "9.2" in cleaned
        assert "1.8" in cleaned
        assert "mg/dL" in cleaned

    def test_normalizes_unicode(self):
        text = "Temperature ≥ 38.5°C"
        cleaned = clean_page_text(text)
        assert ">=" in cleaned

    def test_empty_text_returns_empty(self):
        assert clean_page_text("") == ""
        assert clean_page_text("   ") == ""

    def test_extract_snippet_centers_on_keyword(self):
        text = "Patient has Type 2 Diabetes Mellitus with poor control."
        snippet = extract_snippet(text, "Diabetes", context_chars=40)
        assert "Diabetes" in snippet

    def test_extract_snippet_keyword_not_found(self):
        text = "Patient information here"
        snippet = extract_snippet(text, "nonexistent", context_chars=50)
        assert len(snippet) > 0  # Returns beginning of text


class TestDocumentClassifier:
    def test_classify_admission_note(self, admission_note_text):
        result = classify_by_rules(admission_note_text)
        assert result.document_type == DocumentType.ADMISSION_NOTE
        assert result.confidence > 0.4

    def test_classify_lab_report(self, lab_report_text):
        result = classify_by_rules(lab_report_text)
        assert result.document_type == DocumentType.LAB_REPORT
        assert result.confidence > 0.3

    def test_classify_medication_record(self, medication_record_text):
        result = classify_by_rules(medication_record_text)
        assert result.document_type == DocumentType.MEDICATION_RECORD
        assert result.confidence > 0.3

    def test_empty_text_returns_unknown(self):
        result = classify_by_rules("")
        assert result.document_type == DocumentType.UNKNOWN
        assert result.confidence == 0.0

    def test_scores_sum_handled(self, admission_note_text):
        result = classify_by_rules(admission_note_text)
        assert result.scores is not None
        assert len(result.scores) > 0
        assert all(0.0 <= v <= 1.0 for v in result.scores.values())


class TestMetadataExtractor:
    def _make_pages(self, text: str, doc_id: str = "test-doc", doc_name: str = "test.pdf") -> list:
        return [
            PageChunk(
                page_number=1,
                text=text,
                char_count=len(text),
                word_count=len(text.split()),
                is_empty=False,
                document_id=doc_id,
                document_name=doc_name,
                document_type=DocumentType.ADMISSION_NOTE,
            )
        ]

    def test_extracts_patient_name(self, admission_note_text):
        pages = self._make_pages(admission_note_text)
        metadata = extract_metadata(pages, "doc-1", "test.pdf", DocumentType.ADMISSION_NOTE)
        assert metadata.patient_name is not None
        assert "Doe" in metadata.patient_name or "John" in metadata.patient_name

    def test_extracts_mrn(self, admission_note_text):
        pages = self._make_pages(admission_note_text)
        metadata = extract_metadata(pages, "doc-1", "test.pdf", DocumentType.ADMISSION_NOTE)
        assert metadata.mrn is not None
        assert "00123" in metadata.mrn or "MRN" in (metadata.mrn or "")

    def test_extracts_admission_date(self, admission_note_text):
        pages = self._make_pages(admission_note_text)
        metadata = extract_metadata(pages, "doc-1", "test.pdf", DocumentType.ADMISSION_NOTE)
        assert metadata.admission_date is not None
        assert "2025" in (metadata.admission_date or "")

    def test_extracts_provider(self, admission_note_text):
        pages = self._make_pages(admission_note_text)
        metadata = extract_metadata(pages, "doc-1", "test.pdf", DocumentType.ADMISSION_NOTE)
        assert metadata.provider_name is not None
        assert "Chen" in (metadata.provider_name or "")

    def test_evidence_refs_present_when_extracted(self, admission_note_text):
        pages = self._make_pages(admission_note_text)
        metadata = extract_metadata(pages, "doc-1", "test.pdf", DocumentType.ADMISSION_NOTE)
        if metadata.patient_name:
            assert metadata.patient_name_evidence is not None
            assert metadata.patient_name_evidence.page_number == 1
            assert len(metadata.patient_name_evidence.excerpt) > 10

    def test_empty_pages_returns_empty_metadata(self):
        pages = self._make_pages("")
        metadata = extract_metadata(pages, "doc-1", "test.pdf", DocumentType.UNKNOWN)
        assert metadata.patient_name is None
        assert metadata.mrn is None


class TestPDFExtractor:
    def test_extract_real_pdf(self, sample_pdf_path):
        result = extract_pdf(sample_pdf_path, "doc-1", "test.pdf", DocumentType.ADMISSION_NOTE)
        assert isinstance(result, ExtractionResult)
        assert result.page_count >= 1
        assert len(result.page_chunks) >= 1
        assert result.full_text  # Non-empty
        assert len(result.processing_logs) > 0

    def test_page_chunks_have_page_numbers(self, sample_pdf_path):
        result = extract_pdf(sample_pdf_path, "doc-1", "test.pdf", DocumentType.ADMISSION_NOTE)
        for i, chunk in enumerate(result.page_chunks):
            assert chunk.page_number == i + 1

    def test_page_chunks_have_document_reference(self, sample_pdf_path):
        result = extract_pdf(sample_pdf_path, "doc-1", "test.pdf", DocumentType.ADMISSION_NOTE)
        for chunk in result.page_chunks:
            assert chunk.document_id == "doc-1"
            assert chunk.document_name == "test.pdf"

    def test_nonexistent_file_raises(self):
        from app.utils.exceptions import PDFExtractionException
        with pytest.raises(PDFExtractionException):
            extract_pdf("/nonexistent/path/file.pdf", "doc-1", "file.pdf")

    def test_corrupted_file_raises(self):
        from app.utils.exceptions import PDFCorruptedException
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"This is not a valid PDF file")
            path = f.name
        try:
            with pytest.raises(PDFCorruptedException):
                extract_pdf(path, "doc-1", "bad.pdf")
        finally:
            os.remove(path)
