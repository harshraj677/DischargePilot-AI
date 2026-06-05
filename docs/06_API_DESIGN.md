# DischargePilot AI — API Design

---

## Base URL

```
Development:  http://localhost:8000/api/v1
Production:   https://api.dischargepilot.health/v1
```

## Conventions

- All request/response bodies: `application/json`
- File uploads: `multipart/form-data`
- Datetime format: ISO 8601 (`2025-06-05T14:30:00Z`)
- IDs: UUID v4 strings
- Pagination: `page` (1-based) + `page_size` (default 20, max 100) query params
- Error format: `{ "error": "...", "detail": "...", "code": "..." }`
- HTTP status codes follow REST conventions

---

## 1. Patient Endpoints

### `POST /patients`
Create a new patient record.

**Request:**
```json
{
  "mrn": "MRN-2025-00123",
  "first_name": "John",
  "last_name": "Doe",
  "date_of_birth": "1971-03-15",
  "gender": "M",
  "admission_date": "2025-05-28T08:00:00Z",
  "attending_md": "Dr. Sarah Chen",
  "ward": "Internal Medicine - Ward 3B"
}
```

**Response `201 Created`:**
```json
{
  "id": "a1b2c3d4-...",
  "mrn": "MRN-2025-00123",
  "first_name": "John",
  "last_name": "Doe",
  "date_of_birth": "1971-03-15",
  "gender": "M",
  "admission_date": "2025-05-28T08:00:00Z",
  "discharge_date": null,
  "attending_md": "Dr. Sarah Chen",
  "ward": "Internal Medicine - Ward 3B",
  "document_count": 0,
  "summary_status": null,
  "created_at": "2025-06-05T10:00:00Z"
}
```

---

### `GET /patients`
List all patients with pagination.

**Query Params:** `page`, `page_size`, `search` (searches MRN, name), `ward`, `summary_status`

**Response `200 OK`:**
```json
{
  "items": [ { ...patient objects... } ],
  "total": 48,
  "page": 1,
  "page_size": 20,
  "has_more": true
}
```

---

### `GET /patients/{patient_id}`
Get a single patient with document summary and latest summary status.

**Response `200 OK`:**
```json
{
  "id": "a1b2c3d4-...",
  "mrn": "MRN-2025-00123",
  "first_name": "John",
  "last_name": "Doe",
  "date_of_birth": "1971-03-15",
  "gender": "M",
  "admission_date": "2025-05-28T08:00:00Z",
  "discharge_date": null,
  "attending_md": "Dr. Sarah Chen",
  "ward": "Internal Medicine - Ward 3B",
  "documents": [
    {
      "id": "doc-uuid",
      "document_type": "admission_note",
      "file_name": "admission_note_john_doe.pdf",
      "status": "PROCESSED",
      "page_count": 12,
      "created_at": "2025-06-05T09:30:00Z"
    }
  ],
  "latest_summary": {
    "id": "summary-uuid",
    "status": "PENDING_REVIEW",
    "created_at": "2025-06-05T10:15:00Z"
  },
  "created_at": "2025-06-05T09:00:00Z"
}
```

---

### `PATCH /patients/{patient_id}`
Update patient record (e.g., add discharge date).

**Request:**
```json
{
  "discharge_date": "2025-06-05T14:00:00Z"
}
```

**Response `200 OK`:** Updated patient object.

---

## 2. Document Endpoints

### `POST /patients/{patient_id}/documents`
Upload one or more clinical source PDFs. Triggers async PDF processing.

**Request:** `multipart/form-data`
```
file:           [binary PDF file]
document_type:  admission_note | progress_note | lab_report | medication_record
```

**Response `202 Accepted`:**
```json
{
  "id": "doc-uuid",
  "patient_id": "patient-uuid",
  "document_type": "admission_note",
  "file_name": "admission_note.pdf",
  "file_size_bytes": 245760,
  "status": "PROCESSING",
  "page_count": null,
  "created_at": "2025-06-05T10:00:00Z"
}
```

---

### `GET /patients/{patient_id}/documents`
List all documents for a patient.

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "doc-uuid",
      "document_type": "admission_note",
      "file_name": "admission_note.pdf",
      "file_size_bytes": 245760,
      "page_count": 12,
      "status": "PROCESSED",
      "created_at": "2025-06-05T09:30:00Z"
    }
  ],
  "total": 4
}
```

---

### `GET /documents/{document_id}`
Get a single document including processing status.

**Response `200 OK`:**
```json
{
  "id": "doc-uuid",
  "patient_id": "patient-uuid",
  "document_type": "admission_note",
  "file_name": "admission_note.pdf",
  "status": "PROCESSED",
  "page_count": 12,
  "processing_error": null,
  "created_at": "2025-06-05T09:30:00Z"
}
```

---

### `DELETE /documents/{document_id}`
Remove a document before agent run is triggered.

**Response `204 No Content`**

---

## 3. Agent Endpoints

### `POST /patients/{patient_id}/agent/run`
Trigger agent run for a patient. All uploaded documents must be in PROCESSED status.

**Request:**
```json
{
  "config": {
    "max_iterations": 25,
    "enable_safety_layer": true
  }
}
```

**Response `202 Accepted`:**
```json
{
  "run_id": "run-uuid",
  "patient_id": "patient-uuid",
  "status": "PENDING",
  "created_at": "2025-06-05T10:05:00Z"
}
```

**Error `400 Bad Request`** — if documents not yet processed:
```json
{
  "error": "Documents not ready",
  "detail": "2 documents are still processing. Wait for all documents to reach PROCESSED status.",
  "code": "DOCUMENTS_NOT_READY"
}
```

---

### `GET /agent/runs/{run_id}`
Get current status and progress of an agent run. Used for polling from the frontend.

**Response `200 OK`:**
```json
{
  "run_id": "run-uuid",
  "patient_id": "patient-uuid",
  "status": "EXECUTING",
  "current_step": {
    "step_number": 6,
    "tool_name": "reconcile_medications",
    "started_at": "2025-06-05T10:05:45Z"
  },
  "progress": {
    "steps_completed": 5,
    "steps_total": 14,
    "percent": 36
  },
  "iteration_count": 6,
  "started_at": "2025-06-05T10:05:00Z",
  "completed_at": null,
  "summary_id": null,
  "error_message": null
}
```

When completed:
```json
{
  "run_id": "run-uuid",
  "status": "COMPLETED",
  "progress": { "steps_completed": 14, "steps_total": 14, "percent": 100 },
  "summary_id": "summary-uuid",
  "completed_at": "2025-06-05T10:06:48Z",
  "total_tokens_in": 24300,
  "total_tokens_out": 8900
}
```

---

### `GET /agent/runs/{run_id}/trace`
Get the full execution trace for an agent run.

**Response `200 OK`:**
```json
{
  "run_id": "run-uuid",
  "patient_id": "patient-uuid",
  "status": "COMPLETED",
  "plan": [
    { "step_id": "s1", "tool_name": "extract_demographics", "priority": 1 }
  ],
  "trace": [
    {
      "id": "trace-uuid",
      "step_number": 1,
      "step_id": "s1",
      "tool_name": "extract_demographics",
      "tool_input": { "doc_ids": ["doc-uuid"], "fields": ["name", "dob", "mrn"] },
      "tool_output": {
        "success": true,
        "extracted": { "first_name": "John", "last_name": "Doe", "dob": "1971-03-15" },
        "evidence_refs": [{ "doc_id": "doc-uuid", "page": 1, "excerpt": "Patient: John Doe..." }]
      },
      "success": true,
      "latency_ms": 1240,
      "reasoning": "Demographics extracted from admission note header",
      "timestamp": "2025-06-05T10:05:05Z"
    }
  ]
}
```

---

### `GET /agent/runs`
List all agent runs with filters.

**Query Params:** `patient_id`, `status`, `page`, `page_size`

---

## 4. Summary Endpoints

### `GET /summaries/{summary_id}`
Get the full generated discharge summary with all sections and evidence.

**Response `200 OK`:**
```json
{
  "id": "summary-uuid",
  "patient_id": "patient-uuid",
  "agent_run_id": "run-uuid",
  "status": "PENDING_REVIEW",
  "version": 1,
  "sections": {
    "patient_demographics": {
      "content": "John Doe, 54-year-old male, MRN: MRN-2025-00123. Admitted 2025-05-28. Attending: Dr. Sarah Chen.",
      "confidence": "HIGH",
      "needs_review": false,
      "evidence_refs": [
        {
          "doc_id": "doc-uuid",
          "document_type": "admission_note",
          "page": 1,
          "excerpt": "Patient: John Doe, DOB: 1971-03-15..."
        }
      ]
    },
    "principal_diagnosis": {
      "content": "Type 2 Diabetes Mellitus, uncontrolled (HbA1c 9.2%, 2025-05-29)",
      "confidence": "HIGH",
      "needs_review": false,
      "evidence_refs": [...]
    },
    "discharge_medications": {
      "content": "[NEEDS CLINICIAN REVIEW] Metformin 1000mg PO BID...",
      "confidence": "MEDIUM",
      "needs_review": true,
      "evidence_refs": [...]
    }
  },
  "conflicts_found": 2,
  "missing_fields": 1,
  "medications_reconciled": 8,
  "reviewed_by": null,
  "approved_at": null,
  "created_at": "2025-06-05T10:07:00Z"
}
```

---

### `PATCH /summaries/{summary_id}/sections/{section_name}`
Update a specific section (clinician inline edit).

**Request:**
```json
{
  "content": "Metformin 1000mg PO BID, Lisinopril 10mg PO daily (NEW)",
  "edit_note": "Corrected metformin dose; confirmed lisinopril is new prescription"
}
```

**Response `200 OK`:** Updated section object. Summary version incremented.

---

### `POST /summaries/{summary_id}/approve`
Approve the discharge summary for finalization.

**Request:**
```json
{
  "approved_by": "dr.chen@hospital.org",
  "attestation": "I have reviewed this discharge summary and confirm its accuracy."
}
```

**Response `200 OK`:**
```json
{
  "id": "summary-uuid",
  "status": "APPROVED",
  "approved_by": "dr.chen@hospital.org",
  "approved_at": "2025-06-05T11:30:00Z"
}
```

---

### `GET /summaries/{summary_id}/export`
Export summary as formatted PDF or plain text.

**Query Params:** `format=pdf|text`

**Response `200 OK`:**
- `format=pdf` → `application/pdf` binary
- `format=text` → `application/json` with formatted text string

---

## 5. Safety Flag Endpoints

### `GET /summaries/{summary_id}/safety-flags`
Get all safety flags for a summary.

**Query Params:** `severity`, `resolved`, `category`

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "flag-uuid",
      "severity": "CRITICAL",
      "category": "ALLERGY_CONFLICT",
      "title": "Prescribed medication conflicts with documented allergy",
      "description": "Admission note documents penicillin allergy. Day 3 progress note contains a prescription for amoxicillin (a penicillin-class antibiotic). This conflict was not resolved in subsequent notes.",
      "source_doc_ids": ["doc-uuid-admission", "doc-uuid-progress-day3"],
      "conflicting_text": {
        "source_1": { "doc": "Admission Note", "page": 2, "text": "Allergies: Penicillin (anaphylaxis)" },
        "source_2": { "doc": "Progress Note Day 3", "page": 1, "text": "Rx: Amoxicillin 500mg TID x 7 days" }
      },
      "recommendation": "Verify allergy status and medication intent with attending physician before discharge.",
      "resolved": false,
      "created_at": "2025-06-05T10:07:00Z"
    }
  ],
  "total": 3,
  "critical_count": 1,
  "high_count": 1,
  "medium_count": 1
}
```

---

### `PATCH /safety-flags/{flag_id}/resolve`
Mark a safety flag as resolved with clinician note.

**Request:**
```json
{
  "resolution_note": "Confirmed with patient: penicillin allergy was documented in error. Amoxicillin prescription is appropriate. Allergy record corrected in EHR.",
  "resolved_by": "dr.chen@hospital.org"
}
```

**Response `200 OK`:** Updated flag object.

---

## 6. Analytics Endpoints

### `GET /analytics/overview`
Get platform-level metrics.

**Response `200 OK`:**
```json
{
  "period": "last_30_days",
  "summaries": {
    "total_generated": 142,
    "approved": 138,
    "escalated": 4,
    "avg_generation_time_seconds": 47.3,
    "avg_clinician_review_time_minutes": 18.2
  },
  "safety": {
    "total_flags_raised": 89,
    "critical_flags": 6,
    "high_flags": 21,
    "flags_resolved_rate": 0.94,
    "top_flag_categories": [
      { "category": "MISSING_FIELD", "count": 34 },
      { "category": "MEDICATION_CONFLICT", "count": 22 }
    ]
  },
  "agent": {
    "avg_iterations_per_run": 13.4,
    "avg_tokens_per_run": 31200,
    "tool_success_rate": 0.987,
    "replanning_rate": 0.23
  },
  "quality": {
    "avg_section_rating": 4.1,
    "feedback_submitted_rate": 0.61,
    "top_issues": [
      { "issue_type": "INCOMPLETE", "section": "hospital_course", "count": 8 }
    ]
  }
}
```

---

### `GET /analytics/agent-performance`
Detailed per-tool performance metrics.

**Query Params:** `start_date`, `end_date`

**Response `200 OK`:**
```json
{
  "tool_metrics": [
    {
      "tool_name": "extract_diagnoses",
      "total_calls": 427,
      "success_rate": 0.993,
      "avg_latency_ms": 1840,
      "avg_tokens_consumed": 2100
    }
  ]
}
```

---

## API Error Reference

| Code | HTTP Status | Meaning |
|---|---|---|
| `PATIENT_NOT_FOUND` | 404 | Patient ID does not exist |
| `DOCUMENT_NOT_FOUND` | 404 | Document ID does not exist |
| `DOCUMENTS_NOT_READY` | 400 | Agent run requested but documents still processing |
| `RUN_ALREADY_ACTIVE` | 409 | An agent run is already in progress for this patient |
| `SUMMARY_NOT_FOUND` | 404 | Summary ID does not exist |
| `SUMMARY_ALREADY_APPROVED` | 409 | Cannot edit an approved summary |
| `CRITICAL_FLAGS_UNRESOLVED` | 422 | Cannot approve summary with unresolved CRITICAL flags |
| `INVALID_FILE_TYPE` | 400 | Uploaded file is not a PDF |
| `FILE_TOO_LARGE` | 413 | Uploaded file exceeds 50MB limit |
| `EXTRACTION_FAILED` | 500 | PDF could not be extracted |
| `AGENT_FAILED` | 500 | Agent run terminated with unrecoverable error |
