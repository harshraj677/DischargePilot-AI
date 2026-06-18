# DischargePilot AI

**An agentic AI system that generates evidence-grounded hospital discharge summaries from unstructured clinical documents, backed by a multi-layer clinical safety engine.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org)
[![Groq](https://img.shields.io/badge/Groq-llama--3.3--70b-orange.svg)](https://groq.com)
[![Claude](https://img.shields.io/badge/Claude-Sonnet%204.6%20(OCR%20fallback)-6b4fbb.svg)](https://anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Problem Statement

Hospital discharge summaries are critical clinical documents — yet 70% of 30-day hospital readmissions are linked to documentation gaps at discharge. Physicians routinely spend 2–3 hours per patient manually synthesizing information scattered across admission notes, lab reports, medication records, and consult notes.

**DischargePilot AI automates this synthesis** with an agentic AI pipeline that:

- Extracts structured clinical knowledge from unstructured documents (native PDF text **and** scanned images)
- Processes scanned hospital documents, image-based clinical reports, and handwritten notes via multi-provider OCR
- Detects medication conflicts, drug interactions, and diagnosis contradictions
- Validates every generated fact against source documents — zero fabrication tolerance
- Runs a second, LLM-driven clinical documentation QA pass that catches missing data, pending results, and guideline-aware medication issues while explicitly minimizing false positives and alert fatigue
- Surfaces all pending lab results and flags them for clinician review
- Learns from physician edits to improve over time

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                       DischargePilot AI Platform                      │
│                                                                        │
│  Frontend (Next.js 15)            Backend (FastAPI + Python 3.11)     │
│  ┌───────────────────┐            ┌───────────────────────────────┐  │
│  │ Patient Dashboard  │◄──REST────►│ API Layer (7 routers)         │  │
│  │ Agent Trace View   │            │ Service Layer                 │  │
│  │ Safety Report      │            │ ┌───────────────────────────┐ │  │
│  │ Summary Editor     │            │ │  OCR MODULE                │ │  │
│  │ Learning Panel     │            │ │  Page Classifier            │ │  │
│  │ Analytics Board    │            │ │  Multi-Provider OCR         │ │  │
│  └───────────────────┘            │ │  Safety Validator           │ │  │
│                                    │ ├───────────────────────────┤ │  │
│                                    │ │  AGENT ENGINE               │ │  │
│                                    │ │  Planner (Groq)              │ │  │
│                                    │ │  11 Clinical Tools           │ │  │
│                                    │ │  Decision Engine             │ │  │
│                                    │ │  Trace Recorder              │ │  │
│                                    │ ├───────────────────────────┤ │  │
│                                    │ │  SAFETY ENGINE               │ │  │
│                                    │ │  5 Deterministic Validators  │ │  │
│                                    │ │  + LLM Clinical Reviewer     │ │  │
│                                    │ ├───────────────────────────┤ │  │
│                                    │ │  LEARNING SYSTEM             │ │  │
│                                    │ │  RLHF + Correction Memory    │ │  │
│                                    │ └───────────────────────────┘ │  │
│                                    │  SQLite + SQLAlchemy           │  │
│                                    └───────────────────────────────┘  │
│                                              │                         │
│                                    Groq API (primary)                 │
│                              Anthropic Claude API (OCR fallback)      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## System Workflow

```
Patient Documents (PDF, Scanned, Images)
        │
        ▼
┌───────────────────────────────────┐
│ OCR & PDF Processing               │
│ • Page classification              │
│ • Native text extraction           │
│ • Image OCR (Groq Vision, primary) │
│ • Claude Vision (OCR fallback)     │
│ • Handwriting detection            │
│ • Multi-provider fallback chain    │
│ • Safety validation                │
└──────────────────┬──────────────────┘
                   ▼
┌───────────────────────────────────┐
│ Combined Text + Confidence Scores  │
└──────────────────┬──────────────────┘
                   ▼
┌─────────────────┐
│ Agent Planner    │  Groq generates a dependency-ordered task graph
└────────┬─────────┘
         ▼
┌───────────────────────────────────────────────────────────┐
│           AGENT EXECUTION LOOP (max 20 iterations)         │
│  Tool Selector → Tool Executor → Decision Engine            │
│  diagnosis → medication → allergy → procedure → lab        │
│  → pending_result → conflict_detector → medication_recon   │
│  → drug_interaction_checker → escalation_manager            │
│  → summary_generator → terminator                           │
│                                                              │
│  Escalation never bypasses summary generation — every run   │
│  (COMPLETED or ESCALATED) produces a persisted summary.     │
└──────────────────┬───────────────────────────────────────────┘
                   ▼
┌───────────────────────────────────────────────────────────┐
│                  SAFETY VALIDATION ENGINE                  │
│  Evidence → Conflict → Medication → Completeness → Pending  │
│  + LLM Clinical Reviewer (evidence-gated, alert-fatigue-aware)│
│  → APPROVED / REVIEW_REQUIRED / BLOCKED                      │
└──────────────────┬───────────────────────────────────────────┘
                   ▼
┌──────────────────┐    ┌───────────────────┐
│ Discharge Summary │───►│ Learning System    │
│ Generator + Save  │    │ RLHF + Memory       │
└──────────────────┘    └───────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **AI Model — Primary** | Groq (`llama-3.3-70b-versatile`) | Planning, clinical extraction, summary generation, vision OCR |
| **AI Model — OCR Fallback** | Anthropic Claude (Sonnet 4.6 / Opus 4.8) | Secondary OCR provider when Groq is unavailable |
| **Backend** | FastAPI (Python 3.11+) | REST API, async processing |
| **Database** | SQLite + SQLAlchemy | Patients, documents, agent runs, discharge reports |
| **PDF Processing** | PyMuPDF (fitz) | Text extraction with page indexing |
| **OCR — Primary** | Groq Vision (`llama-4-scout`) | Medical document OCR, handwriting support |
| **OCR — Fallback** | Claude Vision, EasyOCR, Tesseract | Multi-tier fallback chain |
| **Image Processing** | Pillow (PIL) + OpenCV | Image optimization and conversion |
| **Frontend** | Next.js 15, React 19, TypeScript | Clinical dashboard SPA |
| **UI** | Tailwind CSS, Radix UI, shadcn/ui | Healthcare design system |
| **Charts** | Recharts | Analytics visualizations |
| **Testing** | pytest, pytest-asyncio, FastAPI TestClient | Unit, integration, and OCR test suites |
| **Containerization** | Docker, Docker Compose | Deployment |

---

## Agent Architecture

### 11 Specialized Clinical Tools

| Tool | Function | Depends On |
|------|----------|-----------|
| `diagnosis_extractor` | Extract diagnoses with ICD codes | — |
| `medication_extractor` | Extract admission/discharge medications | — |
| `allergy_extractor` | Extract allergies with severity and NKDA status | — |
| `procedure_extractor` | Extract procedures performed | — |
| `lab_extractor` | Extract lab results and flag critical values | lab_report docs |
| `pending_result_extractor` | Find pending labs and studies awaiting follow-up | — |
| `conflict_detector` | Detect clinical contradictions across facts | diagnosis, medication, allergy |
| `medication_reconciler` | Diff admission vs. discharge medications | medication |
| `drug_interaction_checker` | Drug–drug interaction and contraindication check | medication |
| `escalation_manager` | Evaluate whether physician escalation is required | conflict_detector, medication_reconciler |
| `summary_generator` | Generate and persist the structured discharge summary | the full pipeline above, including escalation_manager |

### Planning → Execution → Decision

The **Planner** generates a dependency-ordered task graph. The **Tool Selector** picks the highest-priority ready task each iteration. The **Decision Engine** evaluates each result and can trigger bounded replanning. The **Termination Controller** guarantees the loop always reaches `summary_generator` — even on escalation or a stalled dependency — before reporting `COMPLETED`, `ESCALATED`, or `TIMED_OUT`.

---

## Safety Architecture

### 6-Layer Safety Validation

```
Layer 1: EvidenceValidator        → No fabrication — evidence required per fact
Layer 2: ConflictValidator        → Unresolved clinical conflicts detected
Layer 3: MedicationValidator      → Allergy–drug cross-reference, high-risk dosing
Layer 4: CompletenessValidator    → Required clinical fields present
Layer 5: PendingResultValidator   → All pending results surfaced
Layer 6: LLM Clinical Reviewer    → Evidence-gated QA pass for missing data, pending
                                     results, medication discrepancies, and
                                     guideline-aware conflict detection — tuned to
                                     minimize false positives and alert fatigue
```

The LLM Clinical Reviewer (`app/safety/llm_reviewer.py`) runs alongside — not instead of — the deterministic validators. Its findings feed into the same aggregate safety score and flag pool. Every finding it produces must cite explicit evidence (source record, lab value, medication, or guideline); findings without evidence are dropped before they ever reach a clinician. Only `HIGH` severity **and** `High` confidence findings require acknowledgment before a summary can be approved.

### Safety Score Formula

```
safety_score = max(0.0, 1.0 − (critical_count × 0.30) − (high_count × 0.10))

BLOCKED         → critical_count > 0
REVIEW_REQUIRED → high_count > 0 or review flags exist
APPROVED        → all clear
```

A `BLOCKED` or `ESCALATED` status never prevents the discharge summary from being generated — it is always produced, with the relevant findings attached as review flags requiring clinician sign-off.

---

## Learning System (RLHF)

Learns from physician feedback to improve summary quality over time:

- **Edit Distance Tracking** — measures how much the doctor had to change
- **Correction Memory** — stores frequent abbreviation expansions as prompt hints
- **Strategy Engine (UCB)** — selects the best prompt variant based on reward history
- **Reward Formula** — `R = 0.5×(1−edit_dist) + 0.3×section_accuracy + 0.2×(1−burden)`

---

## Installation

### Prerequisites

- Python 3.11+, Node.js 18+
- A [Groq API key](https://console.groq.com) (primary AI provider, free tier available)
- An [Anthropic API key](https://console.anthropic.com) (optional — used only as the OCR fallback provider)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # Add GROQ_API_KEY (and optionally ANTHROPIC_API_KEY)
python -c "from app.db.database import engine; from app.db import models; models.Base.metadata.create_all(engine)"
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local        # Set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                       # Open http://localhost:3000
```

### Docker Compose

```bash
docker-compose up --build
# Backend:  http://localhost:8000/docs
# Frontend: http://localhost:3000
```

---

## Running Tests

```bash
cd backend
pytest                              # All tests
pytest tests/test_safety/           # Safety engine + LLM clinical reviewer
pytest tests/test_agent/            # Agent loop and tools
pytest tests/test_groq/             # Groq provider client, cache, rate limiter
pytest tests/test_learning/         # Learning system
pytest tests/integration/           # End-to-end workflow
pytest --cov=app --cov-report=html  # Coverage report
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
| `POST` | `/api/v1/patients` | Create patient |
| `POST` | `/api/v1/patients/{patient_id}/documents` | Upload a clinical document |
| `POST` | `/api/v1/agent/patients/{patient_id}/runs` | Start an agent run |
| `GET` | `/api/v1/agent/runs/{run_id}/trace` | Get the full execution trace |
| `GET` | `/api/v1/agent/runs/{run_id}/knowledge-base` | Inspect the extracted knowledge base |
| `GET` | `/api/v1/summary/patients/{patient_id}/runs/{run_id}/safety` | Get the safety report |
| `POST` | `/api/v1/summary/patients/{patient_id}/runs/{run_id}/generate` | Generate the discharge summary |
| `GET` | `/api/v1/summary/patients/{patient_id}/runs/{run_id}/summary` | Retrieve the persisted summary |
| `POST` | `/api/v1/summary/patients/{patient_id}/runs/{run_id}/summary/approve` | Approve the summary |
| `POST` | `/api/v1/summary/patients/{patient_id}/runs/{run_id}/summary/reject` | Reject the summary |
| `GET` | `/api/v1/learning/metrics` | Learning system metrics |
| `GET` | `/api/v1/system/llm-status` | Provider health (Groq + Claude) |

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
│   │   ├── agent/             # Agent loop, planner, executor, terminator + 11 clinical tools
│   │   ├── groq_provider/     # Groq client, caching, rate limiting, health checks
│   │   ├── ocr/                # OCR module
│   │   │   ├── providers/      # groq, claude, easyocr, tesseract implementations
│   │   │   ├── page_classifier.py
│   │   │   ├── image_extractor.py
│   │   │   ├── fallback_engine.py
│   │   │   ├── handwriting_processor.py
│   │   │   ├── orchestrator.py
│   │   │   └── safety_validator.py
│   │   ├── safety/             # 5 deterministic validators + LLM clinical reviewer
│   │   ├── knowledge/           # Patient knowledge repository
│   │   ├── learning/            # RLHF learning system
│   │   ├── processing/          # PDF / document pipeline
│   │   ├── summary/             # Discharge summary generator
│   │   └── api/                 # 7 routers (patients, documents, agent, summary, learning, system, debug)
│   └── tests/
│       ├── test_groq/           # Groq provider tests
│       ├── test_ocr/            # OCR test suite
│       ├── test_agent/          # Agent loop and tool tests
│       ├── test_safety/         # Safety engine + LLM reviewer tests
│       ├── test_learning/       # Learning system tests
│       └── integration/         # End-to-end workflow tests
├── frontend/
│   └── src/app/                 # 11 clinical dashboard pages
├── evaluation/
│   ├── scenarios/                # 6 clinical test scenarios (JSON)
│   ├── metrics.py
│   ├── runner.py
│   ├── report_generator.py
│   └── clinical_safety_eval.py
├── docs/                         # Architecture, design, and migration documentation
├── docker-compose.yml
└── .env.example
```

---

## Limitations

1. **Demo Data Only** — uses simulated patients; real deployment requires HIPAA-compliant infrastructure
2. **Sequential Execution** — agent tools run sequentially (production would parallelize independent extractors)
3. **SQLite** — development database; production requires PostgreSQL
4. **English Only** — optimized for English-language clinical documents
5. **Drug Interactions** — uses LLM clinical knowledge, not a dedicated pharmacology database (e.g. DrugBank)
6. **OCR Confidence** — handwritten content always requires manual clinician review

---

## OCR & Vision Capabilities

### Multi-Document Format Support
- Native PDF text extraction
- Scanned hospital documents
- Image-based clinical reports
- Embedded images within PDFs
- Handwritten consultation notes

### Multi-Provider OCR with Fallback
- **Groq Vision** (primary) — fast, cost-effective medical document OCR
- **Claude Vision** (fallback) — used when Groq is unavailable
- **EasyOCR / Tesseract** (further fallbacks) — lightweight, reliable backups
- Automatic provider selection based on confidence scoring

### Clinical Safety for OCR
- Three-tier safety levels: SAFE / CONDITIONAL / UNSAFE
- Confidence threshold validation
- Clinical keyword detection (medications, allergies, contraindications)
- Handwriting always flagged for manual review
- Complete evidence chain preservation — zero fabrication guarantee

---

## Future Improvements

- FHIR R4 EHR integration
- WebSocket streaming execution
- DrugBank / RxNorm integration for deterministic interaction checking
- Parallel tool execution
- Role-based access control (physician / nurse / admin)
- Fine-tuned clinical language model
- Additional OCR providers (Google Cloud Vision, Azure Form Recognizer)
- Real-time OCR and safety-score monitoring dashboard

---

## License

MIT License — see [LICENSE](LICENSE)

---

*DischargePilot AI — built by Harsh Raj.*


