# DischargePilot AI — Application Pages Design

---

## Page 1: Dashboard

### Purpose
The clinical command center. Clinicians start here each session. The dashboard communicates the current state of all pending discharges and surfaces anything requiring immediate attention.

### Layout
```
┌──────────────────────────────────────────────────────────────────┐
│  TOP BAR                                                         │
│  DischargePilot AI    [Today: June 5, 2025]    [Dr. Chen ▾]     │
├──────────────────────────────────────────────────────────────────┤
│  SIDEBAR │  MAIN CONTENT                                         │
│          │                                                       │
│  Dash    │  PAGE HEADER                                          │
│  Patients│  Good morning, Dr. Chen                               │
│  Agent   │  3 patients pending discharge today                   │
│  Safety  │                                                       │
│  Summary │  ─── STAT WIDGETS (4-column grid) ──────────────────  │
│  Analyti │  [Pending Review: 3]  [Approved: 1]  [Escalated: 1]  │
│          │  [Critical Flags: 2]                                  │
│          │                                                       │
│          │  ─── ESCALATION BANNER (if any critical flags) ──── │
│          │  ⛔  1 summary has unresolved critical safety flags   │
│          │  John Doe — Allergy conflict requires your attention  │
│          │  [Review Now]                                         │
│          │                                                       │
│          │  ─── DISCHARGE QUEUE (primary content area) ────── │
│          │  Patient queue table for today's discharges           │
│          │  Columns: Patient | Ward | Documents | Status | Time  │
│          │           | Actions                                   │
│          │                                                       │
│          │  ─── RECENT ACTIVITY (secondary, right panel) ──── │
│          │  Activity feed: agent completions, approvals, flags  │
└──────────────────────────────────────────────────────────────────┘
```

### Widgets

**Metric Cards (top row):**
- Pending Review: summaries waiting for clinician review
- Approved Today: summaries approved in last 24h
- Escalated: summaries with unresolved CRITICAL flags
- Critical Flags: total unresolved critical safety flags

**Escalation Banner:**
Appears only when there are unresolved CRITICAL safety flags. Red background. Persistent — does not auto-dismiss. Lists each escalated patient by name with a direct link to their safety review.

**Discharge Queue Table:**
- Patient name + MRN
- Ward
- Document count + types uploaded
- Summary status badge
- Agent last run timestamp
- Quick action: View / Review / Upload Documents

**Recent Activity Feed:**
Scrollable list of recent system events. Shows:
- Agent run completed (with patient name)
- Summary approved (with clinician)
- Safety flag resolved
- New document uploaded
Each item: icon + description + relative time

### User Flow
1. Clinician sees escalation banner → clicks "Review Now" → Safety Review
2. Clinician sees pending review patient → clicks "Review" → Safety Review
3. Clinician needs to start a new patient → clicks "New Patient" → Upload Center

---

## Page 2: Patient Upload Center

### Purpose
Manage the document corpus for a specific patient. Upload PDFs, monitor processing, and trigger the agent when all documents are ready.

### Layout
```
┌──────────────────────────────────────────────────────────────────┐
│  PAGE HEADER                                                     │
│  ← Back     Patient: John Doe  MRN-2025-00123     [New Patient] │
│  Internal Medicine 3B  |  Admitted: May 28, 2025                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LEFT PANEL (60%)              │ RIGHT PANEL (40%)              │
│                                │                                │
│  UPLOAD ZONE                   │ PATIENT INFO CARD              │
│  ┌──────────────────────────┐  │ Full patient demographics      │
│  │                          │  │ Admission details              │
│  │   Drag & drop PDFs here  │  │                                │
│  │   or click to browse     │  │ ─────────────────────────────  │
│  │                          │  │ UPLOAD CHECKLIST               │
│  │   [Browse Files]         │  │ □ Admission Note               │
│  │                          │  │ □ Progress Notes (≥1)          │
│  └──────────────────────────┘  │ □ Lab Reports                  │
│  Accepted: PDF only, max 50MB  │ □ Medication Record            │
│                                │                                │
│  DOCUMENT LIST                 │ AGENT READY STATUS             │
│  ─────────────────────────── │ All required docs uploaded?     │
│  [Doc card] Admission Note ✓  │ ✓ Ready to Generate            │
│  [Doc card] Progress Note  ✓  │ [Generate Discharge Summary →] │
│  [Doc card] Lab Report     ✓  │                                │
│  [Doc card] MAR         ⟳ ... │                                │
│                                │                                │
└──────────────────────────────────────────────────────────────────┘
```

### Document Card
Each uploaded document shows:
- Document type icon + label
- Filename
- Page count (after processing)
- File size
- Processing status (PROCESSING spinner / PROCESSED checkmark / FAILED error)
- Delete button (only before agent run)

### Upload Workflow
1. User drags file(s) into drop zone
2. User selects document type from dropdown per file (or system detects from filename)
3. Upload begins immediately — progress bar per file
4. Processing begins automatically — status updates in real time
5. Once all docs processed: "Generate Discharge Summary" button becomes active
6. Click Generate → navigates to Agent Execution Center for this run

### Validation
- Files must be PDF — non-PDF shows inline error on the file card
- Files over 50MB show size error
- Duplicate file uploads are warned but not blocked
- If any document fails processing, it shows a FAILED state with error reason and a "Retry" button

---

## Page 3: Agent Execution Center

### Purpose
Real-time visualization of the agent processing the patient's documents. Clinician can watch the agent work or leave and return to the completed summary.

### Layout
```
┌──────────────────────────────────────────────────────────────────┐
│  PAGE HEADER                                                     │
│  ← Back     Agent Run — John Doe     [Run ID: abc123]           │
│  Status: ⟳ EXECUTING  |  Started: 2m 14s ago                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LEFT PANEL (55%)              │ RIGHT PANEL (45%)              │
│                                │                                │
│  EXECUTION TIMELINE            │ LIVE ACTIVITY FEED             │
│  ─────────────────────         │ ─────────────────────────────  │
│  [✓] Initialized        0.8s  │ [Bot] Planning extraction...   │
│  [✓] Extract Demographics 1.2s│ [Tool] extract_demographics     │
│  [✓] Extract Diagnoses  1.8s  │   Found: T2DM, HTN, CKD        │
│  [✓] Extract Medications 2.1s │ [Tool] extract_medications      │
│  [✓] Extract Labs       2.4s  │   Found: 8 medications          │
│  [⟳] Reconciling...  ──────   │ [⚠] Conflict detected          │
│  [ ] Detect Conflicts         │   Medication dose discrepancy   │
│  [ ] Safety Validation        │ [Bot] Re-planning...            │
│  [ ] Generate Sections        │ [Tool] reconcile_medications    │
│                               │   In progress...               │
│  CURRENT STEP                 │                                │
│  ┌──────────────────────────┐  │ COUNTERS                       │
│  │ reconcile_medications    │  │ Extractions: 4 complete        │
│  │ Cross-referencing 8 meds │  │ Conflicts found: 1             │
│  │ across 3 source docs...  │  │ Safety checks: 0/5             │
│  └──────────────────────────┘  │ Tokens used: 14,200            │
│                                │                                │
│  PLAN VIEWER (collapsed)       │ [View Full Log]                │
│  [▼ Show execution plan]       │                                │
│                                │                                │
└──────────────────────────────────────────────────────────────────┘
```

When complete:
```
Status: ✓ COMPLETED in 48 seconds
[Review Safety Flags →]  (primary CTA, if any flags)
[View Summary →]         (secondary CTA, if no flags)
```

### Timeline States
- **Completed step:** Gray text, checkmark, latency in ms shown
- **Current step:** Bold brand-blue text, spinning icon, pulsing background, description of what's happening
- **Pending step:** Light gray, empty circle
- **Failed step:** Red text, X icon, error message inline

### User Flow
- Agent runs automatically in background
- If clinician leaves this page, execution continues
- Notification (toast) triggers when execution completes
- Clicking "Review Safety Flags" → Safety Review Center

---

## Page 4: Trace Viewer

### Purpose
Full audit log of everything the agent did. Used by clinicians who want to understand WHY a section was generated the way it was, or by administrators investigating a flagged summary.

### Layout
```
┌──────────────────────────────────────────────────────────────────┐
│  PAGE HEADER                                                     │
│  ← Back to Summary     Agent Trace — John Doe   Run: abc123     │
│  Completed 2025-06-05 10:07:48  |  48.2s  |  33,100 tokens     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  FILTERS BAR                                                     │
│  [All Steps ▾]  [All Tools ▾]  [Success only ▾]  [Search]      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TRACE STEPS (scrollable list)                                  │
│                                                                  │
│  ─ Step 1 — extract_demographics ──────────── 1.2s ✓ ─────────  │
│  │  Input: doc_ids=["doc-abc"], target_fields=[name, dob...]    │
│  │  Output: {first_name: "John", last_name: "Doe", dob: ...}   │
│  │  Evidence: Admission Note p.1                                │
│  │  Reasoning: "Demographics extracted from admission header"   │
│  └───────────────────────────────────────────────────────────── │
│                                                                  │
│  ─ Step 6 — reconcile_medications ──────────── 3.8s ✓ ───────── │
│  │  Input: admission_meds=[...], mar_meds=[...]                 │
│  │  Output: {reconciled: 8, discrepancies: 1, changes: 2}      │
│  │  Discrepancy found: Metformin 500mg (admission) vs 1000mg   │
│  │    (MAR — updated 2025-06-01)                                │
│  │  Reasoning: "Dose updated during admission — flagged as      │
│  │    MEDIUM conflict for clinician confirmation"               │
│  └───────────────────────────────────────────────────────────── │
│                                                                  │
│  SUMMARY PANEL (right, 30%)                                     │
│  Run Statistics                                                  │
│  Total steps: 14                                                 │
│  Re-planning cycles: 1                                           │
│  Conflicts detected: 2                                           │
│  Safety flags created: 3                                         │
│  Total latency: 48.2s                                            │
│  Tokens in: 24,300 | out: 8,800                                 │
└──────────────────────────────────────────────────────────────────┘
```

### Trace Step Expansion
Each step is collapsed by default showing: step number, tool name, status, latency. Click to expand:
- Full JSON input (formatted)
- Full JSON output (formatted, with any nested evidence refs)
- Claude API call details if applicable (tokens, model version)
- Agent reasoning text

---

## Page 5: Safety Review Center

### Purpose
The mandatory review stop before the clinician sees the summary. Forces explicit engagement with every safety flag before proceeding to the summary review.

### Layout
```
┌──────────────────────────────────────────────────────────────────┐
│  PAGE HEADER                                                     │
│  Safety Review — John Doe  MRN-2025-00123                       │
│  ⚠  3 items require your attention before reviewing the summary  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  FILTER TABS                                                     │
│  [All (3)] [Critical (1)] [High (1)] [Medium (1)]               │
│  [Medication Changes (1)] [Missing Fields (1)]                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ⛔ CRITICAL — ALLERGY CONFLICT                                  │
│  ─────────────────────────────────────────────────────────────  │
│  Prescribed medication conflicts with documented allergy        │
│                                                                  │
│  Admission Note (p.2):                                          │
│  "Allergies: Penicillin (anaphylaxis)"                          │
│                                                                  │
│  Progress Note Day 3 (p.1):                                     │
│  "Rx: Amoxicillin 500mg TID x 7 days"                          │
│                                                                  │
│  Recommendation: Verify allergy and medication before discharge  │
│                                                                  │
│  Resolution Note: __________________________________ [Required] │
│  [Mark Resolved ✓]                                              │
│  ─────────────────────────────────────────────────────────────  │
│                                                                  │
│  ⚠ HIGH — MEDICATION DOSE DISCREPANCY                           │
│  [... expanded similar structure ...]                           │
│                                                                  │
│  ○ MEDIUM — MISSING DISCHARGE CONDITION                         │
│  [... expanded similar structure ...]                           │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│  FOOTER BAR                                                      │
│  1 of 3 resolved                                                │
│  [View Summary →]  (disabled until all CRITICAL flags resolved) │
└──────────────────────────────────────────────────────────────────┘
```

### Safety Review Rules
- CRITICAL flags must be resolved (with resolution note) before "View Summary" is enabled
- HIGH and MEDIUM flags can be left unresolved, but they remain visible in the summary
- Each flag resolution is logged with the clinician's identity and timestamp
- "View Summary →" navigates to the Summary Viewer only after critical flag resolution

---

## Page 6: Summary Viewer

### Purpose
The primary clinical review interface. The clinician reviews the generated discharge summary section by section, edits as needed, and approves for finalization.

### Layout
```
┌──────────────────────────────────────────────────────────────────┐
│  PAGE HEADER                                                     │
│  Discharge Summary — John Doe  MRN-2025-00123   [Draft v1]      │
│  Generated: June 5, 2025 10:07  |  Agent Run abc123             │
│                                                                  │
│  STATUS: ● Pending Review   [Approve Summary →]  [Export ▾]    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  MAIN CONTENT (70%)              │ SIDEBAR (30%)                │
│                                  │                              │
│  SECTION NAVIGATION              │ REVIEW PROGRESS              │
│  [Demographics ✓] [Diagnoses ✓]  │ 12/14 sections reviewed      │
│  [Medications ⚠] [Procedures ✓]  │ ████████████░░               │
│                                  │                              │
│  ──── PATIENT DEMOGRAPHICS ─── │ SAFETY SUMMARY               │
│  ┌───────────────────────────┐   │ 3 flags raised               │
│  │ [HIGH confidence]    [Edit]│   │ 1 critical — resolved        │
│  │                            │   │ 2 others — see review        │
│  │ John Doe, 54M              │   │ [View All Flags]             │
│  │ MRN: MRN-2025-00123        │   │                              │
│  │ DOB: March 15, 1971        │   │ EVIDENCE PANEL               │
│  │ Admitted: May 28, 2025     │   │ Click any citation chip      │
│  │ Attending: Dr. Sarah Chen  │   │ to see source text here      │
│  │                            │   │                              │
│  │ Evidence: [Adm Note p.1 ↗] │   │ ─────────────────────────── │
│  └───────────────────────────┘   │ EXPORT ACTIONS               │
│                                  │ [Export as PDF]              │
│  ──── PRINCIPAL DIAGNOSIS ─── │ [Copy to Clipboard]          │
│  ┌───────────────────────────┐   │ [Push to EHR]                │
│  │ [HIGH confidence]    [Edit]│   │                              │
│  │ T2DM, uncontrolled         │   │                              │
│  │ (HbA1c 9.2%)               │   │                              │
│  │ [Adm Note p.3 ↗][Lab p.1↗]│   │                              │
│  └───────────────────────────┘   │                              │
│                                  │                              │
│  ──── DISCHARGE MEDICATIONS ── │                              │
│  ┌─────────────────────────────┐  │                              │
│  │ [NEEDS REVIEW ⚠]      [Edit]│  │                              │
│  │ Metformin 1000mg PO BID     │  │                              │
│  │ Lisinopril 10mg PO daily    │  │                              │
│  │  [NEEDS CLINICIAN REVIEW]   │  │                              │
│  │ [MAR p.4 ↗] [Adm Note p.5↗]│  │                              │
│  └─────────────────────────────┘  │                              │
└──────────────────────────────────────────────────────────────────┘
```

### Section Edit Mode
When clinician clicks "Edit" on a section:
```
The section content area becomes an editable textarea.
Original content shown below for reference.
[Save Changes]  [Cancel]
All edits logged with clinician identity and timestamp.
Version number increments on save.
```

### Approval Flow
1. Clinician clicks "Approve Summary →"
2. Modal appears:
   - Shows summary of unresolved non-critical flags (if any) — clinician must confirm they've been reviewed
   - Attestation statement: "I confirm this discharge summary is accurate and clinically appropriate."
   - [Confirm & Approve] button
3. Summary status changes to APPROVED
4. Summary is locked for editing
5. Export options become available

---

## Page 7: Analytics Dashboard

### Purpose
Platform performance overview for clinical administrators, quality officers, and the attending team. Tracks safety metrics, agent performance, and documentation quality over time.

### Layout
```
┌──────────────────────────────────────────────────────────────────┐
│  PAGE HEADER                                                     │
│  Analytics    [Last 7 Days ▾]  [All Wards ▾]  [Export Report]  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TOP METRICS ROW (4 cards)                                      │
│  [Total Summaries: 142]  [Avg Gen Time: 47s]                    │
│  [Safety Flag Rate: 1.8/summary]  [Approval Rate: 97%]          │
│                                                                  │
│  ROW 2: CHARTS (2-column)                                       │
│  [Summaries by Status — Donut Chart]                            │
│  [Daily Summary Volume — Bar Chart]                             │
│                                                                  │
│  ROW 3: SAFETY METRICS (2-column)                               │
│  [Flag Categories — Horizontal Bar Chart]                       │
│  [Flag Resolution Rate — Line Chart]                            │
│                                                                  │
│  ROW 4: TABLES (full width)                                     │
│  [Top Safety Issues by Category]                                │
│  Category | Count | Avg Resolution Time | Resolution Rate        │
│                                                                  │
│  [Agent Tool Performance Table]                                 │
│  Tool | Calls | Success Rate | Avg Latency | Avg Tokens         │
│                                                                  │
│  ROW 5: QUALITY FEEDBACK                                        │
│  [Section Quality Ratings — horizontal bar per section]         │
│  [Common Issues by Section — table]                             │
└──────────────────────────────────────────────────────────────────┘
```

### Key Metrics Tracked
- Summaries generated per day / week / month
- Average agent execution time
- Average clinician review time
- Approval rate (approved vs. discarded)
- Escalation rate (summaries with CRITICAL flags)
- Flag resolution rate
- Per-section quality ratings (from learning feedback)
- Most common missing fields
- Most common conflict types
- Re-planning rate (% of runs that required re-planning)
