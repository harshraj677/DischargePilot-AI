# OCR Module — Quick Reference

## Quick Start

### Install
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-your-key
```

### Basic Usage

```python
from app.ocr.orchestrator import OCROrchestrator
import fitz

# Load document
doc = fitz.open("document.pdf")

# Create orchestrator
orchestrator = OCROrchestrator(primary_provider="claude")

# Extract native text
page_texts = [page.get_text() for page in doc]

# Process with OCR
result = orchestrator.process_document(
    doc=doc,
    document_id="doc-123",
    document_name="document.pdf",
    page_texts=page_texts,
)

# Get combined text
combined = orchestrator.get_combined_text(
    doc=doc,
    document_id="doc-123",
    page_texts=page_texts,
    ocr_results=result["ocr_results"],
)
```

## API Reference

### OCROrchestrator

Main entry point for OCR processing.

```python
from app.ocr.orchestrator import OCROrchestrator

orchestrator = OCROrchestrator(
    primary_provider="claude",  # Options: "claude", "easyocr", "tesseract"
    enable_handwriting_detection=True,
)

# Process document
result = orchestrator.process_document(
    doc=fitz_document,
    document_id="doc-123",
    document_name="report.pdf",
    page_texts=[...],  # Native extraction per page
)

# Returns:
# {
#     "classifications": [PageClassification, ...],
#     "ocr_results": {page_num: OCRResultWithFallback, ...},
#     "summary": {...}
# }

# Get combined text
text = orchestrator.get_combined_text(
    doc=fitz_document,
    document_id="doc-123",
    page_texts=[...],
    ocr_results=result["ocr_results"],
)
```

### PageClassifier

Classifies page types.

```python
from app.ocr.page_classifier import PageClassifier
from app.ocr.models import PageType

classifier = PageClassifier()

classification = classifier.classify_page(
    page=fitz_page,
    page_number=1,
    native_text="...",
    enable_handwriting_detection=True,
)

# Returns PageClassification with:
# - page_type: TEXT_PAGE | SCANNED_PAGE | IMAGE_PAGE | HANDWRITTEN_PAGE | MIXED_PAGE
# - confidence: 0.0-1.0
# - extracted_text_length: int
# - has_images: bool
# - handwriting: HandwritingDetection | None
```

### OCRFallbackEngine

Manages provider selection and fallback.

```python
from app.ocr.fallback_engine import OCRFallbackEngine

engine = OCRFallbackEngine(
    primary_provider="claude",
    fallback_providers=["easyocr", "tesseract"],
    enable_fallback=True,
)

result = engine.process_page(
    page=fitz_page,
    page_number=1,
    document_id="doc-123",
    native_text="...",
    page_classification=classification,
)

# Returns OCRResultWithFallback or None if OCR not needed
```

### OCRSafetyValidator

Validates OCR results.

```python
from app.ocr.safety_validator import OCRSafetyValidator, SafetyLevel

validator = OCRSafetyValidator()

# Check if safe for extraction
is_safe, reason = validator.validate_for_knowledge_extraction(ocr_result)

# Get detailed assessment
assessment = validator.assess_safety(ocr_result)

# Returns SafetyAssessment with:
# - level: SAFE | CONDITIONAL | UNSAFE
# - confidence_score: 0.0-1.0
# - should_require_review: bool
# - safety_issues: [str]
# - recommendations: [str]

# Generate review report
report = validator.create_review_report(ocr_result)
```

### HandwritingProcessor

Processes handwritten content.

```python
from app.ocr.handwriting_processor import HandwritingProcessor

processor = HandwritingProcessor()

cleaned_text, confidence, requires_review = processor.process_ocr_result(
    ocr_result
)

# Determine if review needed
needs_review = processor.requires_clinical_review(
    text=extracted_text,
    confidence=0.75,
    page_type="handwritten_page",
)

# Create review note
note = processor.create_review_note(
    text=extracted_text,
    confidence=0.75,
    contains_medication=True,
    contains_diagnosis=False,
)
```

### Image Extraction

```python
from app.ocr.image_extractor import PDFImageExtractor

extractor = PDFImageExtractor(dpi=300)

# Render page to image
image_bytes = extractor.extract_page_image(
    page=fitz_page,
    page_number=1,
    output_format="PNG",
)

# Extract embedded images
images = extractor.extract_embedded_images(
    page=fitz_page,
    page_number=1,
)

# Save to disk
path = extractor.save_page_image(
    page=fitz_page,
    page_number=1,
    output_path=Path("output.png"),
)
```

## Page Types

```python
from app.ocr.models import PageType

PageType.TEXT_PAGE          # Native PDF text
PageType.SCANNED_PAGE       # Scanned document
PageType.IMAGE_PAGE         # Image-only
PageType.HANDWRITTEN_PAGE   # Handwritten content
PageType.MIXED_PAGE         # Mix of text and images
```

## Safety Levels

```python
from app.ocr.safety_validator import SafetyLevel

SafetyLevel.SAFE        # Can use directly
SafetyLevel.CONDITIONAL # Can use with review flag
SafetyLevel.UNSAFE      # Require manual review
```

## Common Patterns

### Pattern 1: Basic OCR Processing

```python
from app.ocr.orchestrator import OCROrchestrator

orchestrator = OCROrchestrator()
result = orchestrator.process_document(doc, doc_id, doc_name, texts)
combined_text = orchestrator.get_combined_text(doc, doc_id, texts, result["ocr_results"])
```

### Pattern 2: Safety-Validated Extraction

```python
from app.ocr.safety_validator import OCRSafetyValidator

validator = OCRSafetyValidator()

for page_num, ocr_result_with_fallback in ocr_results.items():
    ocr_result = ocr_result_with_fallback.selected_result
    is_safe, reason = validator.validate_for_knowledge_extraction(ocr_result)
    
    if is_safe:
        # Extract facts
        extract_facts(ocr_result.extracted_text)
    else:
        # Require review
        flag_for_review(ocr_result, reason)
```

### Pattern 3: Handwriting-Aware Processing

```python
from app.ocr.handwriting_processor import HandwritingProcessor

processor = HandwritingProcessor()

cleaned, confidence, needs_review = processor.process_ocr_result(ocr_result)

if needs_review:
    review_note = processor.create_review_note(
        cleaned, confidence,
        ocr_result.contains_medication_names,
        ocr_result.contains_diagnosis_terms,
    )
    send_to_review_queue(review_note)
```

### Pattern 4: Configure by Provider

```python
from app.ocr.orchestrator import OCROrchestrator

# For accuracy (medical documents)
orchestrator = OCROrchestrator(primary_provider="claude")

# For speed
orchestrator = OCROrchestrator(primary_provider="easyocr")

# For reliability
orchestrator = OCROrchestrator(primary_provider="tesseract")
```

## Configuration

### Environment Variables

```bash
# Provider
export OCR_PRIMARY_PROVIDER=claude

# Features
export OCR_ENABLE_FALLBACK=true
export OCR_ENABLE_HANDWRITING_DETECTION=true

# Performance
export OCR_MIN_TEXT_THRESHOLD=100
export OCR_SKIP_IF_TEXT_SUFFICIENT=true

# API
export ANTHROPIC_API_KEY=sk-...
```

### In Code

```python
from app.config import settings

if settings.OCR_ENABLED:
    orchestrator = OCROrchestrator()
```

## Logging

OCR operations are logged automatically:

```python
# Check logs
tail -f backend/logs/app.log

# Or programmatically
from app.utils.logging import get_logger

logger = get_logger(__name__)
logger.info("OCR completed", provider="claude", confidence=0.88)
```

## Testing

```bash
# Run all OCR tests
pytest backend/tests/test_ocr/

# Run specific test
pytest backend/tests/test_ocr/test_page_classifier.py

# With coverage
pytest backend/tests/test_ocr/ --cov=app.ocr

# Specific test class
pytest backend/tests/test_ocr/test_safety_validator.py::TestOCRSafetyValidator
```

## Troubleshooting

### Issue: Import Error

```python
# Error: No module named 'app.ocr'
# Solution: Install dependencies
pip install -r requirements.txt
```

### Issue: Claude API Error

```python
# Error: 401 Unauthorized
# Solution: Set API key
export ANTHROPIC_API_KEY=sk-your-key

# Verify
python -c "from anthropic import Anthropic; print('OK')"
```

### Issue: No Tesseract Found

```bash
# Linux
apt-get install tesseract-ocr

# macOS
brew install tesseract

# Windows
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
```

### Issue: Out of Memory

```python
# Use fallback providers instead
orchestrator = OCROrchestrator(primary_provider="easyocr")

# Or disable handwriting detection
orchestrator.enable_handwriting_detection = False
```

## Performance Tips

### Speed vs Accuracy Trade-off

```python
# Fast & Light
orchest = OCROrchestrator(primary_provider="easyocr")

# Slow & Accurate
orchest = OCROrchestrator(primary_provider="claude")
```

### Skip Unnecessary OCR

```python
# This is automatic, but you can check:
should_ocr = orchestrator.fallback_engine.should_run_ocr(
    native_text="...",
    page_classification=classification,
)
```

### Batch Processing

```python
# Process large documents in batches
batch_size = 10
for i in range(0, len(doc), batch_size):
    pages = doc[i:i+batch_size]
    # Process batch
    import gc
    gc.collect()  # Free memory
```

## Integration Checklist

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Set `ANTHROPIC_API_KEY` environment variable
- [ ] Run tests: `pytest backend/tests/test_ocr/`
- [ ] Update PDF extractor integration (see migration guide)
- [ ] Update safety engine for OCR results
- [ ] Update knowledge repository to track OCR source
- [ ] Test with sample scanned documents
- [ ] Monitor OCR metrics and safety validator
- [ ] Deploy and gather feedback

---

**Quick Links**:
- Full Migration Guide: [20_OCR_VISION_ENHANCEMENT_GUIDE.md](./20_OCR_VISION_ENHANCEMENT_GUIDE.md)
- Implementation Summary: [21_OCR_IMPLEMENTATION_SUMMARY.md](./21_OCR_IMPLEMENTATION_SUMMARY.md)
- Source Code: `backend/app/ocr/`
- Tests: `backend/tests/test_ocr/`
