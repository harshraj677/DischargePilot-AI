# DischargePilot AI — Anthropic Claude to Google Gemini Migration Plan

**Migration Status**: Ready for Implementation  
**Date**: 2026-06-06  
**Target**: Production-Grade Gemini Integration with Multimodal PDF/Image Support

---

## 🎯 Executive Summary

This migration replaces all Anthropic Claude dependencies with Google Gemini 2.5 Pro while adding comprehensive multimodal document support (PDFs, scanned documents, JPG, PNG, WEBP).

**Key Changes:**
- ✅ Remove anthropic package entirely
- ✅ Integrate Google Generative AI SDK
- ✅ Add Gemini Vision OCR for scanned PDFs and images
- ✅ Support PDF, JPG, PNG, WEBP uploads
- ✅ Preserve all safety and clinical features
- ✅ Zero fabrication tolerance maintained

---

## 📊 Current → New Architecture

### Current (Claude-Based)
```
PDF
  ↓
PyMuPDF Text Extraction
  ↓
Claude API (Text Only)
  ↓
Agent Tools
  ↓
Summary
```

**Limitations:**
- ❌ Image-only PDFs fail
- ❌ Scanned documents not supported
- ❌ Handwritten notes missed
- ❌ No image upload support

### New (Gemini-Based Multimodal)
```
User Upload (PDF / JPG / PNG / WEBP)
  ↓
MultimodalDocumentProcessor
  ├─ PDF? → Determine Type
  │   ├─ Text PDF → PyMuPDF extraction
  │   └─ Scanned PDF → Convert page to image → Gemini Vision OCR
  ├─ Image? → Direct Gemini Vision processing
  │
  ↓
GeminiVisionOCR (if needed)
  ├─ Extract diagnoses, medications, allergies
  ├─ Extract procedures, labs, clinical notes
  ├─ Preserve evidence, confidence, page number
  │
  ↓
GeminiClinicalExtractor
  ├─ Structured extraction with safety validation
  ├─ Evidence grounding
  ├─ Confidence scoring
  │
  ↓
Knowledge Repository (with OCR metadata)
  ↓
Agent (with Gemini Planner/Reasoner/Summarizer)
  ↓
GeminiSummaryGenerator
  ├─ Demographics
  ├─ Hospital Course
  ├─ Diagnoses / Medications / Allergies
  ├─ Procedures / Labs
  ├─ Follow-up Instructions
  ├─ Safety Flags
  │
  ↓
Safety Engine (Existing - Enhanced for Gemini)
  ↓
Discharge Summary (Clinically Safe)
```

**Advantages:**
- ✅ Text + Scanned + Image PDFs
- ✅ Direct image uploads (JPG, PNG, WEBP)
- ✅ Handwritten support with confidence
- ✅ Multimodal vision processing
- ✅ Same safety guarantees

---

## 🔄 Migration Strategy

### Phase 1: Core Gemini Integration (Foundations)
**Deliverables:**
1. `backend/app/gemini/client.py` - GeminiClient wrapper
2. `backend/app/gemini/config.py` - Gemini configuration
3. `backend/app/gemini/vision.py` - GeminiVisionService
4. `backend/app/gemini/extraction.py` - GeminiClinicalExtractor
5. Update `requirements.txt` - Add google-generativeai, remove anthropic

**Outcome:** Core Gemini integration ready

---

### Phase 2: Multimodal Document Processing
**Deliverables:**
1. `backend/app/gemini/ocr.py` - GeminiVisionOCR
2. `backend/app/processing/multimodal.py` - MultimodalDocumentProcessor
3. Enhanced image extraction (PDF images + upload images)
4. Page classification (text vs scanned vs image)

**Outcome:** Can process PDFs and images with vision OCR

---

### Phase 3: Agent Migration
**Deliverables:**
1. `backend/app/gemini/planner.py` - GeminiPlanner (replaces Claude planner)
2. `backend/app/gemini/reasoner.py` - GeminiReasoner (replaces Claude reasoning)
3. `backend/app/gemini/summary.py` - GeminiSummaryGenerator (replaces Claude summary)
4. Update `backend/app/agent/planner.py` to use Gemini
5. Update `backend/app/agent/decision_engine.py` for Gemini prompts

**Outcome:** Agent fully uses Gemini for planning, reasoning, summarization

---

### Phase 4: Upload & Validation
**Deliverables:**
1. Enhanced `backend/app/api/documents.py` - PDF + image upload handling
2. Fixed upload validation - Accept PDF, JPG, JPEG, PNG, WEBP
3. File type detection and routing
4. Multi-file and mixed-file support

**Outcome:** Upload endpoint accepts all formats

---

### Phase 5: Frontend Updates
**Deliverables:**
1. Enhanced upload center component
2. Drag-and-drop support
3. File type preview
4. OCR/Vision processing status display
5. Mixed file upload display

**Outcome:** User can upload PDFs or images seamlessly

---

### Phase 6: Testing & Validation
**Deliverables:**
1. `backend/tests/test_gemini/` - Gemini integration tests
2. Test text PDF processing
3. Test scanned PDF processing
4. Test image upload (JPG, PNG, WEBP)
5. Test mixed uploads
6. Test vision OCR confidence scoring
7. Test handwritten note extraction
8. Test safety validation

**Outcome:** Comprehensive test coverage for Gemini

---

### Phase 7: Documentation & Deployment
**Deliverables:**
1. Migration guide (Claude → Gemini)
2. Updated environment variable docs
3. Deployment checklist
4. Troubleshooting guide
5. API changes documentation

**Outcome:** Team can deploy and support new system

---

## 🏗️ Implementation Details

### Module Structure

```
backend/app/gemini/
├── __init__.py
├── config.py              # Gemini configuration
├── client.py              # GeminiClient wrapper
├── vision.py              # GeminiVisionService
├── ocr.py                 # GeminiVisionOCR
├── extraction.py          # GeminiClinicalExtractor
├── planner.py             # GeminiPlanner (agent)
├── reasoner.py            # GeminiReasoner (agent)
└── summary.py             # GeminiSummaryGenerator

backend/app/processing/
├── multimodal.py          # MultimodalDocumentProcessor
└── (existing files)
```

### Key Classes

**GeminiClient**
```python
class GeminiClient:
    """Wrapper for Google Gemini API"""
    - configure(api_key: str)
    - get_vision_model() → GenerativeModel
    - get_chat_model() → GenerativeModel
    - health_check() → bool
```

**GeminiVisionOCR**
```python
class GeminiVisionOCR:
    """Extracts clinical content from images using Gemini Vision"""
    - extract_diagnoses(image) → List[Diagnosis]
    - extract_medications(image) → List[Medication]
    - extract_allergies(image) → List[Allergy]
    - extract_procedures(image) → List[Procedure]
    - extract_labs(image) → List[LabResult]
    - extract_clinical_notes(image) → str
    - get_confidence_score() → float
```

**GeminiClinicalExtractor**
```python
class GeminiClinicalExtractor:
    """Structured clinical extraction with safety validation"""
    - extract(text: str, source_type: str) → ExtractedData
    - validate_confidence(data) → SafetyLevel
    - preserve_evidence(data, source) → EvidencedFact
```

**MultimodalDocumentProcessor**
```python
class MultimodalDocumentProcessor:
    """Process PDFs and images"""
    - process_upload(file: UploadFile) → ProcessedDocument
    - process_pdf(pdf_path: str) → Dict
    - process_image(image_path: str) → Dict
    - determine_content_type(file) → ContentType
```

---

## 📋 Removed Components

**Remove completely:**
- `from anthropic import Anthropic`
- All Claude API calls
- Claude prompts and system messages
- Claude model configurations
- Anthropic error handling

**No longer needed:**
- ANTHROPIC_API_KEY env variable
- Claude-specific prompt templates
- Claude reasoning logic

---

## ✅ Requirements Changes

### Before (Claude)
```
anthropic>=0.28.0
```

### After (Gemini)
```
google-generativeai>=0.3.0
pillow>=10.0.0  (for image processing)
python-multipart>=0.0.5  (for file uploads)
```

---

## 🔐 Security & Safety

**Preserved:**
- ✅ Zero fabrication tolerance
- ✅ Evidence grounding requirement
- ✅ Confidence scoring
- ✅ Manual review flagging
- ✅ Safety validation engine
- ✅ Escalation management

**Enhanced:**
- ✅ OCR confidence thresholds
- ✅ Handwriting detection and flagging
- ✅ Image quality validation
- ✅ Multimodal source tracking

---

## 🚀 Deployment Checklist

- [ ] Update requirements.txt
- [ ] Update .env.example with GEMINI_API_KEY
- [ ] Run all tests
- [ ] Test with sample PDFs (text + scanned)
- [ ] Test with sample images (JPG, PNG, WEBP)
- [ ] Test upload center
- [ ] Verify agent execution with Gemini
- [ ] Check safety validation
- [ ] Review generated summaries
- [ ] Verify no Claude references remain
- [ ] Update documentation
- [ ] Deploy to staging
- [ ] Deploy to production

---

## 📅 Timeline

**Phase 1 (Gemini Core)**: 2-3 hours  
**Phase 2 (Multimodal Processing)**: 2-3 hours  
**Phase 3 (Agent Migration)**: 2-3 hours  
**Phase 4 (Upload & Validation)**: 1-2 hours  
**Phase 5 (Frontend)**: 1-2 hours  
**Phase 6 (Testing)**: 2-3 hours  
**Phase 7 (Documentation)**: 1 hour  

**Total Estimated Time**: 12-18 hours

---

## 🎯 Success Criteria

- ✅ All Claude references removed
- ✅ Gemini integration complete
- ✅ Text PDFs process correctly
- ✅ Scanned PDFs processed with vision OCR
- ✅ Images (JPG, PNG, WEBP) upload and process
- ✅ Handwritten notes detected and flagged
- ✅ Safety validation working
- ✅ All tests passing
- ✅ Frontend shows processing status
- ✅ Discharge summaries generated with Gemini
- ✅ No performance degradation
- ✅ Documentation complete

---

## 🔄 Rollback Plan

If issues occur:
1. Revert to previous branch
2. Claude dependencies still in git history
3. Database schema unchanged
4. Frontend changes backward compatible
5. No data migration required

---

## 📞 Support & Troubleshooting

**Common Issues:**
1. GEMINI_API_KEY not set → Check .env file
2. Image processing slow → Gemini Vision is slower than text, expected
3. OCR accuracy low → Use higher confidence threshold, flag for review
4. Upload fails → Check file type, file size limits

---

**Ready to Begin Implementation?**

Start with Phase 1: Core Gemini Integration

---

*Last Updated: 2026-06-06*  
*Status: Ready for Implementation*
