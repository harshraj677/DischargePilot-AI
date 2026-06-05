# DischargePilot AI — Database Design

---

## Overview

The database is SQLite for Phase 1. The schema is designed to be migration-compatible with PostgreSQL for production scaling. All tables use UUID primary keys, include `created_at`/`updated_at` timestamps, and use soft deletes (`deleted_at`) for audit compliance.

---

## Entity Relationship Diagram

```
┌──────────────┐         ┌──────────────────┐       ┌──────────────────┐
│   patients   │────────►│    documents     │       │   agent_runs     │
│              │  1:N    │                  │       │                  │
│ id (PK)      │         │ id (PK)          │       │ id (PK)          │
│ mrn          │         │ patient_id (FK)  │       │ patient_id (FK)  │
│ first_name   │         │ document_type    │       │ status           │
│ last_name    │         │ file_name        │       │ plan_json        │
│ date_of_birth│         │ file_path        │       │ config_json      │
│ gender       │         │ page_count       │       │ started_at       │
│ mrn          │         │ status           │       │ completed_at     │
│ admission_dt │         │ extracted_text   │       │ error_message    │
│ discharge_dt │         │ page_chunks_json │       │ iteration_count  │
│ attending_md │         │ created_at       │       │ total_tokens     │
│ ward         │         └──────────────────┘       │ created_at       │
│ created_at   │                  │                  └──────────────────┘
└──────────────┘                  │                           │
       │                          │                           │ 1:N
       │                          │              ┌────────────▼─────────┐
       │ 1:N                      │              │    agent_traces      │
       │                          │              │                      │
       ▼                          │              │ id (PK)              │
┌──────────────────────┐          │              │ run_id (FK)          │
│  discharge_summaries │◄─────────┘              │ step_id              │
│                      │  N:1                    │ tool_name            │
│ id (PK)              │                         │ input_json           │
│ patient_id (FK)      │                         │ output_json          │
│ agent_run_id (FK)    │◄──────── agent_runs     │ success              │
│ status               │                         │ latency_ms           │
│ sections_json        │                         │ error_message        │
│ reviewed_by          │                         │ timestamp            │
│ reviewed_at          │                         └──────────────────────┘
│ approved_at          │
│ export_count         │         ┌──────────────────────────────┐
│ created_at           │────────►│       safety_flags           │
└──────────────────────┘  1:N    │                              │
                                 │ id (PK)                      │
                                 │ summary_id (FK)              │
                                 │ run_id (FK)                  │
                                 │ severity                     │
                                 │ category                     │
                                 │ description                  │
                                 │ source_doc_ids_json          │
                                 │ conflicting_text_json        │
                                 │ resolved                     │
                                 │ resolved_by                  │
                                 │ resolution_note              │
                                 │ resolved_at                  │
                                 │ created_at                   │
                                 └──────────────────────────────┘

┌──────────────────────┐
│   learning_feedback  │
│                      │
│ id (PK)              │
│ summary_id (FK)      │
│ section_name         │
│ rating               │
│ issue_type           │
│ comment              │
│ submitted_by         │
│ created_at           │
└──────────────────────┘
```

---

## Table Definitions

### `patients`

Stores core patient identity and encounter information.

```sql
CREATE TABLE patients (
    id              TEXT PRIMARY KEY,           -- UUID
    mrn             TEXT NOT NULL UNIQUE,        -- Medical Record Number
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    date_of_birth   TEXT NOT NULL,               -- ISO 8601 date
    gender          TEXT,                        -- M / F / Other / Unknown
    admission_date  TEXT,                        -- ISO 8601 datetime
    discharge_date  TEXT,                        -- ISO 8601 datetime (nullable until discharge)
    attending_md    TEXT,                        -- Attending physician name
    ward            TEXT,                        -- Hospital ward / unit
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at      TEXT                         -- Soft delete
);

CREATE INDEX idx_patients_mrn ON patients(mrn);
CREATE INDEX idx_patients_created ON patients(created_at);
```

---

### `documents`

Stores uploaded clinical source documents and their extracted text.

```sql
CREATE TABLE documents (
    id              TEXT PRIMARY KEY,            -- UUID
    patient_id      TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    document_type   TEXT NOT NULL,               -- ENUM: admission_note | progress_note | lab_report | medication_record
    file_name       TEXT NOT NULL,               -- Original filename
    file_path       TEXT NOT NULL,               -- Storage path
    file_size_bytes INTEGER,
    page_count      INTEGER,
    status          TEXT NOT NULL DEFAULT 'UPLOADED',  -- UPLOADED | PROCESSING | PROCESSED | FAILED
    extracted_text  TEXT,                        -- Full extracted plain text
    page_chunks     TEXT,                        -- JSON: [{page: 1, text: "..."}, ...]
    processing_error TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_documents_patient ON documents(patient_id);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_documents_status ON documents(status);
```

---

### `agent_runs`

Tracks each execution of the agent for a patient encounter.

```sql
CREATE TABLE agent_runs (
    id              TEXT PRIMARY KEY,            -- UUID
    patient_id      TEXT NOT NULL REFERENCES patients(id),
    status          TEXT NOT NULL DEFAULT 'PENDING',
                    -- PENDING | PLANNING | EXECUTING | RE_PLANNING | VALIDATING
                    -- | GENERATING | COMPLETED | ESCALATED | FAILED | INCOMPLETE
    plan            TEXT,                        -- JSON: execution plan steps
    config          TEXT,                        -- JSON: agent configuration at runtime
    memory_snapshot TEXT,                        -- JSON: final memory state at completion
    started_at      TEXT,
    completed_at    TEXT,
    error_message   TEXT,
    iteration_count INTEGER DEFAULT 0,
    total_tokens_in  INTEGER DEFAULT 0,
    total_tokens_out INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_agent_runs_patient ON agent_runs(patient_id);
CREATE INDEX idx_agent_runs_status ON agent_runs(status);
CREATE INDEX idx_agent_runs_created ON agent_runs(created_at);
```

---

### `agent_traces`

Complete audit log of every tool execution within an agent run. This is the source of truth for the Trace Viewer.

```sql
CREATE TABLE agent_traces (
    id              TEXT PRIMARY KEY,            -- UUID
    run_id          TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    step_id         TEXT NOT NULL,               -- From ToolCallSpec.step_id
    step_number     INTEGER NOT NULL,            -- Execution order
    tool_name       TEXT NOT NULL,
    tool_input      TEXT,                        -- JSON: tool input (redacted if PHI)
    tool_output     TEXT,                        -- JSON: tool result summary
    success         INTEGER NOT NULL DEFAULT 1,  -- 0 = failure
    latency_ms      REAL,
    error_message   TEXT,
    claude_tokens_in  INTEGER,                   -- Tokens if this step called Claude API
    claude_tokens_out INTEGER,
    reasoning       TEXT,                        -- Agent's reasoning for this step
    timestamp       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_traces_run ON agent_traces(run_id);
CREATE INDEX idx_traces_tool ON agent_traces(tool_name);
CREATE INDEX idx_traces_timestamp ON agent_traces(timestamp);
```

---

### `discharge_summaries`

Stores the generated discharge summary with all sections, evidence, and review metadata.

```sql
CREATE TABLE discharge_summaries (
    id              TEXT PRIMARY KEY,            -- UUID
    patient_id      TEXT NOT NULL REFERENCES patients(id),
    agent_run_id    TEXT NOT NULL REFERENCES agent_runs(id),
    status          TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
                    -- PENDING_REVIEW | IN_REVIEW | APPROVED | ESCALATED | INCOMPLETE
    sections        TEXT NOT NULL,               -- JSON: all summary sections with evidence
    safety_summary  TEXT,                        -- JSON: summary of safety issues found
    conflicts_found INTEGER DEFAULT 0,
    missing_fields  INTEGER DEFAULT 0,
    medications_reconciled INTEGER DEFAULT 0,
    reviewed_by     TEXT,                        -- Clinician identifier
    review_started_at TEXT,
    reviewed_at     TEXT,
    approved_by     TEXT,
    approved_at     TEXT,
    export_count    INTEGER DEFAULT 0,
    last_exported_at TEXT,
    version         INTEGER NOT NULL DEFAULT 1,  -- Increments on clinician edits
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_summaries_patient ON discharge_summaries(patient_id);
CREATE INDEX idx_summaries_status ON discharge_summaries(status);
CREATE INDEX idx_summaries_created ON discharge_summaries(created_at);
```

The `sections` column stores a JSON structure like:
```json
{
  "patient_demographics": {
    "content": "John Doe, 54M, MRN: 12345...",
    "confidence": "HIGH",
    "needs_review": false,
    "evidence_refs": [
      {"doc_id": "uuid", "page": 1, "excerpt": "Patient: John Doe..."}
    ]
  },
  "principal_diagnosis": {
    "content": "Type 2 Diabetes Mellitus with HbA1c 9.2%",
    "confidence": "HIGH",
    "needs_review": false,
    "evidence_refs": [...]
  }
}
```

---

### `safety_flags`

Individual safety issues identified during agent execution.

```sql
CREATE TABLE safety_flags (
    id              TEXT PRIMARY KEY,            -- UUID
    summary_id      TEXT REFERENCES discharge_summaries(id),
    run_id          TEXT NOT NULL REFERENCES agent_runs(id),
    severity        TEXT NOT NULL,               -- CRITICAL | HIGH | MEDIUM | INFO
    category        TEXT NOT NULL,
                    -- MEDICATION_CONFLICT | ALLERGY_CONFLICT | DIAGNOSIS_CONFLICT
                    -- | MISSING_FIELD | PENDING_RESULT | DOSE_DISCREPANCY
                    -- | POLYPHARMACY | UNVERIFIED_STATEMENT
    title           TEXT NOT NULL,               -- Short description for UI display
    description     TEXT NOT NULL,               -- Full explanation
    source_doc_ids  TEXT,                        -- JSON: list of involved document IDs
    conflicting_text TEXT,                       -- JSON: the conflicting text snippets
    recommendation  TEXT,                        -- What clinician should do
    resolved        INTEGER NOT NULL DEFAULT 0,
    resolved_by     TEXT,
    resolution_note TEXT,
    resolved_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_flags_summary ON safety_flags(summary_id);
CREATE INDEX idx_flags_severity ON safety_flags(severity);
CREATE INDEX idx_flags_resolved ON safety_flags(resolved);
CREATE INDEX idx_flags_category ON safety_flags(category);
```

---

### `learning_feedback`

Captures clinician feedback on generated content for future quality improvement.

```sql
CREATE TABLE learning_feedback (
    id              TEXT PRIMARY KEY,            -- UUID
    summary_id      TEXT NOT NULL REFERENCES discharge_summaries(id),
    section_name    TEXT NOT NULL,               -- Which section the feedback is about
    rating          INTEGER,                     -- 1–5 stars
    issue_type      TEXT,
                    -- INCORRECT | INCOMPLETE | HALLUCINATED | POOR_LANGUAGE
                    -- | MISSING_INFO | GOOD
    comment         TEXT,
    original_content TEXT,                       -- What was generated
    corrected_content TEXT,                      -- What clinician changed it to (if edited)
    submitted_by    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_feedback_summary ON learning_feedback(summary_id);
CREATE INDEX idx_feedback_section ON learning_feedback(section_name);
CREATE INDEX idx_feedback_issue ON learning_feedback(issue_type);
CREATE INDEX idx_feedback_created ON learning_feedback(created_at);
```

---

## Database Relationships Summary

| Relationship | Type | Description |
|---|---|---|
| `patients` → `documents` | 1:N | One patient has many uploaded documents |
| `patients` → `agent_runs` | 1:N | One patient can have multiple agent runs over time |
| `patients` → `discharge_summaries` | 1:N | One patient can have multiple summaries (e.g., readmission) |
| `agent_runs` → `agent_traces` | 1:N | One run has many trace steps |
| `agent_runs` → `discharge_summaries` | 1:1 | One run produces one summary |
| `discharge_summaries` → `safety_flags` | 1:N | One summary has many safety flags |
| `discharge_summaries` → `learning_feedback` | 1:N | One summary can receive many feedback items |

---

## Migration Strategy

```python
# alembic/versions/0001_initial_schema.py
# Creates all tables in the correct order respecting foreign key dependencies:
# 1. patients
# 2. documents
# 3. agent_runs
# 4. agent_traces
# 5. discharge_summaries
# 6. safety_flags
# 7. learning_feedback
```

SQLite foreign key enforcement must be enabled per connection:
```python
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```
