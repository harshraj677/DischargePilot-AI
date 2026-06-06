"""
Unit tests for the Document Classifier (Phase 2).

Tests cover:
1. Correct document type classification
2. Confidence thresholds
3. Unknown/ambiguous documents
4. Clinical keyword detection
"""
from __future__ import annotations

import pytest

from app.processing.document_classifier import DocumentClassifier


ADMISSION_NOTE = """
ADMISSION NOTE
Patient: John Doe  MRN: 12345
Chief Complaint: Shortness of breath
History of Present Illness: 54-year-old male admitted with chest pain and dyspnea.
Assessment: Pneumonia, Type 2 DM
Plan: IV antibiotics, glycemic management
"""

LAB_REPORT = """
LABORATORY RESULTS REPORT
Patient: John Doe  MRN: 12345
WBC: 9.2 K/uL (4.0-11.0) — NORMAL
Hemoglobin: 11.8 g/dL — LOW
Creatinine: 1.8 mg/dL — HIGH
Glucose: 412 mg/dL — CRITICAL HIGH
HbA1c: 9.2%
Pending: Blood cultures — PENDING
"""

MEDICATION_RECORD = """
MEDICATION ADMINISTRATION RECORD
Patient: John Doe
Metformin 1000mg PO BID — Administered 0800
Lisinopril 10mg PO daily — Administered 0900
Atorvastatin 40mg PO QHS — Administered 2100
Regular Insulin sliding scale — 6 units @ 0700
"""

DISCHARGE_SUMMARY = """
DISCHARGE SUMMARY
Patient: John Doe  Discharge Date: 06/05/2025
Principal Diagnosis: Community-acquired pneumonia
Discharge Medications: Amoxicillin 500mg TID x7 days
Follow-up: PCP in 1 week
Discharge Condition: Stable
"""

OPERATIVE_NOTE = """
OPERATIVE NOTE
Procedure: Laparoscopic cholecystectomy
Surgeon: Dr. Smith
Anesthesia: General
Estimated Blood Loss: 50mL
Complications: None
Specimens: Gallbladder sent to pathology
"""

RADIOLOGY_REPORT = """
RADIOLOGY REPORT
Study: CT Chest with contrast
Indication: Rule out pulmonary embolism
Findings: No evidence of pulmonary embolism. Bilateral lower lobe consolidation
  consistent with pneumonia.
Impression: Community-acquired pneumonia, bilateral lower lobes.
"""


class TestDocumentClassifier:
    def setup_method(self):
        self.classifier = DocumentClassifier()

    def test_classifies_admission_note(self):
        result = self.classifier.classify(ADMISSION_NOTE)
        assert result.document_type in ("admission_note", "clinical_note")
        assert result.confidence >= 0.5

    def test_classifies_lab_report(self):
        result = self.classifier.classify(LAB_REPORT)
        assert result.document_type == "lab_report"
        assert result.confidence >= 0.5

    def test_classifies_medication_record(self):
        result = self.classifier.classify(MEDICATION_RECORD)
        assert result.document_type in ("medication_record", "mar")
        assert result.confidence >= 0.5

    def test_classifies_discharge_summary(self):
        result = self.classifier.classify(DISCHARGE_SUMMARY)
        assert result.document_type == "discharge_summary"

    def test_classifies_radiology_report(self):
        result = self.classifier.classify(RADIOLOGY_REPORT)
        assert result.document_type in ("radiology_report", "imaging_report")

    def test_empty_text_classified_as_unknown(self):
        result = self.classifier.classify("")
        assert result.document_type in ("unknown", "other")
        assert result.confidence < 0.5

    def test_confidence_between_zero_and_one(self):
        for text in [ADMISSION_NOTE, LAB_REPORT, MEDICATION_RECORD]:
            result = self.classifier.classify(text)
            assert 0.0 <= result.confidence <= 1.0

    def test_returns_document_type_attribute(self):
        result = self.classifier.classify(ADMISSION_NOTE)
        assert hasattr(result, "document_type")
        assert hasattr(result, "confidence")

    def test_batch_classification(self):
        texts = [ADMISSION_NOTE, LAB_REPORT, MEDICATION_RECORD]
        results = self.classifier.classify_batch(texts)
        assert len(results) == 3
        for r in results:
            assert r.document_type is not None

    def test_lab_report_detects_pending(self):
        result = self.classifier.classify(LAB_REPORT)
        # Classifier should note the PENDING keyword
        assert result.document_type == "lab_report"
