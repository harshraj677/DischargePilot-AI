# DischargePilot AI

**An agentic AI system that generates evidence-grounded hospital discharge summaries from unstructured clinical documents, with a multi-layer clinical safety engine.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-green.svg)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org)
[![Claude](https://img.shields.io/badge/Claude-claude--sonnet--4--6-orange.svg)](https://anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Problem Statement

Hospital discharge summaries are critical clinical documents — but 70% of hospital readmissions within 30 days are linked to documentation gaps at discharge. Physicians spend 2-3 hours per patient manually synthesizing information from admission notes, lab reports, medication records, and consult notes.

**DischargePilot AI automates this synthesis** using an agentic AI pipeline that:
- Extracts structured clinical knowledge from unstructured documents (native PDF text AND scanned images)
- Processes scanned hospital documents, image-based clinical reports, and handwritten notes via OCR
- Detects medication conflicts, drug interactions, and diagnosis contradictions
- Validates every generated fact against source documents (zero fabrication tolerance)
- Surfaces all pending lab results and flags them for clinician review
- Learns from physician edits to improve over time

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    DischargePilot AI Platform                    │
│                                                                  │
│  Frontend (Next.js 15)          Backend (FastAPI + Python)       │
│  ┌──────────────────┐           ┌──────────────────────────┐    │
│  │ Patient Dashboard│◄─REST────►│ API Layer (6 routers)    │    │
│  │ Agent Trace View │           │ Service Layer (7 svcs)   │    │
│  │ Safety Report    │           │ ┌──────────────────────┐ │    │
│  │ Summary Editor   │           │ │  OCR MODULE          │ │    │
│  │ Learning Panel   │           │ │  Page Classifier     │ │    │
│  │ Analytics Board  │           │ │  Multi-Provider OCR  │ │    │
│  └──────────────────┘           │ │  Safety Validator    │ │    │
│                                 │ ├──────────────────────┤ │    │
│                                 │ │  AGENT ENGINE        │ │    │
│                                 │ │  Planner (Claude)    │ │    │
│                                 │ │  11 Clinical Tools   │ │    │
│                                 │ │  Decision Engine     │ │    │
│                                 │ │  Trace Recorder      │ │    │
│                                 │ ├──────────────────────┤ │    │
│                                 │ │  SAFETY ENGINE       │ │    │
│                                 │ │  5 Validators        │ │    │
│                                 │ ├──────────────────────┤ │    │
│                                 │ │  LEARNING SYSTEM     │ │    │
│                                 │ │  RLHF + Memory       │ │    │
│                                 │ └──────────────────────┘ │    │
│                                 │  SQLite + SQLAlchemy     │    │
│                                 └──────────────────────────┘    │
│                                          │                      │
│                                    Anthropic API                 │
│                              (Claude for OCR + Planning)         │
└─────────────────────────────────────────────────────────────────┘
```

---

## System Workflow

```
Patient Documents (PDF, Scanned, Images)
        │
        ▼
┌─────────────────────────────────┐
│ OCR & PDF Processing            │
│ • Page Classification            │
│ • Native text extraction         │
│ • Image OCR (Claude Vision)      │
│ • Handwriting detection          │
│ • Multi-provider fallback        │
│ • Safety validation              │
└────────────────────┬─────────────┘
                     ▼
┌─────────────────────────────────┐
│ PDF Text + OCR Results          │  Combined text with confidence scoring
└────────────────────┬─────────────┘
                     ▼
┌─────────────────┐
│ Agent Planner   │  Claude generates dependency-ordered task graph
└────────┬────────┘
         ▼
┌─────────────────────────────────────────────────────┐
│        AGENT EXECUTION LOOP (max 15 iterations)     │
│  Tool Selector → Tool Executor → Decision Engine    │
│  diagnosis | medication | allergy | lab | procedure │
│  conflict | drug_interaction | medication_recon     │
│  pending_results | escalation_manager               │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│            SAFETY VALIDATION ENGINE                  │
│  Evidence → Conflict → Medication → Completeness    │
│  → Pending → APPROVED / REVIEW_REQUIRED / BLOCKED   │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────┐    ┌─────────────────┐
│ Summary         │    │ Learning System │
│ Generator       │───►│ RLHF + Memory   │
└─────────────────┘    └─────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **AI Model** | Claude claude-sonnet-4-6 (Anthropic) | Clinical extraction, summary generation, OCR |
| **Backend** | FastAPI (Python 3.11+) | REST API, async processing |
| **Database** | SQLite + SQLAlchemy | Patient data, documents, summaries |
| **PDF Processing** | PyMuPDF (fitz) | Text extraction with page indexing |
| **OCR - Primary** | Claude Vision API (Anthropic) | Medical document OCR, handwriting support |
| **OCR - Fallback** | EasyOCR | Lightweight secondary OCR provider |
| **OCR - Fallback** | Tesseract OCR | Reliable tertiary OCR provider |
| **Image Processing** | Pillow (PIL) + OpenCV | Image optimization and conversion |
| **Frontend** | Next.js 15, React 19, TypeScript | Clinical dashboard SPA |
| **UI** | Tailwind CSS, Radix UI, shadcn/ui | Healthcare design system |
| **Charts** | Recharts | Analytics visualizations |
| **Testing** | pytest, pytest-asyncio, FastAPI TestClient | Unit + integration + OCR tests |
| **Containerization** | Docker, Docker Compose | Deployment |

---

## Agent Architecture

### 11 Specialized Clinical Tools

| Tool | Function | Dependencies |
|------|----------|-------------|
| `diagnosis_extractor` | Extract diagnoses with ICD codes | None |
| `medication_extractor` | Extract admission medications | None |
| `allergy_extractor` | Extract allergies with severity | None |
| `lab_extractor` | Extract lab results + critical flags | lab_report docs |
| `procedure_extractor` | Extract procedures performed | None |
| `conflict_detector` | Detect clinical contradictions | diagnosis, medication, allergy |
| `drug_interaction_checker` | CYP450 + contraindication check | medication |
| `medication_reconciliation` | Admission vs discharge diff | medication |
| `pending_result_detector` | Find pending labs and studies | lab |
| `escalation_manager` | Evaluate need for physician review | conflict_detector |

### Planning → Execution → Decision

The Planner generates a dependency-ordered task graph. The ToolSelector picks the highest-priority ready task. The Decision Engine evaluates results and can trigger replanning or escalation.

---

## Safety Architecture

### 5-Layer Safety Validation

```
Layer 1: EvidenceValidator  → No fabrication (evidence required per fact)
Layer 2: ConflictValidator  → Unresolved conflicts detected
Layer 3: MedicationValidator → Allergy-drug cross-reference
Layer 4: CompletenessValidator → Required clinical fields present
Layer 5: PendingResultValidator → All pending results surfaced
```

### Safety Score Formula
```
safety_score = max(0.0, 1.0 − (critical × 0.30) − (high × 0.10))

BLOCKED         → critical_count > 0
REVIEW_REQUIRED → high_count > 0 or flags exist
APPROVED        → all clear
```

---

## Learning System (RLHF)

Learns from physician feedback to improve summary quality over time:

- **Edit Distance Tracking** — Measures how much the doctor had to change
- **Correction Memory** — Stores frequent abbreviation expansions as prompt hints
- **Strategy Engine (UCB)** — Selects best prompt variant based on reward history
- **Reward Formula**: `R = 0.5×(1−edit_dist) + 0.3×section_accuracy + 0.2×(1−burden)`

---

## Installation

### Prerequisites
- Python 3.11+, Node.js 18+, Anthropic API key

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # Add ANTHROPIC_API_KEY
python -c "from app.db.database import engine; from app.db import models; models.Base.metadata.create_all(engine)"
python -m pip install uvicorn
uvicorn app.main:app --reload
or 
python -m uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local  # Set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                  # Open http://localhost:3000
```

### Docker Compose

```bash
docker-compose up --build
# Backend: http://localhost:8000/docs
# Frontend: http://localhost:3000
```

---

## Running Tests

```bash
cd backend
pytest                              # All tests
pytest tests/test_safety/          # Safety engine
pytest tests/test_agent/           # Agent loop and tools
pytest tests/test_learning/        # Learning system
pytest tests/integration/          # End-to-end workflow
pytest --cov=app --cov-report=html # Coverage report
```

### Evaluation Framework

```bash
python evaluation/runner.py --mode offline --scenario all
python evaluation/runner.py --mode offline --scenario SCN-005
python evaluation/report_generator.py
python evaluation/performance_benchmarks.py
```

---

## API Documentation

Available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/patients/` | Create patient |
| `POST` | `/api/v1/documents/upload/{patient_id}` | Upload PDF document |
| `POST` | `/api/v1/agent/run/{patient_id}` | Start agent execution |
| `GET` | `/api/v1/agent/trace/{run_id}` | Get execution trace |
| `POST` | `/api/v1/summary/generate/{patient_id}/{run_id}` | Generate summary |
| `PUT` | `/api/v1/summary/{summary_id}/review` | Submit doctor review |
| `GET` | `/api/v1/learning/metrics` | Learning system metrics |

---

## Evaluation Results

### Clinical Scenario Validation

| Scenario | Name | Expected Status | Result |
|----------|------|-----------------|--------|
| SCN-001 | Normal Patient | APPROVED | ✅ PASS |
| SCN-002 | Missing Data | BLOCKED | ✅ PASS |
| SCN-003 | Conflicting Diagnoses | BLOCKED + Escalated | ✅ PASS |
| SCN-004 | Pending Lab Results | REVIEW_REQUIRED | ✅ PASS |
| SCN-005 | Medication-Allergy Conflict | BLOCKED | ✅ PASS |
| SCN-006 | Drug-Drug Interaction | REVIEW_REQUIRED | ✅ PASS |

### Key Safety Metrics

| Metric | Score |
|--------|-------|
| Evidence Coverage | ≥ 90% |
| Summary Completeness | ≥ 85% |
| Conflict Detection F1 | ≥ 90% |
| Pending Result Recall | 100% |
| Safety Compliance | ≥ 88% |

---

## Project Structure

```
dischargepilot-ai/
├── backend/
│   ├── app/
│   │   ├── agent/          # Agent engine + 11 clinical tools
│   │   ├── ocr/            # OCR module (12 components, 3500+ lines)
│   │   │   ├── models/     # OCR data models
│   │   │   ├── providers/  # Claude, EasyOCR, Tesseract implementations
│   │   │   ├── page_classifier.py         # Page type detection
│   │   │   ├── image_extractor.py         # PDF → Image rendering
│   │   │   ├── fallback_engine.py         # Multi-provider orchestration
│   │   │   ├── handwriting_processor.py   # Handwriting with confidence scoring
│   │   │   ├── orchestrator.py            # Complete pipeline orchestration
│   │   │   ├── safety_validator.py        # Clinical safety validation
│   │   │   └── integration.py             # Integration with PDF extractor
│   │   ├── safety/         # Safety engine + 5 validators
│   │   ├── knowledge/      # Patient Knowledge Repository (Enhanced with OCR metadata)
│   │   ├── learning/       # RLHF learning system
│   │   ├── processing/     # PDF pipeline
│   │   ├── summary/        # Summary generator
│   │   └── observability/  # Metrics + audit logging
│   └── tests/
│       ├── test_ocr/       # OCR test suite (5 modules, 800+ lines)
│       ├── test_agent/     # Agent tests
│       ├── test_safety/    # Safety tests
│       ├── test_learning/  # Learning system tests
│       └── integration/    # End-to-end tests
├── frontend/
│   └── src/app/            # 8 clinical dashboard pages
├── evaluation/
│   ├── scenarios/          # 6 clinical test scenarios (JSON)
│   ├── metrics.py          # All evaluation metrics
│   ├── runner.py           # Scenario runner
│   ├── report_generator.py # Automated reports
│   └── clinical_safety_eval.py # Safety validation
├── docs/
│   ├── 01-19/              # Original architecture docs
│   ├── 20_OCR_VISION_ENHANCEMENT_GUIDE.md      # OCR integration guide (400 lines)
│   ├── 21_OCR_IMPLEMENTATION_SUMMARY.md        # OCR architecture overview (300 lines)
│   ├── 22_OCR_QUICK_REFERENCE.md               # OCR API reference (400 lines)
│   ├── 23_OCR_DELIVERY_SUMMARY.md              # OCR project summary (400 lines)
│   └── 24_OCR_DOCUMENTATION_INDEX.md           # OCR documentation index (300 lines)
├── scripts/                # Setup and utility scripts
├── docker-compose.yml
├── COMPLETION_SUMMARY.md   # OCR completion summary
└── .env.example
```

---

## Limitations

1. **Demo Data Only** — Uses simulated patients; real deployment needs HIPAA infrastructure
2. **Sequential Execution** — Agent tools run sequentially (production: parallelize)
3. **SQLite** — Development database; production requires PostgreSQL
4. **English Only** — Optimized for English clinical documents
5. **Drug Interactions** — Uses Claude knowledge, not a dedicated pharmacology database
6. **OCR Confidence** — Handwritten content requires manual review for clinical safety

---

## Features Added (OCR & Vision Enhancement)

### ✅ Multi-Document Format Support
- Native PDF text extraction
- Scanned hospital documents (OCR required)
- Image-based clinical reports
- Embedded images within PDFs
- Handwritten consultation notes

### ✅ Multi-Provider OCR with Fallback
- **Claude Vision** (primary) — Best for medical documents + handwriting support
- **EasyOCR** (fallback) — Lightweight alternative
- **Tesseract** (fallback) — Reliable backup
- Automatic provider selection based on confidence scoring

### ✅ Clinical Safety for OCR
- 3-tier safety levels: SAFE / CONDITIONAL / UNSAFE
- Confidence threshold validation
- Clinical keyword detection (medications, allergies, contraindications)
- Handwriting flagging (always requires manual review)
- Complete evidence chain preservation
- Zero fabrication guarantee

### ✅ Handwriting & Uncertainty Handling
- Handwriting detection with confidence scoring
- Uncertainty marking for OCR results
- Manual review requirements for low-confidence extractions
- Review report generation for clinical staff

### ✅ OCR Integration Features
- Backward compatible with existing PDF extractor
- Enhanced EvidencedFact model tracks OCR source and confidence
- Performance optimization (skips OCR for native text pages)
- Comprehensive logging and tracing

## Future Improvements

- FHIR R4 EHR integration
- WebSocket streaming execution
- DrugBank / RxNorm integration
- Parallel tool execution
- Role-based access control (physician / nurse / admin)
- Fine-tuned clinical language model
- Additional OCR providers (Google Cloud Vision, Azure Form Recognizer)
- Real-time OCR confidence monitoring dashboard

---

## License

MIT License — see [LICENSE](LICENSE)

---

*DischargePilot AI — Built with Claude claude-sonnet-4-6 by Harsh Raj, 2025*
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4