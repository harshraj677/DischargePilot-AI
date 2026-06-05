# DischargePilot AI — Development Roadmap

---

## Overview

10 implementation phases. Each phase has clear deliverables, acceptance criteria, and explicit dependencies on prior phases. Phases 1–6 constitute the Minimum Viable Product (MVP). Phases 7–10 complete the full platform.

**Estimated Total Timeline:** 12–16 weeks for a single full-stack engineer

---

## Phase 1 — Architecture & Project Foundation
**Duration:** 3–4 days  
**Goal:** Establish the complete project skeleton with working infrastructure for both frontend and backend.

### Deliverables
- [ ] Monorepo setup with `frontend/` and `backend/` directories
- [ ] Backend: FastAPI app with health check endpoint, CORS configured, logging setup
- [ ] Backend: SQLite database with Alembic migrations; all tables created
- [ ] Backend: Pydantic models for all entities (from `07_DATA_MODELS.md`)
- [ ] Backend: Repository pattern scaffolded for all entities
- [ ] Frontend: Next.js 15 project initialized with TypeScript, Tailwind, shadcn/ui
- [ ] Frontend: Global layout shell (sidebar, topbar, content area)
- [ ] Frontend: Route structure matching all 7 pages
- [ ] Frontend: TypeScript type definitions mirroring all backend models
- [ ] Frontend: API client (`lib/api.ts`) with typed request/response methods
- [ ] `docker-compose.yml` running both services with hot reload
- [ ] `.env.example` with all required variables

### Acceptance Criteria
- Backend starts cleanly on `uvicorn app.main:app`
- All database tables created on startup
- Frontend starts cleanly on `npm run dev`
- All pages render without errors (empty state UI is fine)
- `GET /api/v1/health` returns `{ status: "ok" }`

---

## Phase 2 — PDF Processing Pipeline
**Duration:** 4–5 days  
**Goal:** Upload PDFs, extract text, and store processed content ready for agent consumption.

### Deliverables
- [ ] `POST /patients` — create patient record
- [ ] `GET /patients` — list patients with pagination
- [ ] `GET /patients/{id}` — patient detail with document list
- [ ] `POST /patients/{id}/documents` — upload PDF, trigger async processing
- [ ] `GET /documents/{id}` — document status polling
- [ ] `DELETE /documents/{id}` — remove document
- [ ] PDF extraction pipeline (`processing/pdf_extractor.py`)
  - [ ] PyMuPDF text extraction per page
  - [ ] Text cleaning and normalization
  - [ ] Chunking strategy (page-level chunks with character counts)
  - [ ] Page index construction for evidence citation
- [ ] Background task processing via FastAPI BackgroundTasks
- [ ] Document status updates (UPLOADED → PROCESSING → PROCESSED / FAILED)
- [ ] Frontend: Patient list page with real data
- [ ] Frontend: Patient upload center — drag-and-drop zone
- [ ] Frontend: Document cards with processing status (polling)
- [ ] Frontend: Upload progress indicators
- [ ] Error handling: invalid file type, file too large, extraction failure

### Acceptance Criteria
- Upload a real clinical PDF → status transitions to PROCESSED
- Page chunks stored with correct page numbers
- Extraction errors logged and surfaced in document status
- Frontend shows real-time processing status via polling

---

## Phase 3 — Clinical Knowledge Extraction (Tool Layer)
**Duration:** 5–6 days  
**Goal:** Build all extraction tools that form the foundation of the agent's clinical knowledge.

### Deliverables
- [ ] `base_tool.py` — abstract base class with: input schema, output schema, `run()`, `update_memory()`, `prepare_input()`
- [ ] `extract_demographics` tool — name, DOB, MRN, admission date, attending
- [ ] `extract_diagnoses` tool — principal + secondary diagnoses with ICD hints and evidence refs
- [ ] `extract_medications` tool — name, dose, route, frequency, prescribing source, evidence refs
- [ ] `extract_procedures` tool — procedures with dates and evidence refs
- [ ] `extract_labs` tool — test name, value, unit, reference range, status (pending/final), evidence refs
- [ ] All tools integrated with Claude API (`claude/client.py`)
- [ ] Prompt templates for each tool (`claude/prompts/`)
- [ ] Structured output schemas for each tool (`claude/schemas/`)
- [ ] Anti-hallucination instructions in every prompt
- [ ] Evidence reference generation (doc_id + page + excerpt) in every tool output
- [ ] Unit tests for each tool with sample clinical text fixtures

### Acceptance Criteria
- Each tool called with a sample clinical text chunk returns structured output conforming to its Pydantic schema
- Every extracted entity has at least one evidence reference
- Tool outputs contain `needs_review` and `confidence` fields
- Prompts explicitly block fabrication (verified by test cases with sparse input)
- All tools handle empty/insufficient input gracefully

---

## Phase 4 — Agent Loop
**Duration:** 5–7 days  
**Goal:** Build the full agent execution engine — the core of the platform.

### Deliverables
- [ ] `AgentMemory` dataclass — all state fields from `04_AGENT_ARCHITECTURE.md`
- [ ] `Planner` — generates initial execution plan via Claude API
- [ ] `ToolSelector` — picks next tool from plan respecting dependencies
- [ ] `Executor` — runs tool, updates memory, handles errors, writes trace
- [ ] `RePlanner` — detects gaps and inserts additional steps
- [ ] `Terminator` — evaluates completion conditions (SUCCESS, ESCALATED, MAX_ITERATIONS)
- [ ] `Tracer` — writes `AgentTrace` records to SQLite for every tool execution
- [ ] `AgentEngine.run()` — main execution loop tying all components together
- [ ] `POST /patients/{id}/agent/run` — triggers run as background task
- [ ] `GET /agent/runs/{id}` — returns current status + progress
- [ ] `GET /agent/runs/{id}/trace` — returns full execution trace
- [ ] Agent run lifecycle management: PENDING → PLANNING → EXECUTING → COMPLETED
- [ ] Iteration limit enforcement (default: 25 iterations max)
- [ ] Frontend: Agent Execution Center with timeline and live activity feed
- [ ] Frontend: Status polling (every 2 seconds during execution)
- [ ] Frontend: Completion redirect to Safety Review

### Acceptance Criteria
- End-to-end test: upload 4 clinical PDFs → trigger agent → run completes → summary created
- Trace viewer shows every tool execution with input/output
- Re-planning inserts new steps when missing fields are detected
- Max iterations enforced — does not run infinitely
- Agent status correctly reflects each state transition

---

## Phase 5 — Tool Layer: Reconciliation & Conflict Detection
**Duration:** 4–5 days  
**Goal:** Build the medication reconciliation and conflict detection tools — the most clinically critical tools.

### Deliverables
- [ ] `reconcile_medications` tool
  - [ ] Cross-references medications from all document sources
  - [ ] Identifies NEW, DOSE_CHANGED, DISCONTINUED, CONTINUED changes
  - [ ] Creates `MedicationChange` records
  - [ ] Creates `MedicationDiscrepancy` records for conflicts
- [ ] `detect_conflicts` tool
  - [ ] Compares diagnoses across documents
  - [ ] Compares medications across documents
  - [ ] Compares lab values across documents
  - [ ] Compares allergy lists against medication lists (CRITICAL conflict type)
  - [ ] Creates `Conflict` records with dual source evidence
- [ ] `check_completeness` tool
  - [ ] Verifies all 14 required summary sections have extractable data
  - [ ] Creates `MissingField` records for absent content
  - [ ] Returns severity (CRITICAL for principal diagnosis / medications, LOW for optional fields)
- [ ] `link_evidence` tool
  - [ ] Attaches source citations to generated text
  - [ ] Creates inline evidence reference chips
- [ ] `escalate` tool
  - [ ] Creates `EscalationRecord` for CRITICAL issues
  - [ ] Transitions agent state to ESCALATED
- [ ] Integration tests covering allergy-medication conflict scenario

### Acceptance Criteria
- Allergy-drug conflict detected and escalated to CRITICAL in test fixtures
- Medication dose discrepancy correctly creates HIGH conflict
- Missing principal diagnosis creates CRITICAL missing field flag
- Cross-document medication reconciliation handles same drug in multiple documents

---

## Phase 6 — Safety Engine
**Duration:** 4–5 days  
**Goal:** Build the complete safety validation subsystem — the clinical safety gatekeeper.

### Deliverables
- [ ] `FabricationGuard` — blocks statements without source evidence
- [ ] `ConflictChecker` — surfaces all detected conflicts as SafetyFlag records
- [ ] `MedicationSafetyChecker` — rule-based checks for known high-risk patterns
  - [ ] Allergy conflict with prescribed drug
  - [ ] Dose outside expected range
  - [ ] Duplicate medication entries
- [ ] `CompletenessChecker` — required field validation; marks missing as `[NOT DOCUMENTED IN SOURCE]`
- [ ] `PendingResultsGuard` — ensures pending labs remain flagged
- [ ] `SafetyValidator` orchestrator — runs all checks, creates `SafetyFlag` DB records
- [ ] Safety flags stored in SQLite with severity, category, description, evidence
- [ ] `GET /summaries/{id}/safety-flags` — returns flags grouped by severity
- [ ] `PATCH /safety-flags/{id}/resolve` — clinician resolution with note
- [ ] Frontend: Safety Review Center — all flags displayed by severity
- [ ] Frontend: Flag resolution workflow — required note, confirm button
- [ ] Frontend: "View Summary" gated behind CRITICAL flag resolution
- [ ] Frontend: Escalation banner on dashboard for critical flags

### Acceptance Criteria
- CRITICAL flag blocks summary approval in UI
- Fabrication guard test: if agent attempts to output ungrounded statement, it is blocked or flagged
- All 5 safety check types create appropriate DB records
- Clinician can resolve flags with notes, audit trail preserved

---

## Phase 7 — Summary Generation
**Duration:** 5–6 days  
**Goal:** Build the summary generation layer — all 14 discharge summary sections generated and assembled.

### Deliverables
- [ ] `build_section` tool — generates one section from memory + evidence
  - [ ] Patient Demographics section
  - [ ] Admission / Discharge Dates section
  - [ ] Principal Diagnosis section
  - [ ] Secondary Diagnoses section
  - [ ] Hospital Course section
  - [ ] Procedures section
  - [ ] Allergies section
  - [ ] Discharge Medications section
  - [ ] Medication Changes section
  - [ ] Follow-Up Instructions section
  - [ ] Pending Results section
  - [ ] Discharge Condition section
  - [ ] Safety Flags Summary section
- [ ] Per-section prompt templates with anti-hallucination instructions
- [ ] Missing field placeholder insertion: `[NOT DOCUMENTED IN SOURCE DOCUMENTS]`
- [ ] Uncertainty marker: `[NEEDS CLINICIAN REVIEW]`
- [ ] `DischargeSummary` record created in SQLite with all sections + evidence
- [ ] `GET /summaries/{id}` — full summary with evidence refs
- [ ] `PATCH /summaries/{id}/sections/{name}` — inline edit
- [ ] `POST /summaries/{id}/approve` — approval with CRITICAL flag check
- [ ] `GET /summaries/{id}/export?format=pdf` — formatted PDF export
- [ ] Frontend: Summary Viewer with section-by-section layout
- [ ] Frontend: Evidence reference chips with hover excerpt preview
- [ ] Frontend: Confidence indicators on each section
- [ ] Frontend: Inline edit mode for sections
- [ ] Frontend: Approval workflow with attestation modal
- [ ] Frontend: PDF export

### Acceptance Criteria
- All 14 sections present in output (with `[NOT DOCUMENTED]` for any missing)
- Every section has at least one evidence reference (or clearly marked as missing)
- Sections with `NEEDS_REVIEW` confidence are visually distinguished in the UI
- Approval blocked if any unresolved CRITICAL flags exist
- Exported PDF renders all sections cleanly

---

## Phase 8 — Observability & Admin
**Duration:** 3–4 days  
**Goal:** Build the full observability layer — trace viewer, analytics, and learning feedback.

### Deliverables
- [ ] Frontend: Trace Viewer — full audit log with expandable steps
- [ ] Frontend: Tool input/output formatted JSON viewer
- [ ] Frontend: Run statistics panel (tokens, latency, re-plans)
- [ ] `GET /analytics/overview` — platform metrics endpoint
- [ ] `GET /analytics/agent-performance` — per-tool metrics endpoint
- [ ] Frontend: Analytics Dashboard — metric cards + charts
- [ ] `POST /summaries/{id}/feedback` — learning feedback endpoint
- [ ] Frontend: Inline section feedback (thumbs up/down + issue type)
- [ ] Structured logging with request IDs across all API calls
- [ ] Agent token usage tracking and storage in `agent_runs` table

### Acceptance Criteria
- Trace viewer shows complete execution history for any run
- Analytics dashboard loads real data from the last 30 days
- Feedback submission creates `learning_feedback` record with section + rating
- All API requests include correlation ID in logs

---

## Phase 9 — Frontend Polish & UX Completion
**Duration:** 4–5 days  
**Goal:** Complete all frontend work to match the design system — transitions, empty states, error states, accessibility.

### Deliverables
- [ ] All page transitions (150ms fade-in via Framer Motion)
- [ ] Skeleton loaders for all data-loading states (no full-page spinners)
- [ ] Empty states for all list views (patients, documents, runs)
- [ ] Complete error boundary implementation
- [ ] Toast notifications for: agent completion, approval, resolution, errors
- [ ] All buttons have loading states (spinner while in-flight)
- [ ] Clinical text formatting (medication doses, lab values, dates)
- [ ] Print stylesheet for exported summaries
- [ ] Keyboard navigation for all interactive elements
- [ ] ARIA labels on all icon buttons
- [ ] Dashboard escalation banner real-time polling
- [ ] Page title updates for browser tab (e.g. "Safety Review — John Doe — DischargePilot AI")
- [ ] Responsive layout at `md` breakpoint (1024px)
- [ ] All shadcn/ui components customized to match design system tokens

### Acceptance Criteria
- No full-page spinners anywhere in the application
- All empty states have a meaningful message and CTA
- All error states have a specific message and recovery action
- Keyboard-only navigation works for primary workflows
- Print layout renders a clean single-column summary

---

## Phase 10 — Learning System & Production Hardening
**Duration:** 3–4 days  
**Goal:** Learning feedback loop, production configuration, security hardening.

### Deliverables
- [ ] Learning feedback storage and retrieval API complete
- [ ] Feedback analytics in analytics dashboard (section quality scores)
- [ ] Agent configuration tuning based on feedback data
- [ ] Rate limiting on API endpoints
- [ ] File upload security: MIME type validation, path traversal protection
- [ ] Input validation hardening on all endpoints
- [ ] Environment-based configuration (dev vs. prod settings)
- [ ] Database backup utility script
- [ ] Production `Dockerfile` for both services
- [ ] `docker-compose.prod.yml` configuration
- [ ] API documentation via FastAPI's auto-generated OpenAPI/Swagger UI
- [ ] README with setup instructions, environment variables, architecture overview

### Acceptance Criteria
- Feedback loop: submitted feedback appears in analytics dashboard
- Rate limiting tested: upload endpoint accepts max 10 files/minute
- Security: attempted path traversal in file upload is blocked
- Both services build and run cleanly via docker-compose
- OpenAPI docs accessible at `/docs`

---

## MVP Definition

**Phases 1–7 constitute the MVP.** A working MVP delivers:

1. Upload clinical PDFs for a patient
2. Run the agentic pipeline
3. Review safety flags before the summary
4. Review the generated discharge summary with evidence citations
5. Edit sections inline
6. Approve and export the summary

**Phases 8–10** add observability, polish, analytics, and production hardening.

---

## Technology Version Reference

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Backend runtime |
| FastAPI | 0.115+ | API framework |
| Pydantic | 2.x | Data validation |
| SQLAlchemy | 2.x | ORM |
| Alembic | 1.x | DB migrations |
| PyMuPDF (fitz) | 1.24+ | PDF extraction |
| anthropic (SDK) | 0.34+ | Claude API client |
| Node.js | 20+ | Frontend runtime |
| Next.js | 15.x | React framework |
| TypeScript | 5.x | Frontend types |
| Tailwind CSS | 3.x | Styling |
| shadcn/ui | Latest | Component library |
| Framer Motion | 11.x | Animations |
| Lucide React | Latest | Icons |
