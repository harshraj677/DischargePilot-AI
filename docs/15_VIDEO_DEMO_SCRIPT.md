# Video Demo Script — DischargePilot AI

**Target Length:** 4–5 minutes
**Format:** Screen recording with narration
**Audience:** AI Engineer hiring panel / Healthcare AI evaluators

---

## Pre-Recording Setup

- Backend running at `localhost:8000`
- Frontend running at `localhost:3000`
- Browser at 1920×1080, zoom 100%
- Dark mode enabled for professional appearance
- Sample PDF documents ready to upload
- Terminal visible for backend output (optional split-screen)

---

## OPENING (0:00–0:20)

**[Show: Landing page / Dashboard]**

> "This is DischargePilot AI — an agentic AI system that generates evidence-grounded hospital discharge summaries from unstructured clinical documents.
>
> The system uses Claude claude-sonnet-4-6 as its reasoning engine, with 11 specialized clinical extraction tools, a 5-layer safety validation system, and a reinforcement learning system that improves from physician feedback.
>
> Let me show you how it works."

---

## DEMO 1: Normal Patient — Full Discharge Workflow (0:20–1:30)

**[Navigate to: Patients → New Patient]**

> "First, I'll create a new patient. Margaret Chen, 67-year-old female, admitted to Internal Medicine."

**[Fill in patient form → Save]**

> "Now I'll upload her clinical documents — an admission note and lab report."

**[Navigate to Upload → Drag in PDF files]**

> "The system automatically classifies each document — this is the admission note, and this is the lab report. Document classification happens using keyword pattern matching."

**[Click "Run Agent"]**

> "Now I'll start the agent. Watch the execution trace on the right — the planner first generates a task graph based on what document types are available."

**[Show the trace building in real-time]**

> "The agent runs 11 specialized tools in dependency order — first diagnoses, then medications, allergies, labs... and finally conflict detection, which depends on all the earlier results.
>
> Every tool call is logged here in the execution trace with the exact text excerpts used as evidence."

**[Trace completes → Navigate to Safety Report]**

> "Now the safety engine validates everything. Five independent validators run — Evidence, Conflict, Medication, Completeness, and Pending Results.
>
> For Margaret, everything checks out — status is APPROVED with a safety score of 92%."

**[Navigate to Summary]**

> "And here's the generated discharge summary — every section grounded in source documents, with page references for every extracted fact."

---

## DEMO 2: Missing Data Detection (1:30–2:15)

**[Create new patient: "James Okonkwo" → Upload admission note only]**

> "Now let's test a more challenging scenario — a patient whose discharge medications weren't documented."

**[Run Agent → Show trace]**

> "The agent runs normally, but when it tries to extract discharge medications, it finds nothing. It marks this as missing information."

**[Navigate to Safety Report]**

> "The Completeness Validator detects missing discharge medications and missing hospital course notes.
>
> Status: **BLOCKED**. The system refuses to generate a summary rather than fabricating content."

**[Show blocking issues panel]**

> "This is the key clinical safety guarantee — DischargePilot AI will never invent medication information. It explicitly blocks generation and tells the clinician exactly what's missing."

---

## DEMO 3: Medication-Allergy Conflict (2:15–3:00)

**[Create new patient: "Elena Rodriguez" → Upload documents with Penicillin allergy + Amoxicillin prescription]**

> "This is the most critical safety test. Elena has a documented life-threatening Penicillin allergy — she was intubated in 2019 — but the discharge prescription contains Amoxicillin, which is a penicillin-class antibiotic."

**[Run Agent → Safety Report]**

> "The agent detects both the allergy and the medication. The Conflict Detection tool flags them. The Medication Validator cross-references them.
>
> Safety status: **BLOCKED** — critical allergy conflict detected."

**[Show blocking issue detail]**

> "The system surfaces exactly what the problem is: 'Amoxicillin prescribed despite documented life-threatening Penicillin allergy.' And it escalates to the physician for immediate review.
>
> This is how clinical AI should work — catching errors before they reach the patient."

---

## DEMO 4: Drug Interaction Detection (3:00–3:30)

**[Load or show pre-run SCN-006 results — Harold Fitzgerald — Warfarin + Fluconazole]**

> "Here's a subtler case — Harold is on Warfarin for atrial fibrillation, and he's been prescribed Fluconazole for oral candidiasis.
>
> Fluconazole inhibits CYP2C9, the enzyme that metabolizes Warfarin. This is a well-established serious drug interaction — it can cause supratherapeutic INR and major bleeding."

**[Show Drug Interaction Tool result in trace]**

> "The drug interaction checker detects this and classifies it as 'serious'. But unlike the allergy conflict — which is absolute — this interaction is manageable.
>
> Status: **REVIEW_REQUIRED**. The summary is generated, but with a review flag that includes the mechanism, clinical consequence, and management recommendations — INR monitoring twice weekly."

---

## DEMO 5: Learning System (3:30–4:20)

**[Navigate to Learning Dashboard]**

> "Finally, the learning system. DischargePilot AI uses RLHF — reinforcement learning from human feedback — to improve over time."

**[Navigate to a summary → Doctor Review panel]**

> "The AI doctor reviewer simulates a physician editing the summary. For example, 'DM2' gets expanded to 'Type 2 Diabetes Mellitus'. 'BID' becomes 'twice daily'."

**[Submit review → Show reward score]**

> "Each review session generates a reward score — based on how much the physician had to change.
>
> The system stores these corrections in its Correction Memory and uses them as prompt hints for the next generation."

**[Navigate to Learning Analytics]**

> "Over 10 sessions, the average reward score improves from 0.55 to 0.82. Edit distance drops by 75%. The system is getting measurably better at generating summaries that physicians don't need to correct."

---

## CLOSING (4:20–4:45)

**[Show Architecture Diagram or return to Dashboard]**

> "DischargePilot AI demonstrates several important properties for production healthcare AI:
>
> **First, clinical safety** — multiple independent validation layers, zero fabrication tolerance, and explicit blocking when information is missing or conflicting.
>
> **Second, explainability** — every fact has a source document, page number, and confidence score. Every agent decision is recorded in the execution trace.
>
> **Third, learning** — the system improves from physician feedback using a structured RLHF approach.
>
> The full source code, evaluation framework, and documentation are available in the repository. Thank you."

---

## Recording Tips

1. **Slow down** at the Safety Report — this is the most impressive part
2. **Zoom in** on the blocking issue detail and conflict description
3. **Highlight** the execution trace — it shows the agent reasoning step by step
4. **Use a real patient PDF** if available, or generate a sample using the included script
5. **Keep narration** even-paced — don't rush through the safety demos

## Demo Order Priority

If time is limited, prioritize in this order:
1. Normal workflow (Demo 1) — shows end-to-end capability
2. Allergy conflict (Demo 3) — most impressive safety demo
3. Learning system (Demo 5) — differentiates from basic AI tools
4. Drug interaction (Demo 4) — shows nuanced clinical reasoning
5. Missing data (Demo 2) — demonstrates completeness validation
