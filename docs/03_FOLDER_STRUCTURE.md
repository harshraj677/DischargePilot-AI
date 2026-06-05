# DischargePilot AI — Production-Grade Folder Structure

---

## Overview

The project is organized as a monorepo with two top-level packages:
- `frontend/` — Next.js 15 TypeScript application
- `backend/` — Python FastAPI application

```
dischargepilot-ai/
├── frontend/                          # Next.js 15 TypeScript Application
├── backend/                           # Python FastAPI Application
├── docs/                              # Architecture & Design Documentation
├── scripts/                           # Dev, build, deployment scripts
├── .github/                           # CI/CD workflows
├── docker-compose.yml                 # Local development orchestration
├── .env.example                       # Environment variable template
└── README.md
```

---

## Backend Folder Structure

```
backend/
│
├── app/
│   │
│   ├── main.py                        # FastAPI app entrypoint, middleware, router registration
│   ├── config.py                      # Settings via pydantic-settings (env vars, Claude API key, DB path)
│   ├── dependencies.py                # FastAPI dependency injection (DB session, auth)
│   │
│   ├── api/                           # HTTP Layer — all API route handlers
│   │   ├── __init__.py
│   │   ├── router.py                  # Aggregates all sub-routers
│   │   ├── patients.py                # CRUD endpoints for patients
│   │   ├── documents.py               # File upload, list, delete endpoints
│   │   ├── agent.py                   # Run agent, get status, get trace endpoints
│   │   ├── summaries.py               # Get summary, update, approve, export endpoints
│   │   ├── safety.py                  # Get safety flags, resolve flag endpoints
│   │   └── analytics.py              # Platform metrics and stats endpoints
│   │
│   ├── models/                        # Pydantic Data Models (request/response schemas)
│   │   ├── __init__.py
│   │   ├── patient.py                 # Patient, PatientCreate, PatientResponse
│   │   ├── document.py                # Document, DocumentCreate, DocumentResponse
│   │   ├── diagnosis.py               # Diagnosis, DiagnosisList
│   │   ├── medication.py              # Medication, MedicationChange, ReconciliationResult
│   │   ├── procedure.py               # Procedure model
│   │   ├── lab_result.py              # LabResult, LabPanel
│   │   ├── conflict.py                # Conflict, ConflictSeverity
│   │   ├── safety_flag.py             # SafetyFlag, SafetySeverity, EscalationRecord
│   │   ├── summary.py                 # DischargeSummary, SummarySection, EvidenceRef
│   │   ├── agent.py                   # AgentRun, AgentState, AgentTrace, ToolCall
│   │   └── feedback.py                # LearningFeedback, SectionRating
│   │
│   ├── db/                            # Database Layer
│   │   ├── __init__.py
│   │   ├── database.py                # SQLite engine, session factory, Base declarative
│   │   ├── models.py                  # SQLAlchemy ORM table definitions
│   │   ├── migrations/                # Alembic migration scripts
│   │   │   ├── env.py
│   │   │   ├── script.py.mako
│   │   │   └── versions/
│   │   │       └── 0001_initial_schema.py
│   │   └── repositories/              # Data access layer — encapsulates all DB queries
│   │       ├── __init__.py
│   │       ├── patient_repo.py
│   │       ├── document_repo.py
│   │       ├── agent_repo.py
│   │       ├── summary_repo.py
│   │       └── safety_repo.py
│   │
│   ├── services/                      # Business Logic Layer
│   │   ├── __init__.py
│   │   ├── pdf_service.py             # PDF processing pipeline orchestration
│   │   ├── agent_service.py           # Agent run lifecycle management
│   │   ├── summary_service.py         # Summary assembly, approval, export
│   │   ├── safety_service.py          # Safety flag management and escalation
│   │   └── analytics_service.py       # Metrics aggregation
│   │
│   ├── agent/                         # Agent Engine — Core AI Reasoning System
│   │   ├── __init__.py
│   │   ├── engine.py                  # Main agent execution loop entry point
│   │   ├── planner.py                 # Initial plan generation via Claude API
│   │   ├── replanner.py               # Gap detection and plan revision logic
│   │   ├── tool_selector.py           # Selects next tool from plan
│   │   ├── executor.py                # Executes selected tool, handles errors
│   │   ├── memory.py                  # In-memory agent state during a run
│   │   ├── terminator.py              # Termination condition evaluation
│   │   ├── tracer.py                  # Writes agent trace records to DB
│   │   │
│   │   ├── tools/                     # Individual agent tools
│   │   │   ├── __init__.py
│   │   │   ├── base_tool.py           # Abstract base class for all tools
│   │   │   ├── extract_demographics.py
│   │   │   ├── extract_diagnoses.py
│   │   │   ├── extract_medications.py
│   │   │   ├── extract_procedures.py
│   │   │   ├── extract_labs.py
│   │   │   ├── reconcile_medications.py
│   │   │   ├── detect_conflicts.py
│   │   │   ├── check_completeness.py
│   │   │   ├── validate_safety.py
│   │   │   ├── build_section.py
│   │   │   ├── link_evidence.py
│   │   │   └── escalate.py
│   │   │
│   │   └── safety/                    # Safety Validation Subsystem
│   │       ├── __init__.py
│   │       ├── validator.py           # Orchestrates all safety checks
│   │       ├── fabrication_guard.py   # Blocks ungrounded statements
│   │       ├── conflict_checker.py    # Detects cross-document conflicts
│   │       ├── medication_safety.py   # Drug interaction and allergy checks
│   │       ├── completeness_checker.py # Required field validation
│   │       └── pending_results_guard.py # Ensures pending tests stay pending
│   │
│   ├── processing/                    # PDF & Document Processing
│   │   ├── __init__.py
│   │   ├── pdf_extractor.py           # PyMuPDF text extraction
│   │   ├── text_cleaner.py            # Clinical text normalization
│   │   ├── chunker.py                 # Text chunking strategies
│   │   ├── document_classifier.py     # Validates document type declarations
│   │   └── page_indexer.py            # Page-level index for evidence citations
│   │
│   ├── claude/                        # Claude API Client
│   │   ├── __init__.py
│   │   ├── client.py                  # Anthropic SDK wrapper, retry logic, logging
│   │   ├── prompts/                   # Prompt templates (one file per task type)
│   │   │   ├── extract_entities.py
│   │   │   ├── detect_conflicts.py
│   │   │   ├── generate_section.py
│   │   │   ├── reconcile_medications.py
│   │   │   └── validate_safety.py
│   │   └── schemas/                   # Structured output JSON schemas for Claude
│   │       ├── diagnosis_schema.py
│   │       ├── medication_schema.py
│   │       ├── conflict_schema.py
│   │       ├── section_schema.py
│   │       └── safety_schema.py
│   │
│   └── utils/                         # Shared Utilities
│       ├── __init__.py
│       ├── logging.py                 # Structured logging setup
│       ├── exceptions.py              # Custom exception classes
│       ├── file_utils.py              # File handling helpers
│       └── date_utils.py              # Clinical date parsing utilities
│
├── tests/                             # Test Suite
│   ├── conftest.py                    # Pytest fixtures, test DB setup
│   ├── test_api/
│   │   ├── test_patients.py
│   │   ├── test_documents.py
│   │   ├── test_agent.py
│   │   └── test_summaries.py
│   ├── test_agent/
│   │   ├── test_planner.py
│   │   ├── test_tools.py
│   │   └── test_safety.py
│   ├── test_processing/
│   │   └── test_pdf_extractor.py
│   └── fixtures/
│       └── sample_pdfs/               # Test PDF files for clinical document processing
│
├── alembic.ini                        # Alembic DB migration config
├── pyproject.toml                     # Python project config (deps, linting, testing)
├── requirements.txt                   # Production dependencies
├── requirements-dev.txt               # Development dependencies
└── Dockerfile                         # Backend container definition
```

### Backend Directory Responsibility Map

| Directory | Responsibility |
|---|---|
| `app/api/` | HTTP routing only. No business logic. Delegates to services. |
| `app/models/` | All Pydantic schemas for request validation and response serialization |
| `app/db/` | All database interaction — ORM models, migrations, repositories |
| `app/db/repositories/` | Single place for all SQL queries. Services never write raw SQL. |
| `app/services/` | Business logic orchestration. Calls repositories + agent/processing. |
| `app/agent/` | Full agent loop implementation — isolated from HTTP concerns |
| `app/agent/tools/` | Each tool is self-contained: input schema, logic, output schema |
| `app/agent/safety/` | Safety validation runs as an independent subsystem |
| `app/processing/` | PDF extraction pipeline — stateless functions |
| `app/claude/` | All Claude API interaction isolated here. Rest of app never calls Anthropic SDK directly. |
| `app/utils/` | Truly shared, side-effect-free utilities |

---

## Frontend Folder Structure

```
frontend/
│
├── src/
│   │
│   ├── app/                           # Next.js App Router — page definitions
│   │   ├── layout.tsx                 # Root layout: sidebar, nav, providers
│   │   ├── page.tsx                   # Redirect to /dashboard
│   │   ├── globals.css                # Tailwind base styles
│   │   │
│   │   ├── dashboard/
│   │   │   └── page.tsx               # Dashboard — patient queue, metrics
│   │   │
│   │   ├── patients/
│   │   │   ├── page.tsx               # Patient list
│   │   │   ├── [id]/
│   │   │   │   ├── page.tsx           # Patient detail view
│   │   │   │   └── upload/
│   │   │   │       └── page.tsx       # Document upload for specific patient
│   │   │
│   │   ├── agent/
│   │   │   ├── [runId]/
│   │   │   │   ├── page.tsx           # Agent Execution Center (live view)
│   │   │   │   └── trace/
│   │   │   │       └── page.tsx       # Trace Viewer (full audit log)
│   │   │
│   │   ├── safety/
│   │   │   └── [summaryId]/
│   │   │       └── page.tsx           # Safety Review Center
│   │   │
│   │   ├── summary/
│   │   │   └── [summaryId]/
│   │   │       └── page.tsx           # Summary Viewer + Review + Export
│   │   │
│   │   └── analytics/
│   │       └── page.tsx               # Analytics Dashboard
│   │
│   ├── components/                    # React Component Library
│   │   │
│   │   ├── ui/                        # Base shadcn/ui components (auto-generated)
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── input.tsx
│   │   │   ├── table.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── toast.tsx
│   │   │   └── tooltip.tsx
│   │   │
│   │   ├── layout/                    # Layout primitives
│   │   │   ├── Sidebar.tsx            # Navigation sidebar
│   │   │   ├── TopBar.tsx             # Page header bar
│   │   │   ├── PageHeader.tsx         # Page title + breadcrumb
│   │   │   └── ContentArea.tsx        # Main content wrapper
│   │   │
│   │   ├── patient/                   # Patient-specific components
│   │   │   ├── PatientCard.tsx        # Patient summary card
│   │   │   ├── PatientBadge.tsx       # Inline patient identifier
│   │   │   └── PatientTable.tsx       # Patient list table
│   │   │
│   │   ├── upload/                    # Document upload components
│   │   │   ├── DropZone.tsx           # Drag-and-drop file upload area
│   │   │   ├── DocumentTypeSelector.tsx # Dropdown to declare document type
│   │   │   ├── DocumentCard.tsx       # Individual uploaded document card
│   │   │   └── UploadProgress.tsx     # Upload and processing progress bar
│   │   │
│   │   ├── agent/                     # Agent execution components
│   │   │   ├── ExecutionTimeline.tsx  # Step-by-step execution progress
│   │   │   ├── AgentStateIndicator.tsx # Current agent state badge
│   │   │   ├── ToolCallCard.tsx       # Individual tool call display
│   │   │   ├── PlanViewer.tsx         # Agent's execution plan
│   │   │   └── LiveActivityFeed.tsx   # Scrolling real-time tool activity
│   │   │
│   │   ├── trace/                     # Trace viewer components
│   │   │   ├── TraceTimeline.tsx      # Full execution history
│   │   │   ├── TraceStep.tsx          # Individual trace step
│   │   │   ├── ToolInputOutput.tsx    # Tool call input/output viewer
│   │   │   └── ReasoningBlock.tsx     # Agent reasoning display
│   │   │
│   │   ├── safety/                    # Safety review components
│   │   │   ├── SafetyFlagCard.tsx     # Individual safety flag display
│   │   │   ├── ConflictDisplay.tsx    # Conflict with source references
│   │   │   ├── MissingFieldAlert.tsx  # Missing required field indicator
│   │   │   ├── MedicationConflict.tsx # Medication safety issue display
│   │   │   └── EscalationBanner.tsx   # Critical escalation alert banner
│   │   │
│   │   ├── summary/                   # Summary viewer components
│   │   │   ├── SummarySection.tsx     # Individual section (title + content + evidence)
│   │   │   ├── EvidenceRef.tsx        # Inline evidence citation chip
│   │   │   ├── SectionEditor.tsx      # Inline edit mode for a section
│   │   │   ├── ConfidenceIndicator.tsx # High/Medium/NeedsReview badge
│   │   │   └── ExportPanel.tsx        # Export actions (PDF, copy, EHR push)
│   │   │
│   │   ├── analytics/                 # Analytics components
│   │   │   ├── MetricCard.tsx         # Single metric display card
│   │   │   ├── AgentPerformanceChart.tsx
│   │   │   ├── SafetyTrendChart.tsx
│   │   │   └── ProcessingStatsTable.tsx
│   │   │
│   │   └── common/                    # Shared cross-domain components
│   │       ├── StatusBadge.tsx        # Generic status badge
│   │       ├── SeverityIndicator.tsx  # Color-coded severity levels
│   │       ├── EmptyState.tsx         # Empty state with CTA
│   │       ├── LoadingSpinner.tsx     # Clinical-styled loading indicator
│   │       ├── ErrorBoundary.tsx      # Error fallback UI
│   │       └── ConfirmDialog.tsx      # Approval confirmation modal
│   │
│   ├── hooks/                         # Custom React Hooks
│   │   ├── usePatients.ts             # Patient data fetching + mutations
│   │   ├── useDocuments.ts            # Document upload and management
│   │   ├── useAgentRun.ts             # Agent run lifecycle + polling
│   │   ├── useSummary.ts              # Summary data + edit operations
│   │   ├── useSafetyFlags.ts          # Safety flag data
│   │   └── useAnalytics.ts            # Analytics data fetching
│   │
│   ├── lib/                           # Shared Libraries & Utilities
│   │   ├── api.ts                     # Axios/fetch client — all API calls defined here
│   │   ├── utils.ts                   # shadcn/ui cn() utility + misc helpers
│   │   ├── constants.ts               # App-wide constants (API base URL, status enums)
│   │   ├── types.ts                   # TypeScript interfaces mirroring backend models
│   │   └── formatters.ts              # Date, medication, lab value formatters
│   │
│   └── styles/
│       └── globals.css                # Tailwind directives + CSS custom properties
│
├── public/
│   ├── logo.svg                       # DischargePilot AI logo
│   └── favicon.ico
│
├── tailwind.config.ts                 # Tailwind configuration + design tokens
├── tsconfig.json                      # TypeScript configuration
├── next.config.ts                     # Next.js configuration
├── components.json                    # shadcn/ui component registry config
├── package.json
└── Dockerfile                         # Frontend container definition
```

### Frontend Directory Responsibility Map

| Directory | Responsibility |
|---|---|
| `src/app/` | Page definitions and routing only. Minimal logic — delegates to components and hooks. |
| `src/components/ui/` | Raw shadcn/ui primitives. Never modified directly — extend by wrapping. |
| `src/components/[domain]/` | Domain-specific composite components built from ui primitives. |
| `src/components/common/` | Cross-domain shared components. No domain-specific logic. |
| `src/hooks/` | All data fetching and state management. Pages import hooks, not raw API calls. |
| `src/lib/api.ts` | Single source of truth for all backend API calls. Never call fetch/axios from components directly. |
| `src/lib/types.ts` | TypeScript types that mirror the backend Pydantic models. Keep in sync. |

---

## Documentation Folder

```
docs/
├── 01_PRODUCT_VISION.md
├── 02_SYSTEM_ARCHITECTURE.md
├── 03_FOLDER_STRUCTURE.md             ← this file
├── 04_AGENT_ARCHITECTURE.md
├── 05_DATABASE_DESIGN.md
├── 06_API_DESIGN.md
├── 07_DATA_MODELS.md
├── 08_UX_STRATEGY.md
├── 09_DESIGN_SYSTEM.md
├── 10_PAGES_DESIGN.md
├── 11_UI_MOCKUPS.md
└── 12_DEVELOPMENT_ROADMAP.md
```
