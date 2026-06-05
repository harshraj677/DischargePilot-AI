# DischargePilot AI — Healthcare UX Strategy

---

## Design Philosophy

DischargePilot AI is clinical infrastructure. It is used by physicians under time pressure, in high-stakes environments, where a misread UI element is not inconvenient — it is potentially dangerous.

The UX must reflect this reality.

**Three principles drive every design decision:**

### 1. Trust Through Transparency
The system must never feel like a black box. Clinicians need to see exactly where every piece of information came from, what the system is uncertain about, and what it could not find. Trust is earned through visibility, not claims.

**Applied:** Every summary section shows its evidence source. Every uncertainty is surfaced, never hidden. Every conflict is surfaced, never resolved silently.

### 2. Clinician Control at Every Step
The system assists; the clinician decides. The UI must never make it feel like the system has finalized anything without human approval. The clinician must feel that they are reviewing the agent's work, not rubber-stamping it.

**Applied:** Summaries are presented as drafts. Every section has an edit button. Approval is a deliberate action, not the default. Critical safety flags cannot be bypassed without explicit resolution.

### 3. Information Hierarchy Over Aesthetics
Healthcare professionals are trained to read structured information quickly. Dense, well-organized clinical information is easier to read than sparse, visually "clean" layouts that sacrifice information density for aesthetics.

**Applied:** The UI is information-rich but organized. Consistent section headers. Color used only for clinical meaning (severity, status), never for decoration.

---

## Target User Profiles

### Profile A — Hospitalist Physician
- **Context:** Rounds complete, 3 patients to discharge, 45 minutes available
- **Device:** Hospital workstation (1440px wide), sometimes tablet
- **Needs:** Fast review, no unnecessary clicks, critical flags visible immediately
- **Fears:** Missing a safety issue because the UI buried it

**Design implication:** Safety flags and unresolved conflicts must be the first thing visible on the review screen. Summary content is secondary to safety review completion.

### Profile B — Resident Physician
- **Context:** Learning clinical documentation; less experience with medication reconciliation
- **Device:** Shared hospital workstation
- **Needs:** Guidance on what to check; clear indicators of what the AI flagged vs. confirmed
- **Fears:** Submitting an incorrect summary

**Design implication:** Confidence indicators on every section. Tooltips explaining what "NEEDS REVIEW" means. Help text inline rather than buried in docs.

### Profile C — Nurse Case Manager
- **Context:** Coordinating discharge logistics, patient education
- **Device:** Workstation, sometimes mobile
- **Needs:** Medication list, follow-up instructions, discharge condition
- **Fears:** Patient leaving without complete discharge instructions

**Design implication:** Summary export must be clean and printable. Medication list section must be prominent and clearly formatted.

---

## What to Avoid

### Visual Anti-Patterns for Healthcare

| Anti-Pattern | Why It Fails in Healthcare |
|---|---|
| Neon or saturated colors | Reduces trust; looks consumer, not clinical |
| Heavy animations on data elements | Distracts from critical information |
| Gamification elements (streaks, confetti) | Trivializes serious clinical decisions |
| Auto-dismissing toasts for safety alerts | Clinicians may miss critical information |
| Ambiguous icon-only buttons | Dangerous in a clinical context — labels required |
| Dark mode by default | Clinical environments use bright light; dark mode can reduce readability on clinical monitors |
| Modal-heavy workflows | Forces sequential interaction; clinicians need to cross-reference multiple pieces of information simultaneously |

### Content Anti-Patterns

| Anti-Pattern | Why It Fails |
|---|---|
| Presenting AI output without uncertainty indicators | Creates false confidence |
| "Approving" without showing unresolved flags | Creates liability; violates clinical safety |
| Collapsing critical safety information | Safety content must be expanded by default |
| Truncating evidence excerpts with "..." | Clinicians need to see the full source text |
| Generic error messages | "Something went wrong" is unacceptable in a clinical tool — always specify what failed and what to do |

---

## Information Architecture

```
DischargePilot AI
│
├── Dashboard
│   ├── Patient Queue (today's discharges)
│   ├── Summary Status Tracker
│   ├── Safety Alert Feed
│   └── Quick Metrics
│
├── Patients
│   ├── Patient List
│   └── Patient Detail
│       └── Upload Center
│
├── Agent Execution
│   ├── Live Execution View (during run)
│   └── Trace Viewer (post-run audit)
│
├── Clinical Review
│   ├── Safety Review Center (pre-summary review)
│   └── Summary Viewer (full summary + evidence)
│
└── Analytics
    ├── Performance Overview
    ├── Safety Metrics
    └── Learning Feedback
```

**Navigation principle:** The workflow is linear. Dashboard → Upload → Execute → Safety Review → Summary → Approve. The navigation design guides clinicians through this flow without requiring them to know where to go next.

---

## Interaction Model

### Progressive Disclosure
- Show critical safety information first, always expanded
- Show summary sections collapsed by default (section header + first line visible), expandable
- Show evidence references as chips that expand to full excerpts on hover/click
- Show agent trace as collapsed timeline that expands to full tool input/output on click

### State Communication
Every element that represents system state must communicate that state visibly:

| State | Visual Treatment |
|---|---|
| Processing / Loading | Subtle pulse animation on the affected component; never full-page spinner |
| Agent executing | Step-by-step timeline with current step highlighted and animated |
| Needs clinician action | Amber background tint on the affected section |
| Critical alert | Red left border + icon on the component |
| Approved / Complete | Green checkmark badge |
| Not documented in source | Gray italic text with `[NOT DOCUMENTED]` prefix |
| Needs review | Amber dashed underline on the specific text |

### Error Handling
- System errors: Full-width error banner with specific description + recovery action
- Validation errors: Inline under the specific field
- Agent errors: Dedicated error state in execution timeline with trace link for debugging
- Upload errors: Per-file error with specific reason (too large, not PDF, extraction failed)

---

## Accessibility Requirements

- **WCAG 2.1 AA** compliance minimum
- Color cannot be the only indicator of clinical severity — always pair color with icon + text label
- All interactive elements have keyboard navigation support
- Font sizes: minimum 14px for body text, 12px for labels — never smaller
- Contrast ratio: minimum 4.5:1 for normal text, 3:1 for large text
- Focus indicators visible on all interactive elements
- Screen reader labels on all icon buttons
- Loading states announced to screen readers via `aria-live`

---

## Clinical Clarity Standards

### Medication Display
Medications are always displayed in the standardized clinical format:
```
[Drug Name] [Dose] [Route] [Frequency]
e.g.: Metformin 1000mg PO BID
```
Never abbreviate route/frequency without a tooltip. US standard abbreviations only.

### Lab Values
Always display with unit and reference range when available:
```
HbA1c: 9.2% (Reference: <5.7%)  ↑ HIGH
```

### Dates
Always display in unambiguous format: `May 28, 2025` not `05/28/25`

### Diagnoses
Always display full diagnosis name first; ICD hint in parentheses if available:
```
Type 2 Diabetes Mellitus (E11.65)
```

### Evidence Citations
Never truncate source excerpts below 100 characters. Always show:
- Source document name and type
- Page number
- The exact excerpt

---

## Performance UX

Clinical tools must be fast. Performance targets:

| Action | Target |
|---|---|
| Page navigation | < 200ms perceived |
| Patient search | < 300ms results |
| Document upload feedback | < 100ms after drop |
| Agent status polling | Every 2 seconds during execution |
| Summary load | < 500ms |
| Safety flags load | < 300ms |
| PDF export generation | < 3 seconds with progress indicator |
