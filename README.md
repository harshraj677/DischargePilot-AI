<div align="center">

# DischargePilot AI

### Agentic Clinical Discharge Summary Assistant
#### Evidence-Based Safety Validation · Full Clinical Observability · Clinician-in-the-Loop

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=flat&logo=next.js&logoColor=white)](https://nextjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?style=flat&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Claude](https://img.shields.io/badge/Claude_API-Anthropic-E97028?style=flat)](https://anthropic.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

</div>

---

## Overview

**DischargePilot AI** is a production-grade healthcare AI platform that reads patient clinical source-note PDFs and generates structured discharge summary drafts for clinician review.

This is **not** a PDF summarization tool. It is a true **agentic AI system** that:

- Plans and re-plans its extraction strategy based on available documents
- Uses specialized clinical tools for entity extraction, medication reconciliation, and conflict detection
- Maintains an agent memory that accumulates clinical knowledge across tool executions
- Runs an independent safety validation layer that blocks ungrounded outputs
- Generates a structured, evidence-cited discharge summary draft
- Presents every finding to the clinician for final review and approval

> **The system never auto-finalizes clinical documents. The clinician is always the decision-maker.**

---

## The Problem

| Root Cause | Clinical Impact |
|---|---|
| Fragmented notes across multiple documents | Critical details missed at discharge |
| No automated medication reconciliation | Dangerous polypharmacy and dose errors |
| Manual documentation under time pressure | Rushed, incomplete discharge summaries |
| No structured safety validation | Conflicts and gaps reach the patient |
| No evidence traceability | Unable to audit what a summary is based on |

**1 in 5 patients** are readmitted within 30 days. **40–50%** of medication errors occur at care transitions. Clinicians spend **2–4 hours per patient** on discharge documentation.

---

## Key Features

### Agentic Reasoning Engine
- Custom agent loop with Planner, Tool Selector, Executor, Re-Planner, and Terminator
- Agent re-plans dynamically when gaps or conflicts are detected mid-execution
- Full execution trace logged to SQLite — every tool call is auditable
- Maximum iteration guard prevents infinite loops

### Clinical Safety Layer
- **Fabrication Guard** — every generated statement must trace to a source document
- **Conflict Detector** — surfaces all cross-document inconsistencies
- **Medication Safety Checker** — allergy conflicts, dose discrepancies, drug interactions
- **Completeness Validator** — missing fields explicitly marked, never omitted silently
- **Pending Results Guard** — lab results awaited in source remain flagged as pending

### Evidence-Grounded Output
- Every section of the discharge summary cites its source document, page number, and exact excerpt
- Missing information marked as `[NOT DOCUMENTED IN SOURCE DOCUMENTS]`
- Uncertain content marked as `[NEEDS CLINICIAN REVIEW]`
- Confidence level (High / Medium / Needs Review) on every section

### Full Observability
- Real-time agent execution timeline
- Complete trace viewer showing every tool's input, output, and reasoning
- Safety flag audit trail with resolution history
- Analytics dashboard for platform-wide quality metrics

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DISCHARGEPILOT AI PLATFORM                       │
│                                                                         │
│   FRONTEND (Next.js 15)          BACKEND (FastAPI + Python)             │
│   ┌──────────────────────┐       ┌────────────────────────────────┐    │
│   │  Dashboard           │       │  PDF Processing Engine         │    │
│   │  Upload Center       │◄─────►│  Agent Engine                  │    │
│   │  Execution Center    │ REST  │  ├── Planner                   │    │
│   │  Trace Viewer        │       │  ├── Tool Selector              │    │
│   │  Safety Review       │       │  ├── Executor                  │    │
│   │  Summary Viewer      │       │  ├── Re-Planner                │    │
│   │  Analytics           │       │  └── Safety Validator          │    │
│   └──────────────────────┘       │                                │    │
│                                  │  Tool Layer                    │    │
│                                  │  ├── extract_demographics      │    │
│                                  │  ├── extract_diagnoses         │    │
│                                  │  ├── extract_medications       │    │
│                                  │  ├── reconcile_medications     │    │
│                                  │  ├── detect_conflicts          │    │
│                                  │  ├── validate_safety           │    │
│                                  │  └── build_section             │    │
│                                  │                                │    │
│                                  │  Claude API  │  SQLite DB      │    │
│                                  └────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

**Complete architecture documentation** → [`docs/02_SYSTEM_ARCHITECTURE.md`](docs/02_SYSTEM_ARCHITECTURE.md)

---

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | Next.js 15, TypeScript | React framework with App Router |
| **UI Library** | Tailwind CSS, shadcn/ui | Accessible component system |
| **Animations** | Framer Motion | Clinical-appropriate transitions |
| **Backend** | Python 3.12, FastAPI | High-performance async API |
| **Validation** | Pydantic v2 | Strict data model validation |
| **AI Layer** | Claude API (Anthropic) | Structured clinical reasoning |
| **PDF Processing** | PyMuPDF | Page-indexed text extraction |
| **Database** | SQLite + SQLAlchemy | Persistent storage with migrations |
| **Migrations** | Alembic | Schema versioning |

---

## Project Structure

```
dischargepilot-ai/
├── frontend/                    # Next.js 15 TypeScript application
│   └── src/
│       ├── app/                 # App Router pages
│       ├── components/          # Clinical UI components
│       ├── hooks/               # Data fetching hooks
│       └── lib/                 # API client, types, utilities
│
├── backend/
│   └── app/
│       ├── api/                 # FastAPI route handlers
│       ├── agent/               # Agent engine + all tools
│       │   ├── tools/           # Individual clinical tools
│       │   └── safety/          # Safety validation subsystem
│       ├── claude/              # Claude API client + prompts
│       ├── db/                  # SQLAlchemy models + repositories
│       ├── models/              # Pydantic schemas
│       ├── processing/          # PDF extraction pipeline
│       └── services/            # Business logic layer
│
└── docs/                        # Complete architecture blueprint
```

**Full folder structure** → [`docs/03_FOLDER_STRUCTURE.md`](docs/03_FOLDER_STRUCTURE.md)

---

## Agent Architecture

The agent follows a goal-directed, stateful execution loop:

```
START
  │
  ▼
[Planner] ──── Generates extraction plan from available document types
  │
  ▼
[Tool Selector] ── Picks next tool respecting dependencies
  │
  ▼
[Executor] ──── Runs tool, updates AgentMemory, writes trace
  │
  ▼
[Re-Planner] ── Detects gaps, conflicts → inserts additional steps
  │
  ▼
[Safety Validator] ── Runs all 5 safety checks before generation
  │
  ▼
[Summary Generator] ── Builds all 14 sections with evidence links
  │
  ▼
END ── Summary + Safety Flags → Clinician Review
```

**Full agent design** → [`docs/04_AGENT_ARCHITECTURE.md`](docs/04_AGENT_ARCHITECTURE.md)

---

## Discharge Summary Sections

The platform generates all 14 required clinical sections:

| Section | Safety Notes |
|---|---|
| Patient Demographics | Verified against admission note |
| Admission Date | Cross-referenced across documents |
| Discharge Date | Explicitly marked if not documented |
| **Principal Diagnosis** | CRITICAL — must have source evidence |
| Secondary Diagnoses | All diagnoses across all notes |
| Hospital Course | Synthesized from progress notes |
| Procedures | With dates and provider |
| Allergies | Cross-checked against medications |
| **Discharge Medications** | Fully reconciled across all docs |
| **Medication Changes** | NEW / CHANGED / DISCONTINUED flagged |
| Follow-Up Instructions | Pending referrals noted |
| **Pending Results** | Awaited results stay flagged |
| Discharge Condition | Stable / Improved / Unchanged etc. |
| Safety Flags Summary | All unresolved flags for clinician |

---

## Safety Severity Levels

| Level | Color | Meaning | Clinician Action |
|---|---|---|---|
| `CRITICAL` | 🔴 Red | Immediate patient safety risk (e.g., allergy-drug conflict) | **Must resolve before export** |
| `HIGH` | 🟠 Orange | Significant conflict or missing critical field | Must review before approval |
| `MEDIUM` | 🟡 Amber | Uncertain info, ambiguous statement | Flagged inline in summary |
| `INFO` | 🔵 Blue | Pending results, minor notes | Displayed in summary footer |

---

## Documentation

All 12 blueprint documents are in the `/docs` folder:

| # | Document | Description |
|---|---|---|
| 01 | [Product Vision](docs/01_PRODUCT_VISION.md) | Problem, users, workflow, user journey |
| 02 | [System Architecture](docs/02_SYSTEM_ARCHITECTURE.md) | Full architecture diagrams and component breakdown |
| 03 | [Folder Structure](docs/03_FOLDER_STRUCTURE.md) | Complete project structure with responsibility maps |
| 04 | [Agent Architecture](docs/04_AGENT_ARCHITECTURE.md) | Agent state machine, memory, tools, safety validator |
| 05 | [Database Design](docs/05_DATABASE_DESIGN.md) | SQLite schema, ERD, all table definitions |
| 06 | [API Design](docs/06_API_DESIGN.md) | All REST endpoints with request/response schemas |
| 07 | [Data Models](docs/07_DATA_MODELS.md) | All Pydantic models for every clinical entity |
| 08 | [UX Strategy](docs/08_UX_STRATEGY.md) | Healthcare UX philosophy and interaction model |
| 09 | [Design System](docs/09_DESIGN_SYSTEM.md) | Colors, typography, spacing, all component specs |
| 10 | [Pages Design](docs/10_PAGES_DESIGN.md) | Detailed design for all 7 application pages |
| 11 | [UI Mockups](docs/11_UI_MOCKUPS.md) | ASCII wireframes for every page |
| 12 | [Development Roadmap](docs/12_DEVELOPMENT_ROADMAP.md) | 10-phase implementation plan with acceptance criteria |

---

## Development Roadmap

| Phase | Focus | Duration |
|---|---|---|
| **Phase 1** | Architecture & Project Foundation | 3–4 days |
| **Phase 2** | PDF Processing Pipeline | 4–5 days |
| **Phase 3** | Clinical Knowledge Extraction (Tools) | 5–6 days |
| **Phase 4** | Agent Loop | 5–7 days |
| **Phase 5** | Reconciliation & Conflict Detection | 4–5 days |
| **Phase 6** | Safety Engine | 4–5 days |
| **Phase 7** | Summary Generation | 5–6 days |
| **Phase 8** | Observability & Analytics | 3–4 days |
| **Phase 9** | Frontend Polish & UX | 4–5 days |
| **Phase 10** | Learning System & Production Hardening | 3–4 days |

**Phases 1–7 constitute the MVP.** Full roadmap → [`docs/12_DEVELOPMENT_ROADMAP.md`](docs/12_DEVELOPMENT_ROADMAP.md)

---

## Key Design Decisions

**Why a custom agent loop instead of LangChain?**
Full control over the execution loop means full observability. Every tool call, input, output, and agent decision is logged to SQLite. Clinicians can see exactly what the agent did and why — essential for clinical trust and liability.

**Why evidence references on every statement?**
In clinical documentation, every statement must be verifiable. Evidence references are not a feature — they are the anti-hallucination mechanism. If a statement cannot be traced to a source document, it must not appear in the summary.

**Why a dedicated safety layer separate from the agent?**
Safety validation is not a prompt instruction that can be overridden. It is an independent subsystem that operates on structured data after all extraction is complete. It runs the same checks regardless of what the agent produced.

**Why always clinician-in-the-loop?**
Medical liability, regulatory compliance, and clinical ethics all require that a qualified clinician reviews and approves every discharge summary. The system's role is to make that review faster, more complete, and fully evidence-grounded.

---

## Author

**Harsh Raj**
- GitHub: [@harshraj677](https://github.com/harshraj677)
- Email: rajharsh7070@gmail.com

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">

Built with care for safer clinical transitions

</div>
