# DischargePilot AI — Complete System Architecture

---

## High-Level Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          DISCHARGEPILOT AI PLATFORM                          │
│                                                                              │
│  ┌─────────────────────┐         ┌──────────────────────────────────────┐   │
│  │    FRONTEND LAYER    │         │           BACKEND LAYER              │   │
│  │  Next.js 15 + TS    │◄───────►│        FastAPI (Python)              │   │
│  │  Tailwind + shadcn  │  REST   │        Port 8000                     │   │
│  │  Framer Motion      │  HTTP   │        Pydantic Validation           │   │
│  │  Port 3000          │         └──────────────┬───────────────────────┘   │
│  └─────────────────────┘                        │                           │
│                                                 │                           │
│         ┌───────────────────────────────────────┼──────────────────────┐   │
│         │                    CORE SERVICES       │                      │   │
│         │                                        ▼                     │   │
│         │   ┌──────────────────┐    ┌────────────────────────┐        │   │
│         │   │  PDF PROCESSING  │    │    AGENT ENGINE         │        │   │
│         │   │    ENGINE        │    │                         │        │   │
│         │   │  ─ PyMuPDF       │───►│  ─ Planner              │        │   │
│         │   │  ─ Text Extract  │    │  ─ Tool Selector        │        │   │
│         │   │  ─ Page Index    │    │  ─ Execution Loop       │        │   │
│         │   │  ─ Chunking      │    │  ─ Memory               │        │   │
│         │   └──────────────────┘    │  ─ Re-Planner           │        │   │
│         │                           └──────────┬─────────────┘        │   │
│         │                                      │                      │   │
│         │         ┌────────────────────────────┼──────────────────┐  │   │
│         │         │            TOOL LAYER       │                  │  │   │
│         │         │                             ▼                  │  │   │
│         │         │  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │  │   │
│         │         │  │ Extract  │  │  Recon   │  │  Validator  │  │  │   │
│         │         │  │  Tool    │  │  Tool    │  │  Tool       │  │  │   │
│         │         │  └──────────┘  └──────────┘  └─────────────┘  │  │   │
│         │         │  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │  │   │
│         │         │  │ Section  │  │ Conflict │  │  Evidence   │  │  │   │
│         │         │  │ Builder  │  │ Detector │  │  Linker     │  │  │   │
│         │         │  └──────────┘  └──────────┘  └─────────────┘  │  │   │
│         │         └─────────────────────────────────────────────┘  │   │
│         │                                                            │   │
│         │   ┌──────────────────────────────────────────────────┐   │   │
│         │   │                  SAFETY LAYER                     │   │   │
│         │   │  ─ Conflict Detector  ─ Medication Safety Check   │   │   │
│         │   │  ─ Completeness Check ─ Hallucination Guard        │   │   │
│         │   │  ─ Escalation Engine  ─ Fabrication Blocker        │   │   │
│         │   └──────────────────────────────────────────────────┘   │   │
│         │                                                            │   │
│         │   ┌──────────────┐    ┌───────────────────────────────┐  │   │
│         │   │  CLAUDE API  │    │       SQLITE DATABASE         │  │   │
│         │   │  (AI Layer)  │    │  Patients / Documents /       │  │   │
│         │   │              │    │  Agent Runs / Summaries /      │  │   │
│         │   │  Structured  │    │  Safety Flags / Traces /       │  │   │
│         │   │  Outputs     │    │  Learning Data                 │  │   │
│         │   └──────────────┘    └───────────────────────────────┘  │   │
│         └────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. Frontend Layer — Next.js 15

**Purpose:** Provide the clinical interface through which physicians interact with the system.

**Key Responsibilities:**
- Render all UI pages (Dashboard, Upload, Execution, Safety Review, Summary)
- Manage real-time agent execution state via polling or Server-Sent Events
- Display evidence-linked discharge summaries with inline editing
- Export approved summaries as formatted PDFs

**Technology choices:**
- **Next.js 15 App Router** — File-based routing, server components for data-heavy pages, client components for interactive sections
- **TypeScript** — Strict typing across all components and API contracts
- **Tailwind CSS** — Utility-first styling for fast, consistent design
- **shadcn/ui** — Accessible, composable component library built on Radix UI primitives
- **Framer Motion** — Clinical-appropriate subtle transitions (no heavy animations)

---

### 2. Backend Layer — FastAPI

**Purpose:** Serve as the application API server, orchestrate all backend services, manage the database, and coordinate agent execution.

**Key Responsibilities:**
- Receive file uploads and trigger PDF processing
- Expose CRUD endpoints for patients, documents, summaries, flags
- Initiate and manage agent runs (synchronous or async via background tasks)
- Provide real-time execution status via SSE or polling endpoints
- Enforce data validation via Pydantic models on all inputs and outputs

**Technology choices:**
- **FastAPI** — High-performance async Python web framework; automatic OpenAPI documentation
- **Pydantic v2** — Model validation, serialization, and schema generation
- **Uvicorn** — ASGI server for FastAPI
- **python-multipart** — File upload handling

---

### 3. PDF Processing Engine

**Purpose:** Extract structured, page-indexed text from clinical PDF documents.

**Pipeline:**
```
PDF File Upload
     │
     ▼
┌─────────────────────┐
│   File Validation   │  ── Check: valid PDF, size limit, page count
└─────────────────────┘
     │
     ▼
┌─────────────────────┐
│  PyMuPDF Extraction │  ── Extract raw text per page
└─────────────────────┘
     │
     ▼
┌─────────────────────┐
│   Text Cleaning     │  ── Normalize whitespace, remove artifacts
└─────────────────────┘
     │
     ▼
┌─────────────────────┐
│  Chunking Strategy  │  ── Split by page, section header, or token count
└─────────────────────┘
     │
     ▼
┌─────────────────────┐
│  Document Indexing  │  ── Store chunks with page refs in SQLite
└─────────────────────┘
     │
     ▼
Processed Document Record
(doc_id, patient_id, type, page_chunks[], status)
```

**Key Design Decisions:**
- Chunks retain their source page number — critical for evidence citation
- Document type is explicitly declared by the uploader (Admission Note, Progress Note, Lab Report, Medication Record) to guide agent extraction strategies
- Text cleaning preserves clinical abbreviations and numeric values

---

### 4. Agent Engine

**Purpose:** The core reasoning system. Orchestrates the full discharge summary generation pipeline through a structured agent loop.

**Architecture:** See `04_AGENT_ARCHITECTURE.md` for full design.

**Brief Summary:**
```
START
  │
  ▼
[Planner] — creates step plan from patient documents
  │
  ▼
[Tool Selector] — selects next tool to execute
  │
  ▼
[Tool Execution] — runs selected tool, stores result in Memory
  │
  ▼
[Re-Planner] — evaluates progress, identifies gaps, re-plans if needed
  │
  ▼
[Safety Validator] — runs safety checks before summary generation
  │
  ▼
[Summary Generator] — constructs structured discharge summary
  │
  ▼
[Termination Check] — all required sections complete? All conflicts surfaced?
  │
  ▼
END — Summary + Safety Flags returned
```

---

### 5. Tool Layer

Each tool is a discrete callable unit with a defined input schema, output schema, and behavior contract.

| Tool | Purpose | Input | Output |
|---|---|---|---|
| `extract_demographics` | Extract patient name, DOB, MRN, admission date | Document chunks | PatientDemographics |
| `extract_diagnoses` | Extract all diagnoses with ICD context | Document chunks | List[Diagnosis] |
| `extract_medications` | Extract medication records from source docs | Document chunks | List[Medication] |
| `extract_procedures` | Extract procedures performed | Document chunks | List[Procedure] |
| `extract_labs` | Extract lab results with dates | Document chunks | List[LabResult] |
| `reconcile_medications` | Cross-reference medications across all docs | List[Medication] | MedicationReconciliation |
| `detect_conflicts` | Find conflicting statements across documents | Extracted entities | List[Conflict] |
| `check_completeness` | Identify missing required discharge fields | Current state | List[MissingField] |
| `validate_safety` | Run safety checks on reconciled data | Current state | List[SafetyFlag] |
| `build_section` | Generate a specific summary section | Section type + evidence | SummarySection |
| `link_evidence` | Attach source citations to generated text | Text + source chunks | EvidenceLinkedText |
| `escalate` | Create high-severity safety flag | Conflict/issue | EscalationRecord |

---

### 6. Safety Layer

**Purpose:** A dedicated validation subsystem that runs independently of the agent loop to ensure all outputs meet clinical safety requirements before being presented to the clinician.

**Safety Checks:**

```
┌──────────────────────────────────────────────────────────────┐
│                    SAFETY VALIDATION PIPELINE                 │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ CHECK 1: Fabrication Blocker                             │ │
│  │ Every statement in the summary must trace to a source    │ │
│  │ chunk. Statements without evidence are blocked.          │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ CHECK 2: Conflict Surface                                │ │
│  │ Any detected conflict between source documents must be   │ │
│  │ surfaced as a safety flag — never silently resolved.     │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ CHECK 3: Medication Safety                               │ │
│  │ Known dangerous drug pairs, allergy conflicts, and       │ │
│  │ dose discrepancies are flagged for clinician review.     │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ CHECK 4: Completeness Validation                         │ │
│  │ All required discharge summary fields must be present    │ │
│  │ or explicitly marked as [NOT DOCUMENTED IN SOURCE].      │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ CHECK 5: Pending Results Guard                           │ │
│  │ Any lab or test marked as pending in source documents    │ │
│  │ must remain flagged as pending in the summary.           │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**Safety Severity Levels:**

| Level | Color | Meaning | Action Required |
|---|---|---|---|
| CRITICAL | Red | Immediate patient safety risk (e.g., allergy conflict with prescribed drug) | Agent escalates; clinician must resolve before export |
| HIGH | Orange | Significant conflict or missing critical field | Summary marked as incomplete; clinician must review |
| MEDIUM | Yellow | Uncertain information, ambiguous statement | Flagged inline for clinician attention |
| INFO | Blue | Pending results, minor notes | Displayed in summary footer |

---

### 7. Claude API Integration (AI Layer)

**Purpose:** Provide LLM reasoning capabilities to the agent, including entity extraction, section generation, and conflict analysis.

**Integration Pattern:**

The agent does not make raw open-ended LLM calls. All Claude API calls are:
- **Structured** — Using Claude's JSON mode and Pydantic output schemas
- **Bounded** — Each call has a specific task with constrained output format
- **Evidence-grounded** — Prompts include source text excerpts; model is explicitly instructed never to add information not present in the provided context
- **Audited** — Every API call is logged with input tokens, output tokens, model version, latency, and the raw response

**Prompt Design Principles:**
1. Role: "You are a clinical documentation assistant. You extract information from provided clinical text. You do not infer, fabricate, or add information not explicitly present."
2. Every prompt includes the exact source text chunk(s) being analyzed
3. Every prompt includes a structured output schema the model must conform to
4. Uncertainty fields are always present in output schemas (confidence, missing_info, caveats)

---

### 8. SQLite Database

**Purpose:** Persistent storage for all platform data including patients, documents, agent runs, traces, summaries, safety flags, and learning feedback.

**Schema:** See `05_DATABASE_DESIGN.md` for full schema.

---

## Data Flow Diagram — Full Request Cycle

```
USER ACTION: "Generate Discharge Summary for Patient #123"

  [Frontend]
      │  POST /api/agent/run  { patient_id: 123 }
      ▼
  [FastAPI Router]
      │  Validate request → create AgentRun record (status=PENDING)
      │  Launch background task
      ▼
  [Agent Engine — Background Task]
      │
      ├──[1] Load patient documents from SQLite
      │       SELECT * FROM documents WHERE patient_id = 123
      │
      ├──[2] Planner generates execution plan
      │       Claude API call: "Given these document types, create an extraction plan"
      │       Returns: ordered list of tool calls
      │
      ├──[3] Tool Selector executes plan step by step
      │       For each tool:
      │         ├── Call tool function with input
      │         ├── Store result in AgentMemory
      │         ├── Log AgentTrace record to SQLite
      │         └── Update AgentRun status
      │
      ├──[4] Re-Planner checks for gaps
      │       If missing fields detected → insert additional tool calls
      │       If conflicts detected → trigger conflict resolution tools
      │
      ├──[5] Safety Validator runs all checks
      │       Creates SafetyFlag records in SQLite
      │       CRITICAL flags → trigger escalation
      │
      ├──[6] Summary Generator builds sections
      │       For each required section:
      │         ├── Call build_section tool
      │         ├── Call link_evidence tool
      │         └── Store in SummarySection
      │
      └──[7] Finalize — create DischargeSummary record
              status = PENDING_REVIEW
              linked to: safety flags, evidence refs, agent run

  [AgentRun status updated to COMPLETED]

  [Frontend polling]
      │  GET /api/agent/run/{run_id}/status
      │  Returns: COMPLETED → redirect to Safety Review → Summary View
      ▼
  [Clinician Reviews → Approves → Export]
```
