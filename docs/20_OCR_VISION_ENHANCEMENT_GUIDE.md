# OCR & Vision Enhancement — Migration Guide

## Overview

This guide helps you integrate the OCR & Vision Enhancement module into DischargePilot AI, enabling support for scanned PDFs, image-based documents, and handwritten clinical notes.

## Key Features Added

✅ **Automatic Page Classification** - Detects text vs. scanned vs. image pages  
✅ **Multi-Provider OCR** - Claude Vision, EasyOCR, Tesseract with fallback  
✅ **Handwriting Detection** - Best-effort extraction with confidence scoring  
✅ **Clinical Safety** - Validates OCR results before knowledge extraction  
✅ **Evidence Tracking** - Preserves complete extraction chain  
✅ **Performance Optimization** - Skips OCR when unnecessary  

## Installation

### 1. Update Dependencies

```bash
pip install -r requirements.txt
```

New packages added:
- `pillow>=10.0.0` - Image processing
- `easyocr>=1.7.1` - Lightweight OCR
- `pytesseract>=0.3.10` - Tesseract OCR binding
- `opencv-python>=4.8.0` - Optional image processing

### 2. Optional: Install Tesseract

For Tesseract OCR support, install the binary:

**Windows:**
```bash
choco install tesseract
# or download from: https://github.com/UB-Mannheim/tesseract/wiki
```

**macOS:**
```bash
brew install tesseract
```

**Linux:**
```bash
apt-get install tesseract-ocr
```

### 3. Configure Environment

Add to `.env`:

```env
# Anthropic API Key (for Claude Vision OCR)
ANTHROPIC_API_KEY=your-api-key

# OCR Configuration
OCR_PRIMARY_PROVIDER=claude  # Options: claude, easyocr, tesseract
OCR_ENABLE_FALLBACK=true
OCR_ENABLE_HANDWRITING_DETECTION=true
```

## Architecture

### New Modules

```
backend/app/ocr/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── ocr_result.py          # Data models
├── page_classifier.py           # Page type classification
├── image_extractor.py           # PDF → Image rendering
├── fallback_engine.py           # Provider fallback strategy
├── handwriting_processor.py      # Handwriting extraction & safety
├── orchestrator.py              # Pipeline orchestration
├── safety_validator.py          # Safety validation
├── integration.py               # Integration with existing PDF extractor
└── providers/
    ├── __init__.py
    ├── base.py                  # Provider interface
    ├── claude.py                # Claude Vision provider
    ├── easyocr.py               # EasyOCR provider
    └── tesseract.py             # Tesseract provider
```

### Data Flow

```
PDF Input
    ↓
PyMuPDF Text Extraction
    ↓
Page Classification
    ├─ Sufficient text? → Use native text
    └─ Need OCR? → Image Extraction
        ↓
    Fallback Engine
        ├─ Try Primary Provider (Claude)
        ├─ Falls back to Alternative Providers
        └─ Select best result by confidence
            ↓
        Handwriting Detection
            ↓
        Safety Validation
            ↓
        Knowledge Repository
            ↓
        Agent Processing
```

## Integration Steps

### Step 1: Update PDF Extractor

In `backend/app/processing/pdf_extractor.py`, enhance the main extraction function:

```python
from app.ocr.integration import OCREnhancedExtractor

def extract_pdf(
    file_path: str,
    document_id: str,
    document_name: str,
    document_type: DocumentType = DocumentType.UNKNOWN,
    enable_ocr: bool = True,  # NEW parameter
) -> ExtractionResult:
    # ... existing extraction code ...
    
    # NEW: Enhance with OCR if needed
    if enable_ocr:
        ocr_extractor = OCREnhancedExtractor()
        result, ocr_metadata = ocr_extractor.enhance_extraction_result(
            original_result=result,
            doc=doc,
            document_id=document_id,
            document_name=document_name,
        )
        # Log OCR metadata for observability
        logger.info("PDF extraction enhanced", ocr_metadata=ocr_metadata)
    
    return result
```

### Step 2: Update Knowledge Repository

In `backend/app/knowledge/repository.py`, track OCR-extracted facts:

```python
def add_fact_from_ocr(
    self,
    category: str,
    value: str,
    ocr_result,  # OCRResult object
    evidence: str,
) -> None:
    """Add a fact extracted via OCR with safety tracking."""
    
    # Create evidenced fact with OCR metadata
    fact = EvidencedFact(
        value=value,
        confidence=ocr_result.confidence_score,
        source_document=...,
        source_document_id=document_id,
        page_number=ocr_result.page_number,
        evidence=evidence,
        extraction_method="ocr",  # NEW field
        ocr_provider=ocr_result.metadata.provider,  # NEW field
        requires_manual_review=ocr_result.requires_manual_review,  # NEW field
    )
    
    # Add to knowledge base
    self._set_fact(category, fact)
    self._touch()
```

### Step 3: Add Safety Validation in Agent

In `backend/app/agent/decision_engine.py`, validate OCR before extraction:

```python
from app.ocr.safety_validator import OCRSafetyValidator

def extract_clinical_facts(self, ocr_result):
    """Extract facts with safety validation."""
    
    validator = OCRSafetyValidator()
    is_safe, reason = validator.validate_for_knowledge_extraction(ocr_result)
    
    if not is_safe:
        self.logger.warning(
            "OCR result unsafe for extraction",
            reason=reason,
            page=ocr_result.page_number,
        )
        return None  # Skip unsafe content
    
    # Proceed with extraction
    # ... existing extraction logic ...
```

### Step 4: Update Safety Engine

In `backend/app/safety/engine.py`, add OCR-specific checks:

```python
def validate_medication_from_ocr(
    self,
    medication_name: str,
    ocr_result,
) -> bool:
    """Validate medication with OCR confidence."""
    
    # Higher scrutiny for low-confidence OCR
    if ocr_result.confidence_score < 0.70:
        # Require drug database lookup
        # Flag for pharmacist review
        # Reduce confidence in conflict detection
        pass
    
    return True
```

## Usage Examples

### Example 1: Process Scanned Hospital Document

```python
from app.ocr.orchestrator import OCROrchestrator
import fitz

# Load document
doc = fitz.open("scanned_hospital_report.pdf")

# Initialize orchestrator
orchestrator = OCROrchestrator(
    primary_provider="claude",
    enable_handwriting_detection=True,
)

# Extract native text
page_texts = [page.get_text() for page in doc]

# Process with OCR
result = orchestrator.process_document(
    doc=doc,
    document_id="doc-123",
    document_name="hospital_report.pdf",
    page_texts=page_texts,
)

# Use combined text
combined_text = orchestrator.get_combined_text(
    doc=doc,
    document_id="doc-123",
    page_texts=page_texts,
    ocr_results=result["ocr_results"],
)
```

### Example 2: Validate OCR Result for Safety

```python
from app.ocr.safety_validator import OCRSafetyValidator

validator = OCRSafetyValidator()

# Check if safe for knowledge extraction
is_safe, reason = validator.validate_for_knowledge_extraction(ocr_result)

if is_safe:
    # Extract facts from OCR
    pass
else:
    # Generate review report
    report = validator.create_review_report(ocr_result)
    logger.warning(report)
```

### Example 3: Handle Handwritten Content

```python
from app.ocr.handwriting_processor import HandwritingProcessor

processor = HandwritingProcessor()

# Process handwritten content
cleaned_text, confidence, requires_review = processor.process_ocr_result(
    ocr_result
)

if requires_review:
    # Create clinical review note
    review_note = processor.create_review_note(
        text=cleaned_text,
        confidence=confidence,
        contains_medication=ocr_result.contains_medication_names,
        contains_diagnosis=ocr_result.contains_diagnosis_terms,
    )
    # Send to clinical review queue
```

## Configuration

### Environment Variables

```env
# OCR Provider Selection
OCR_PRIMARY_PROVIDER=claude              # Primary provider
OCR_ENABLE_FALLBACK=true                 # Enable fallback

# Handwriting Support
OCR_ENABLE_HANDWRITING_DETECTION=true    # Detect handwriting

# Performance
OCR_SKIP_IF_TEXT_SUFFICIENT=true         # Skip if native text good
OCR_MIN_TEXT_THRESHOLD=100               # Chars needed to skip OCR

# API Keys
ANTHROPIC_API_KEY=sk-...                 # Claude Vision API key
```

### Settings in `config.py`

```python
# Add OCR settings
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() == "true"
OCR_PRIMARY_PROVIDER = os.getenv("OCR_PRIMARY_PROVIDER", "claude")
OCR_ENABLE_FALLBACK = os.getenv("OCR_ENABLE_FALLBACK", "true").lower() == "true"
OCR_ENABLE_HANDWRITING_DETECTION = os.getenv(
    "OCR_ENABLE_HANDWRITING_DETECTION", "true"
).lower() == "true"
OCR_MIN_TEXT_THRESHOLD = int(os.getenv("OCR_MIN_TEXT_THRESHOLD", "100"))
OCR_SKIP_IF_TEXT_SUFFICIENT = (
    os.getenv("OCR_SKIP_IF_TEXT_SUFFICIENT", "true").lower() == "true"
)
```

## Testing

Run the test suite:

```bash
# Run all OCR tests
pytest backend/tests/test_ocr/

# Run specific test file
pytest backend/tests/test_ocr/test_page_classifier.py

# Run with coverage
pytest backend/tests/test_ocr/ --cov=app.ocr
```

### Test Categories

1. **Page Classification** - `test_page_classifier.py`
2. **OCR Models** - `test_models.py`
3. **Safety Validation** - `test_safety_validator.py`
4. **Handwriting Processing** - `test_handwriting_processor.py`

## Monitoring & Observability

### Key Metrics to Track

```python
# In observability module
{
    "ocr_triggered": bool,           # Whether OCR was run
    "ocr_provider": str,              # Which provider was used
    "ocr_confidence": float,          # Confidence score (0-1)
    "ocr_processing_time_ms": float,  # Processing duration
    "ocr_fallback_used": bool,        # Was fallback needed
    "handwriting_detected": bool,     # Handwriting present
    "requires_manual_review": bool,   # Needs human review
    "page_type": str,                 # TEXT, SCANNED, IMAGE, etc.
}
```

### Logging Examples

```python
# OCR triggered
logger.info(
    "OCR processing started",
    page=1,
    page_type="scanned_page",
    provider="claude",
)

# OCR completed
logger.info(
    "OCR processing completed",
    page=1,
    provider="claude",
    confidence=0.88,
    processing_time_ms=1234,
)

# Safety validation
logger.warning(
    "OCR result requires review",
    page=1,
    confidence=0.65,
    reason="Low confidence with medication information",
)
```

## Troubleshooting

### Issue: Claude Vision API key not working

**Solution:**
```bash
# Verify API key is set
echo $ANTHROPIC_API_KEY

# Test API connection
python -c "from anthropic import Anthropic; Anthropic(api_key='your-key')"
```

### Issue: EasyOCR model downloading fails

**Solution:**
```python
# Manually download model
import easyocr
reader = easyocr.Reader(['en'], download_enabled=True)
```

### Issue: Tesseract not found

**Solution:**
```bash
# Verify installation
tesseract --version

# Set path in Python (Windows)
import pytesseract
pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### Issue: Out of memory with large PDFs

**Solution:**
```python
# Process pages in batches
for page_num in range(0, len(doc), batch_size):
    pages = doc[page_num:page_num+batch_size]
    # Process batch
    # Clear memory
    import gc
    gc.collect()
```

## Safety Considerations

1. **Never trust OCR blindly** - Always validate confidence
2. **Clinical keywords need higher confidence** - Medications, allergies, contraindications
3. **Handwritten content requires review** - Always flag for manual review
4. **Preserve evidence chain** - Track which content came from OCR
5. **Monitor for fabrication** - Agent should never invent missing OCR content

## Performance Tuning

### Optimize for Speed

```python
# Use EasyOCR for speed (lower accuracy)
orchestrator = OCROrchestrator(primary_provider="easyocr")

# Disable handwriting detection
orchestrator.enable_handwriting_detection = False

# Skip OCR when possible
orchestrator.fallback_engine.enable_optimization = True
```

### Optimize for Accuracy

```python
# Use Claude Vision (best accuracy)
orchestrator = OCROrchestrator(primary_provider="claude")

# Enable handwriting detection
orchestrator.enable_handwriting_detection = True

# Use fallback chain
orchestrator.enable_fallback = True
```

## Rollback Plan

If issues arise, disable OCR temporarily:

```env
# In .env
OCR_ENABLED=false
```

This falls back to native PDF extraction only. Existing functionality remains unchanged.

## Next Steps

1. Install dependencies: `pip install -r requirements.txt`
2. Set `ANTHROPIC_API_KEY` environment variable
3. Run tests: `pytest backend/tests/test_ocr/`
4. Update PDF extractor integration
5. Test with sample scanned documents
6. Monitor OCR metrics and safety validators
7. Collect feedback from clinical team

## Support

For issues or questions:
1. Check logs in `backend/logs/`
2. Review test files for usage examples
3. Check safety validator reports for OCR issues
4. Review Page Classification for page type detection

---

**Version:** 1.0  
**Last Updated:** 2026-06-06
