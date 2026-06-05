# DischargePilot AI — UI Mockups & Layout Specifications

---

## Global Layout Shell

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  ┌────────────────┐ ┌──────────────────────────────────────────────────┐    ║
║  │ SIDEBAR        │ │ TOPBAR                                           │    ║
║  │ 240px fixed    │ │ Logo · Page Title · User Menu        56px fixed  │    ║
║  │                │ └──────────────────────────────────────────────────┘    ║
║  │ ◈ DischargePilot│                                                         ║
║  │ AI             │ ┌──────────────────────────────────────────────────┐    ║
║  │ ─────────────  │ │ MAIN CONTENT AREA                                │    ║
║  │ ⬛ Dashboard   │ │ max-width: 1280px  padding: 32px                 │    ║
║  │ 👤 Patients    │ │ overflow-y: auto                                 │    ║
║  │ 🤖 Agent Runs  │ │                                                  │    ║
║  │ 🛡  Safety     │ │  [ PAGE CONTENT ]                                │    ║
║  │ 📄 Summaries   │ │                                                  │    ║
║  │ 📊 Analytics   │ │                                                  │    ║
║  │                │ │                                                  │    ║
║  │ ─────────────  │ │                                                  │    ║
║  │ ⚙  Settings    │ │                                                  │    ║
║  │ ? Help         │ │                                                  │    ║
║  └────────────────┘ └──────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════════════╝

Sidebar: bg neutral-900  text white  active item: bg brand-700 rounded-md
TopBar: bg white  border-bottom: 1px neutral-200
Main: bg neutral-50
```

---

## Mockup 1: Dashboard

```
╔══════════════════════════════════════════════════════════════════════════╗
║  SIDEBAR        ║  Dashboard                               Dr. Chen ▾  ║
╠═════════════════╬════════════════════════════════════════════════════════╣
║                 ║                                                        ║
║  ⬛ Dashboard ● ║  Good morning, Dr. Chen                                ║
║  👤 Patients    ║  Thursday, June 5, 2025 · 3 patients pending discharge ║
║  🤖 Agent Runs  ║                                                        ║
║  🛡  Safety     ║  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     ║
║  📄 Summaries   ║  │ 3           │ │ 1           │ │ ⛔ 1        │     ║
║  📊 Analytics   ║  │ Pending     │ │ Approved    │ │ Escalated   │     ║
║                 ║  │ Review      │ │ Today       │ │             │     ║
║                 ║  └─────────────┘ └─────────────┘ └─────────────┘     ║
║                 ║                                                        ║
║                 ║  ╔══════════════════════════════════════════════════╗  ║
║                 ║  ║ ⛔ CRITICAL ALERT                               ║  ║
║                 ║  ║ 1 summary has an unresolved critical safety flag ║  ║
║                 ║  ║ John Doe · Allergy conflict detected             ║  ║
║                 ║  ║                           [Review Now →]         ║  ║
║                 ║  ╚══════════════════════════════════════════════════╝  ║
║                 ║                                                        ║
║                 ║  TODAY'S DISCHARGE QUEUE                               ║
║                 ║  ┌──────────────────────────────────────────────────┐  ║
║                 ║  │ PATIENT        WARD      DOCS  STATUS   ACTION   │  ║
║                 ║  ├──────────────────────────────────────────────────┤  ║
║                 ║  │ John Doe       Int Med   4     ⚠ Escal  Review   │  ║
║                 ║  │ MRN-00123      3B              ated              │  ║
║                 ║  ├──────────────────────────────────────────────────┤  ║
║                 ║  │ Maria Santos   Cardiol   3     ● Pending Review  │  ║
║                 ║  │ MRN-00124      5A                        Review  │  ║
║                 ║  ├──────────────────────────────────────────────────┤  ║
║                 ║  │ Robert Kim     Neuro     2     ○ No Summary Upload│  ║
║                 ║  │ MRN-00125      2C                               │  ║
║                 ║  └──────────────────────────────────────────────────┘  ║
╚═════════════════╩════════════════════════════════════════════════════════╝
```

---

## Mockup 2: Patient Upload Center

```
╔══════════════════════════════════════════════════════════════════════════╗
║  ← Patients   Patient: John Doe  MRN-2025-00123     [+ New Patient]     ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  ┌───────────────────────────────────┐  ┌──────────────────────────┐   ║
║  │ UPLOAD DOCUMENTS                  │  │ PATIENT DETAILS          │   ║
║  │                                   │  │ ─────────────────────── │   ║
║  │ ┌───────────────────────────────┐ │  │ Name: John Doe           │   ║
║  │ │                               │ │  │ DOB:  March 15, 1971     │   ║
║  │ │   ↑                           │ │  │ MRN:  MRN-2025-00123     │   ║
║  │ │   Drop PDF files here         │ │  │ Gender: Male             │   ║
║  │ │   or click to browse          │ │  │                          │   ║
║  │ │                               │ │  │ Admitted: May 28, 2025   │   ║
║  │ │   [ Browse Files ]            │ │  │ Ward: Internal Med 3B    │   ║
║  │ │                               │ │  │ Attending: Dr. S. Chen   │   ║
║  │ │   PDF only · Max 50MB/file    │ │  │ ─────────────────────── │   ║
║  │ └───────────────────────────────┘ │  │ DOCUMENT CHECKLIST       │   ║
║  │                                   │  │ ✓ Admission Note         │   ║
║  │ UPLOADED DOCUMENTS                │  │ ✓ Progress Notes (2)     │   ║
║  │ ──────────────────────────────    │  │ ✓ Lab Reports            │   ║
║  │ 📄 admission_note.pdf      ✓      │  │ ✓ Medication Record      │   ║
║  │    Admission Note · 12pp · 240KB  │  │ ─────────────────────── │   ║
║  │                              [×]  │  │ AGENT STATUS             │   ║
║  │ 📄 progress_note_d1.pdf    ✓      │  │ ✅ All docs ready        │   ║
║  │    Progress Note · 4pp · 87KB     │  │                          │   ║
║  │                              [×]  │  │ ┌──────────────────────┐ │   ║
║  │ 📄 lab_report.pdf          ✓      │  │ │ Generate Discharge   │ │   ║
║  │    Lab Report · 8pp · 156KB       │  │ │ Summary →            │ │   ║
║  │                              [×]  │  │ └──────────────────────┘ │   ║
║  │ 📄 medication_record.pdf   ⟳      │  │                          │   ║
║  │    Medication Record · Processing │  └──────────────────────────┘   ║
║  └───────────────────────────────────┘                                  ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## Mockup 3: Agent Execution Center

```
╔══════════════════════════════════════════════════════════════════════════╗
║  ← Upload    Agent Execution — John Doe           Run: abc123           ║
║  ⟳ EXECUTING · 00:00:34 elapsed                  [View Documentation]  ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  ┌─────────────────────────────────┐  ┌─────────────────────────────┐  ║
║  │ EXECUTION TIMELINE              │  │ LIVE ACTIVITY               │  ║
║  │                                 │  │                             │  ║
║  │  ✓  Initialized           0.8s  │  │ 10:05:48  🤖 Planning...    │  ║
║  │  ✓  Extract Demographics  1.2s  │  │  Created 14-step plan       │  ║
║  │  ✓  Extract Diagnoses     2.1s  │  │                             │  ║
║  │  ✓  Extract Medications   1.9s  │  │ 10:05:49  🔧 extract_demos  │  ║
║  │  ✓  Extract Labs          2.4s  │  │  Found: John Doe, 54M...    │  ║
║  │  ●  Reconcile Meds  ───  3.1s  │  │                             │  ║
║  │      Cross-referencing 8 meds   │  │ 10:05:51  🔧 extract_diag  │  ║
║  │      across 3 source docs...    │  │  Found: T2DM, HTN, CKD      │  ║
║  │  ○  Detect Conflicts            │  │                             │  ║
║  │  ○  Safety Validation           │  │ 10:06:03  ⚠ Conflict found  │  ║
║  │  ○  Build: Demographics         │  │  Med dose discrepancy       │  ║
║  │  ○  Build: Diagnoses            │  │  (Metformin 500→1000mg)     │  ║
║  │  ○  Build: Medications          │  │                             │  ║
║  │  ○  Build: Hospital Course      │  │ 10:06:09  🤖 Re-planning    │  ║
║  │  ○  Link Evidence               │  │  Inserting conflict check   │  ║
║  │  ○  Finalize                    │  │                             │  ║
║  │                                 │  │ 10:06:14  🔧 reconcile_meds │  ║
║  │  Progress: 5/14  ████████░░░░░  │  │  Processing...              │  ║
║  └─────────────────────────────────┘  └─────────────────────────────┘  ║
║                                                                          ║
║  ┌─────────────────────────────────────────────────────────────────┐   ║
║  │ COUNTERS                                                         │   ║
║  │ Extractions: 4   Conflicts: 1   Safety Checks: 0/5   Tokens: 14.2K│  ║
║  └─────────────────────────────────────────────────────────────────┘   ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## Mockup 4: Safety Review Center

```
╔══════════════════════════════════════════════════════════════════════════╗
║  ← Agent Run   Safety Review — John Doe  MRN-2025-00123                 ║
║  3 safety items require your review before proceeding                   ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  [All (3)]  [⛔ Critical (1)]  [⚠ High (1)]  [○ Medium (1)]            ║
║                                                                          ║
║  ┌──────────────────────────────────────────────────────────────────┐   ║
║  │  ⛔  CRITICAL  ·  ALLERGY CONFLICT                               │   ║
║  │  ─────────────────────────────────────────────────────────────  │   ║
║  │  Prescribed medication conflicts with documented allergy         │   ║
║  │                                                                  │   ║
║  │  ┌─────────────────────────────────┐                            │   ║
║  │  │ Admission Note · Page 2         │                            │   ║
║  │  │ "ALLERGIES: Penicillin          │                            │   ║
║  │  │  (reaction: anaphylaxis)"       │                            │   ║
║  │  └─────────────────────────────────┘                            │   ║
║  │                        vs                                        │   ║
║  │  ┌─────────────────────────────────┐                            │   ║
║  │  │ Progress Note Day 3 · Page 1    │                            │   ║
║  │  │ "Rx: Amoxicillin 500mg          │                            │   ║
║  │  │  TID × 7 days"                 │                            │   ║
║  │  └─────────────────────────────────┘                            │   ║
║  │                                                                  │   ║
║  │  Recommendation: Verify allergy status and medication intent     │   ║
║  │  with attending before discharge.                                │   ║
║  │                                                                  │   ║
║  │  Resolution note: ________________________________________       │   ║
║  │  (Required to proceed)                                           │   ║
║  │                                      [Mark Resolved ✓]          │   ║
║  └──────────────────────────────────────────────────────────────────┘   ║
║                                                                          ║
║  ┌──────────────────────────────────────────────────────────────────┐   ║
║  │  ⚠  HIGH  ·  MEDICATION DOSE DISCREPANCY                         │   ║
║  │  Metformin: 500mg (Admission Note) vs 1000mg (MAR, updated       │   ║
║  │  June 1). Confirm intended discharge dose.        [Mark Resolved] │   ║
║  └──────────────────────────────────────────────────────────────────┘   ║
║                                                                          ║
║  ─────────────────────────────────────────────────────────────────────  ║
║  1 of 3 resolved  ·  Resolve all CRITICAL flags to proceed             ║
║                                           [View Summary →]  (disabled)  ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## Mockup 5: Summary Viewer

```
╔══════════════════════════════════════════════════════════════════════════╗
║  ← Safety Review   Discharge Summary — John Doe   Draft v1  [Approve →]║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  ┌──────────────────────────────────────────┐  ┌──────────────────────┐║
║  │ SUMMARY SECTIONS                         │  │ REVIEW PROGRESS      │║
║  │                                          │  │ 11/14 reviewed       │║
║  │ ◾ Patient Demographics   [HIGH ✓]       │  │ ████████████░░       │║
║  │ ◾ Diagnoses              [HIGH ✓]       │  │                      │║
║  │ ◾ Hospital Course        [HIGH ✓]       │  │ SAFETY FLAGS         │║
║  │ ◾ Procedures             [HIGH ✓]       │  │ ✓ 1 critical resolved│║
║  │ ◾ Allergies              [HIGH ✓]       │  │ ⚠ 1 high — pending   │║
║  │ ◾ Discharge Medications  [REVIEW ⚠]    │  │ ○ 1 medium — info    │║
║  │ ◾ Medication Changes     [REVIEW ⚠]    │  │ [View All Flags]     │║
║  │ ◾ Follow-Up Instructions  [HIGH ✓]      │  │                      │║
║  │ ◾ Pending Results        [INFO ●]       │  │ EVIDENCE PANEL       │║
║  │ ◾ Discharge Condition    [REVIEW ⚠]    │  │ ─────────────────── │║
║  │                                          │  │ Click any [source ↗] │║
║  ├──────────────────────────────────────────┤  │ chip to see full     │║
║  │                                          │  │ excerpt here.        │║
║  │  PRINCIPAL DIAGNOSIS                     │  │                      │║
║  │  ─────────────────────────────────────   │  │ EXPORT               │║
║  │  ● HIGH confidence              [Edit]   │  │ ─────────────────── │║
║  │                                          │  │ [Export PDF]         │║
║  │  Type 2 Diabetes Mellitus,               │  │ [Copy Text]          │║
║  │  uncontrolled (HbA1c 9.2%, 2025-05-29)  │  │ [Push to EHR]        │║
║  │                                          │  │                      │║
║  │  [Adm Note p.3 ↗]  [Lab Report p.1 ↗]  │  └──────────────────────┘║
║  │                                          │                          ║
║  │  DISCHARGE MEDICATIONS                   │                          ║
║  │  ─────────────────────────────────────   │                          ║
║  │  ⚠ NEEDS REVIEW                [Edit]   │                          ║
║  │                                          │                          ║
║  │  Metformin 1000mg PO BID                 │                          ║
║  │  Lisinopril 10mg PO daily (NEW)          │                          ║
║  │  Atorvastatin 40mg PO QHS               │                          ║
║  │  [NEEDS CLINICIAN REVIEW: Aspirin dose   │                          ║
║  │   unclear from source — 81mg or 325mg?]  │                          ║
║  │                                          │                          ║
║  │  [MAR p.4 ↗]  [Adm Note p.5 ↗]         │                          ║
║  │                                          │                          ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## Mockup 6: Trace Viewer

```
╔══════════════════════════════════════════════════════════════════════════╗
║  ← Summary   Agent Trace — John Doe   Run abc123   Completed 48.2s      ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  [All Steps]  [Tool: All ▾]  [✓ Success only]  [ Search... ]           ║
║                                                                          ║
║  ┌──────────────────────────────────────────────────────────────────┐   ║
║  │ Step 1  ·  extract_demographics  ·  ✓  1.2s               [▼]   │   ║
║  └──────────────────────────────────────────────────────────────────┘   ║
║  ┌──────────────────────────────────────────────────────────────────┐   ║
║  │ Step 2  ·  extract_diagnoses     ·  ✓  1.8s               [▼]   │   ║
║  └──────────────────────────────────────────────────────────────────┘   ║
║  ┌──────────────────────────────────────────────────────────────────┐   ║
║  │ Step 6  ·  reconcile_medications ·  ✓  3.8s               [▲]   │   ║
║  │  ─────────────────────────────────────────────────────────────── │   ║
║  │  INPUT                                                           │   ║
║  │  {                                                               │   ║
║  │    "admission_meds": [                                           │   ║
║  │      {"name": "Metformin", "dose": "500mg", "freq": "BID"}      │   ║
║  │    ],                                                            │   ║
║  │    "mar_meds": [                                                 │   ║
║  │      {"name": "Metformin", "dose": "1000mg", "freq": "BID",     │   ║
║  │       "updated": "2025-06-01"}                                   │   ║
║  │    ]                                                             │   ║
║  │  }                                                               │   ║
║  │                                                                  │   ║
║  │  OUTPUT                                                          │   ║
║  │  {                                                               │   ║
║  │    "reconciled": 8,                                              │   ║
║  │    "discrepancies": [{"med": "Metformin", "severity": "HIGH"}], │   ║
║  │    "changes": [{"type": "DOSE_CHANGED", "from": "500mg", ...}]  │   ║
║  │  }                                                               │   ║
║  │                                                                  │   ║
║  │  REASONING: "Dose updated during admission on 2025-06-01.       │   ║
║  │  Flagging as HIGH conflict for clinician confirmation."          │   ║
║  │                                                                  │   ║
║  │  Tokens: 1,840 in / 420 out  ·  Latency: 3,840ms               │   ║
║  └──────────────────────────────────────────────────────────────────┘   ║
║                                                                          ║
║  ┌──────────────────────────────────────────────────────────────────┐   ║
║  │ RUN SUMMARY                                                      │   ║
║  │ Total steps: 14   Re-plans: 1   Conflicts: 2   Flags: 3         │   ║
║  │ Total latency: 48.2s   Tokens: 24,300 in / 8,800 out            │   ║
║  └──────────────────────────────────────────────────────────────────┘   ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## Mockup 7: Analytics Dashboard

```
╔══════════════════════════════════════════════════════════════════════════╗
║  Analytics Dashboard                    [Last 30 Days ▾]  [Export ▾]  ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌──────────┐ ║
║  │ 142            │ │ 47.3s          │ │ 97%            │ │ 18.2 min │ ║
║  │ Summaries      │ │ Avg Gen Time   │ │ Approval Rate  │ │ Avg Rev  │ ║
║  │ Generated      │ │                │ │                │ │ Time     │ ║
║  │ +8% vs prev    │ │ -3.2s vs prev  │ │ ↑ +1.2%        │ │ -2min    │ ║
║  └────────────────┘ └────────────────┘ └────────────────┘ └──────────┘ ║
║                                                                          ║
║  ┌──────────────────────────────┐ ┌────────────────────────────────┐   ║
║  │ SUMMARY STATUS BREAKDOWN     │ │ DAILY SUMMARY VOLUME           │   ║
║  │                              │ │                                │   ║
║  │    ████ Approved (97%)       │ │  ██  █  ██  ██  ██  ██  ██   │   ║
║  │     ██  Pending  (2%)        │ │  ██  █  ██  ██  ██  ██  ██   │   ║
║  │      █  Escalated(1%)        │ │  ██  ██ ██  ██  ██  ██  ██   │   ║
║  │                              │ │  Mon Tue Wed Thu Fri Sat Sun  │   ║
║  └──────────────────────────────┘ └────────────────────────────────┘   ║
║                                                                          ║
║  SAFETY FLAG CATEGORIES (last 30 days)                                  ║
║  ┌──────────────────────────────────────────────────────────────────┐   ║
║  │ Missing Field        ████████████████████████  34  (38%)        │   ║
║  │ Medication Conflict  ██████████████            22  (25%)        │   ║
║  │ Dose Discrepancy     ████████                  14  (16%)        │   ║
║  │ Pending Result       ██████                    10  (11%)        │   ║
║  │ Allergy Conflict     ████                       6  (7%)         │   ║
║  │ Diagnosis Conflict   ██                         3  (3%)         │   ║
║  └──────────────────────────────────────────────────────────────────┘   ║
║                                                                          ║
║  TOOL PERFORMANCE                                                        ║
║  ┌──────────────────────┬──────────┬───────────┬─────────┬───────────┐ ║
║  │ TOOL                 │ CALLS    │ SUCCESS % │ AVG ms  │ AVG TOKENS│ ║
║  ├──────────────────────┼──────────┼───────────┼─────────┼───────────┤ ║
║  │ extract_diagnoses    │ 427      │ 99.3%     │ 1,840ms │ 2,100     │ ║
║  │ reconcile_meds       │ 412      │ 98.8%     │ 3,240ms │ 3,400     │ ║
║  │ detect_conflicts     │ 398      │ 99.7%     │ 2,100ms │ 1,800     │ ║
║  │ validate_safety      │ 427      │ 100%      │ 1,200ms │ 1,500     │ ║
║  └──────────────────────┴──────────┴───────────┴─────────┴───────────┘ ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## Responsive Breakpoints

| Breakpoint | Width | Layout Change |
|---|---|---|
| `xl` | 1280px+ | Full 3-column dashboard grid |
| `lg` | 1024px–1279px | 2-column grid, sidebar fixed |
| `md` | 768px–1023px | Sidebar collapses to icon-only mode |
| `sm` | 640px–767px | Full-width single column, sidebar hidden (hamburger) |

**Primary design target: 1280px+ (hospital workstation)**

Clinical workflows on mobile are not supported in Phase 1. Tablet (iPad landscape) should render correctly at the `lg` breakpoint.
