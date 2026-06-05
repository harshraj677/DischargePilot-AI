# DischargePilot AI — UI/UX Design System

---

## Design Token Reference

All tokens are defined as CSS custom properties in `globals.css` and mapped to Tailwind via `tailwind.config.ts`.

---

## Color System

### Clinical Color Palette

The color system is built around clinical meaning. Colors signal status and severity, not decoration.

```css
/* Primary Brand — Trust Blue */
--color-brand-50:  #EFF6FF;
--color-brand-100: #DBEAFE;
--color-brand-200: #BFDBFE;
--color-brand-400: #60A5FA;
--color-brand-600: #2563EB;    /* Primary action color */
--color-brand-700: #1D4ED8;    /* Primary hover */
--color-brand-900: #1E3A8A;    /* Dark contexts */

/* Neutral — Clinical Gray */
--color-neutral-50:  #F8FAFC;  /* Page background */
--color-neutral-100: #F1F5F9;  /* Card background */
--color-neutral-200: #E2E8F0;  /* Borders */
--color-neutral-300: #CBD5E1;  /* Dividers */
--color-neutral-500: #64748B;  /* Secondary text */
--color-neutral-700: #334155;  /* Body text */
--color-neutral-900: #0F172A;  /* Headings */

/* Severity — CRITICAL (Red) */
--color-critical-50:  #FFF1F2;
--color-critical-100: #FFE4E6;
--color-critical-500: #EF4444;
--color-critical-600: #DC2626;  /* Critical badge text */
--color-critical-700: #B91C1C;
--color-critical-bg:  #FFF1F2;  /* Critical flag background */
--color-critical-border: #FECDD3;

/* Severity — HIGH (Orange) */
--color-high-50:  #FFF7ED;
--color-high-500: #F97316;
--color-high-600: #EA580C;
--color-high-bg:  #FFF7ED;
--color-high-border: #FED7AA;

/* Severity — MEDIUM (Amber) */
--color-medium-50:  #FFFBEB;
--color-medium-500: #F59E0B;
--color-medium-600: #D97706;
--color-medium-bg:  #FFFBEB;
--color-medium-border: #FDE68A;

/* Severity — INFO (Blue) */
--color-info-50:  #EFF6FF;
--color-info-500: #3B82F6;
--color-info-600: #2563EB;
--color-info-bg:  #EFF6FF;
--color-info-border: #BFDBFE;

/* Status — Success (Green) */
--color-success-50:  #F0FDF4;
--color-success-500: #22C55E;
--color-success-600: #16A34A;
--color-success-bg:  #F0FDF4;
--color-success-border: #BBF7D0;

/* Confidence — Needs Review (Amber dashed underline) */
--color-needs-review: #D97706;

/* Missing Data */
--color-missing-text: #94A3B8;  /* Gray italic for NOT DOCUMENTED */
```

### Color Usage Rules

| Use | Token |
|---|---|
| Primary actions (buttons, links) | `brand-600` |
| Page background | `neutral-50` |
| Card / panel background | `white` or `neutral-100` |
| Body text | `neutral-700` |
| Secondary text / labels | `neutral-500` |
| Borders | `neutral-200` |
| CRITICAL safety flags | `critical-*` |
| HIGH safety flags | `high-*` |
| MEDIUM safety flags | `medium-*` |
| INFO / pending items | `info-*` |
| Approved / success states | `success-*` |
| Missing / not documented text | `missing-text` (gray italic) |

**Never use color alone for clinical severity.** Always pair with icon + text label.

---

## Typography

```css
/* Font Stack */
--font-sans: 'Inter', system-ui, -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;  /* Used for MRNs, IDs */

/* Clinical Data Font — slightly more readable for medical text */
--font-clinical: 'Inter', sans-serif;
```

### Type Scale

| Role | Size | Weight | Line Height | Usage |
|---|---|---|---|---|
| `page-title` | 24px / 1.5rem | 700 | 1.25 | Page headings |
| `section-title` | 18px / 1.125rem | 600 | 1.35 | Card/section titles |
| `subsection-title` | 14px / 0.875rem | 600 | 1.4 | Sub-section headings, labels |
| `body` | 14px / 0.875rem | 400 | 1.6 | Body text, clinical content |
| `body-sm` | 13px / 0.8125rem | 400 | 1.5 | Secondary info, captions |
| `label` | 12px / 0.75rem | 500 | 1.4 | Form labels, table headers |
| `mono` | 13px / 0.8125rem | 400 | 1.6 | MRNs, IDs, code values |
| `clinical-value` | 14px / 0.875rem | 500 | 1.4 | Lab values, medication doses |

**Minimum readable size:** 12px. No clinical data smaller than 13px.

---

## Spacing System

Based on a 4px base unit.

```
4px   (1)  — tight inline spacing, icon-to-text gap
8px   (2)  — small gaps, padding inside badges
12px  (3)  — element padding, small internal gaps
16px  (4)  — standard component padding, between related elements
20px  (5)  — section internal padding
24px  (6)  — between sections within a card
32px  (8)  — between cards, major layout sections
48px  (12) — page-level section breaks
64px  (16) — major page section separators
```

---

## Component Library

### Buttons

```
PRIMARY BUTTON
┌──────────────────────────┐
│   Generate Summary   →   │
└──────────────────────────┘
bg: brand-600  text: white  rounded-md  px-16 py-8  font-500
hover: brand-700  focus-ring: brand-400  disabled: opacity-50

SECONDARY BUTTON (Outline)
┌──────────────────────────┐
│      View Trace          │
└──────────────────────────┘
bg: white  border: neutral-200  text: neutral-700
hover: bg neutral-50

DESTRUCTIVE BUTTON
bg: critical-600  text: white
Only used for irreversible actions like deleting a document

GHOST BUTTON
No border, no background — text only with hover bg neutral-100
Used for low-priority inline actions
```

---

### Status Badges

Small, pill-shaped labels. Color + icon + text. Never color alone.

```
PENDING REVIEW
[●] Pending Review
bg: amber-100  text: amber-700  border: amber-200

APPROVED
[✓] Approved
bg: green-100  text: green-700  border: green-200

IN REVIEW
[⟳] In Review
bg: blue-100  text: blue-700  border: blue-200

ESCALATED
[⚠] Escalated
bg: red-100  text: red-700  border: red-200

INCOMPLETE
[○] Incomplete
bg: gray-100  text: gray-600  border: gray-200
```

---

### Safety Flag Cards

The primary safety communication component. Used in the Safety Review Center.

```
CRITICAL SAFETY FLAG
┌─────────────────────────────────────────────────────────────────┐
│ ⛔ CRITICAL  │  ALLERGY CONFLICT                                │
│──────────────────────────────────────────────────────────────── │
│ Prescribed medication conflicts with documented allergy          │
│                                                                 │
│ Admission Note (p.2): "Allergies: Penicillin (anaphylaxis)"    │
│ Progress Note Day 3 (p.1): "Rx: Amoxicillin 500mg TID x 7d"   │
│                                                                 │
│ Recommendation: Verify allergy and medication intent.           │
│                                                                 │
│ [Mark Resolved]                     [View Source Documents]     │
└─────────────────────────────────────────────────────────────────┘
left-border: 4px solid critical-600
bg: critical-50
title: critical-700 font-600
```

```
HIGH SAFETY FLAG — same structure, orange theme
MEDIUM SAFETY FLAG — same structure, amber theme
INFO FLAG — same structure, blue theme, no "Mark Resolved" action needed
```

---

### Evidence Reference Chips

Inline citations attached to generated text.

```
Normal state (inline):
 [Admission Note p.2 ↗]
 bg: neutral-100  text: neutral-600  rounded  px-8 py-2  text-12  border: neutral-200

Hover state:
 Expands to show excerpt tooltip:
 ┌──────────────────────────────────────────┐
 │ Admission Note — Page 2                  │
 │ ─────────────────────────────────────── │
 │ "Patient: John Doe, DOB: 1971-03-15.    │
 │  Admitted 2025-05-28. Allergies:         │
 │  Penicillin (anaphylaxis)..."            │
 └──────────────────────────────────────────┘
```

---

### Summary Section Cards

The primary display component for each discharge summary section.

```
┌───────────────────────────────────────────────────────────────────┐
│  PRINCIPAL DIAGNOSIS                    [HIGH confidence]  [Edit] │
│──────────────────────────────────────────────────────────────────  │
│  Type 2 Diabetes Mellitus, uncontrolled (HbA1c 9.2%)              │
│                                                                    │
│  Evidence:                                                         │
│  [Admission Note p.3 ↗]  [Lab Report p.1 ↗]                      │
└───────────────────────────────────────────────────────────────────┘
border: neutral-200  rounded-lg  shadow-sm

For sections needing review:
┌───────────────────────────────────────────────────────────────────┐
│  DISCHARGE MEDICATIONS              [NEEDS REVIEW ⚠]  [Edit]     │
│──────────────────────────────────────────────────────────────────  │
│  Metformin 1000mg PO BID                                           │
│  Lisinopril 10mg PO daily [NEEDS CLINICIAN REVIEW]                │
│                                                                    │
│  Evidence: [Medication Record p.4 ↗]                              │
└───────────────────────────────────────────────────────────────────┘
section header bg: amber-50  top-border: 3px solid amber-400
```

---

### Execution Timeline Component

Used in the Agent Execution Center.

```
AGENT EXECUTION TIMELINE

[✓] Initialized          00:01  extract_demographics
[✓] Extracted Diagnoses  00:04  extract_diagnoses
[✓] Extracted Meds       00:06  extract_medications
[⟳] Reconciling...       00:09  reconcile_medications  ← current (animated)
[ ] Conflict Detection
[ ] Safety Validation
[ ] Generate Sections

Each completed step:  gray text, checkmark icon, latency shown
Current step:         bold text, spinning icon, pulsing background
Pending steps:        light gray, empty circle icon
```

---

### Tables

Clinical data tables: high information density, compact rows, clear column headers.

```
TABLE STRUCTURE
┌──────────────┬───────────────────┬────────────┬────────────┬──────────┐
│ PATIENT      │ WARD              │ DOCUMENTS  │ STATUS     │ ACTION   │
├──────────────┼───────────────────┼────────────┼────────────┼──────────┤
│ John Doe     │ Internal Med 3B   │ 4 files    │ ● Pending  │ Review   │
│ MRN-00123   │                   │            │   Review   │          │
├──────────────┼───────────────────┼────────────┼────────────┼──────────┤
│ Jane Smith   │ Cardiology 5A     │ 3 files    │ ✓ Approved │ View     │
│ MRN-00124   │                   │            │            │          │
└──────────────┴───────────────────┴────────────┴────────────┴──────────┘

Row height: 52px
Header: neutral-700 font-600 uppercase tracking-wide text-12
Body: neutral-700 text-14
Alternating rows: white / neutral-50
Hover: brand-50 background
Border: neutral-200
```

---

### Metric Cards

Used on the Dashboard and Analytics pages.

```
┌─────────────────────────┐
│  ↑                      │
│  142                    │
│  Summaries Generated    │
│  +12% this month        │
└─────────────────────────┘

Icon: top-left, brand-600, 20px
Number: neutral-900, 32px, font-700
Label: neutral-500, 13px
Trend: success-600 (up) / critical-600 (down), 12px
```

---

### Conflict Display Component

```
CONFLICT: MEDICATION DISCREPANCY
┌─────────────────────────────────────────────────────────────────┐
│  MEDICATION CONFLICT  │  Severity: HIGH                         │
│─────────────────────────────────────────────────────────────────│
│  SOURCE 1: Admission Note (Page 3)                              │
│  "Metformin 500mg PO BID on admission"                          │
│                                                                 │
│  SOURCE 2: Medication Record (Page 2)                           │
│  "Metformin 1000mg PO BID (updated 2025-06-01)"                 │
│                                                                 │
│  Dose discrepancy detected. Confirm intended discharge dose.    │
│─────────────────────────────────────────────────────────────────│
│  [Mark Resolved — 500mg]  [Mark Resolved — 1000mg]  [Escalate] │
└─────────────────────────────────────────────────────────────────┘
```

---

### Loading States

No full-page spinners. Every loading state is scoped to the component being loaded.

```
SKELETON LOADER (for cards and sections):
A shimmering gray placeholder with the same dimensions as the expected content.
animation: shimmer (left-to-right gradient sweep, 1.5s, repeat)

INLINE SPINNER (for button actions):
16px spinner replacing button text while action is in progress.
Prevents double-submission.

AGENT PROGRESS (for execution):
The timeline component IS the loading state — it shows real progress.
```

---

## Icon Set

Use Lucide React icons throughout — consistent, accessible, open source.

| Context | Icon |
|---|---|
| Critical flag | `ShieldAlert` |
| High flag | `AlertTriangle` |
| Medium flag | `AlertCircle` |
| Info | `Info` |
| Approved / Success | `CheckCircle2` |
| Needs review | `Eye` |
| Missing data | `HelpCircle` |
| Evidence reference | `FileText` |
| Agent executing | `Bot` |
| Agent trace | `GitBranch` |
| Patient | `User` |
| Upload | `Upload` |
| Export | `Download` |
| Edit | `Pencil` |
| Escalate | `Siren` |
| Medication | `Pill` |
| Lab result | `FlaskConical` |
| Diagnosis | `Stethoscope` |
| Procedure | `Scissors` |

---

## Page Layout Grid

```
┌────────────────────────────────────────────────────────┐
│  SIDEBAR (240px fixed)  │  MAIN CONTENT (fluid)        │
│                         │                              │
│  Logo                   │  TOP BAR (56px)              │
│  ─────────────          │  ─────────────────────────── │
│  Navigation links       │                              │
│  ─────────────          │  PAGE HEADER                 │
│                         │  (title + breadcrumb + CTA)  │
│  Patient context        │                              │
│  (when active)          │  CONTENT AREA                │
│                         │  (max-width: 1280px,         │
│  ─────────────          │   auto margin)               │
│  Settings               │                              │
└────────────────────────────────────────────────────────┘

Content area columns:
- Single column: full-width content (summary viewer, trace viewer)
- Two-column (2/3 + 1/3): primary content + sidebar panel (safety review)
- Three-column grid: dashboard widgets, analytics cards
```

---

## Animation Guidelines

Animations must serve function, not aesthetics.

| Animation | Duration | Easing | Usage |
|---|---|---|---|
| Page transition | 150ms | ease-out | Fade in content |
| Component mount | 150ms | ease-out | Slide up + fade |
| Skeleton shimmer | 1500ms | linear, loop | Loading placeholders |
| Agent step pulse | 1000ms | ease-in-out, loop | Current execution step |
| Safety flag expand | 200ms | ease-out | Expanding flag details |
| Toast notification | 300ms enter / 200ms exit | ease-out / ease-in | Status notifications |

**Never animate:** Numbers incrementing, chart bars filling — these feel gamified and reduce trust in clinical data.
