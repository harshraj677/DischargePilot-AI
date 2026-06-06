# Interview Preparation — DischargePilot AI

Concise talking points for AI Engineer interviews and technical presentations.

---

## Elevator Pitch (30 seconds)

> "DischargePilot AI is an agentic AI system that automates hospital discharge summaries from unstructured clinical documents. It uses Claude claude-sonnet-4-6 with 11 specialized clinical extraction tools, a 5-layer safety validation engine that blocks generation when clinical conflicts are detected, and a reinforcement learning system that improves from physician feedback. The key differentiator is clinical safety — the system will never fabricate information and will escalate critical conflicts to a physician rather than silently generating an unsafe summary."

---

## Architecture Explanation (2 minutes)

> "The system has four main layers:
>
> **Layer 1 — Document Processing**: PyMuPDF extracts text from PDFs with page indexing. A document classifier identifies the type. A chunker splits text for context window management.
>
> **Layer 2 — Agent Engine**: This is the core. The Planner generates a dependency-ordered task graph — diagnoses must be extracted before conflicts can be detected, for example. The ToolSelector picks the highest-priority ready task. The Executor runs the tool via Claude. The Decision Engine evaluates the result and can trigger replanning if it finds something critical.
>
> **Layer 3 — Safety Validation**: Five independent validators run in sequence. Evidence Validator rejects any fact without source document grounding. Medication Validator cross-references discharge prescriptions against the allergy list. Completeness Validator checks that all required clinical fields are present. If any critical issue is found, the status is BLOCKED and summary generation cannot proceed.
>
> **Layer 4 — Learning System**: After each summary is generated, an AI doctor reviewer simulates physician editing. We compute normalized edit distance per section, generate a reward score, and store correction patterns in a Correction Memory. A UCB strategy engine selects the best prompt variant for the next generation."

---

## Technical Depth Questions

### "Why use an agent loop instead of a single Claude call?"

> "A single Claude call has a limited context window and can't reason iteratively. The agent loop lets us: 1) Process documents incrementally — each tool only receives relevant chunks, 2) Detect conflicts that only become apparent after multiple extractions, 3) Replan dynamically when critical findings emerge, 4) Maintain a structured state machine that we can observe and debug. The execution trace logs every reasoning step, which is essential for clinical explainability."

### "How do you prevent hallucination?"

> "Three mechanisms: First, every fact is an `EvidencedFact` object that requires a non-empty evidence string — the actual text excerpt from the source document. The Evidence Validator rejects any fact with empty evidence. Second, confidence scores below 0.70 trigger review flags. Third, the safety engine's BLOCKED status means if critical information is missing or conflicting, the system refuses to generate a summary at all — it explicitly blocks rather than fabricates."

### "How does the learning system work?"

> "It's a simplified RLHF loop. After a summary is generated, the AI doctor reviewer — simulating a physician — edits it. We compute normalized Levenshtein edit distance per section, which gives us a measure of how much was changed. The reward formula is: 0.5 × (1 - edit_distance) + 0.3 × section_accuracy + 0.2 × (1 - review_burden). Correction patterns are stored in a memory keyed by section and frequency. High-frequency patterns become prompt hints for the next generation. A UCB algorithm selects which of three prompt strategy variants to use based on cumulative reward."

### "What's the safety score formula?"

> "safety_score = max(0.0, 1.0 - (critical_count × 0.30) - (high_count × 0.10)). Each critical finding reduces the score by 30 percentage points, each high finding by 10. If there's any critical finding — allergy conflict, empty evidence, missing discharge medications — the overall status is BLOCKED and generation cannot proceed. The floor is 0.0. This mirrors how clinical risk scoring works in practice."

### "Why did you choose SQLite?"

> "For a demonstration system with one or two concurrent users, SQLite is appropriate and zero-config. SQLAlchemy abstracts the ORM layer, so migrating to PostgreSQL for production is a single config change — just update the DATABASE_URL. Alembic is already in the dependency stack for migration management."

### "How do you handle the Claude API rate limits?"

> "Currently, tool calls are sequential — one Claude call per tool execution. This is the simplest architecture but doesn't scale well. In production, you'd add: 1) A request queue (Celery + Redis) with rate limiting, 2) Parallel execution for independent tools — diagnoses, medications, and allergies can run simultaneously since they have no dependencies on each other, 3) Caching for repeated patterns. The current architecture is intentionally simple for clarity."

### "What would you change for production?"

> "Six things: 1) PostgreSQL instead of SQLite with proper connection pooling, 2) Parallel tool execution for independent tasks — could cut agent runtime by 40%, 3) A dedicated drug interaction database (DrugBank/RxNorm) instead of relying on Claude's knowledge, 4) FHIR R4 integration to pull data directly from hospital EHR systems, 5) Role-based access control — physicians and nurses have different permissions, 6) HIPAA-compliant audit logging with immutable append-only storage."

---

## Clinical Safety Talking Points

### What makes this clinically safe?

1. **Zero fabrication tolerance** — every fact requires source document evidence
2. **Independent validation layers** — 5 validators that can't be bypassed
3. **Explicit blocking** — BLOCKED status prevents unsafe summary generation entirely
4. **Escalation mechanism** — critical conflicts route to physician, not auto-resolved
5. **Full audit trail** — every extraction traceable to source document and page number

### What safety tests did you run?

> "Six clinical scenarios: normal patient, missing data, conflicting diagnoses, pending lab results, medication-allergy conflict, and drug-drug interaction. The most critical test — SCN-005 — puts a patient with a documented life-threatening Penicillin allergy and a discharge prescription for Amoxicillin (a penicillin-class drug). The system correctly detected this, set status to BLOCKED, triggered escalation, and refused to generate a summary."

---

## Learning System Talking Points

### How is this different from just prompting Claude better?

> "Prompting better is a one-time improvement. RLHF is a feedback loop — the system gets better with every patient. The correction memory stores what specific physicians are correcting and how often. High-frequency patterns become prompt hints. Over 10 sessions in our evaluation, edit distance dropped 75% and reward scores improved 49%. The system adapts to the style preferences of the clinical context it's deployed in."

---

## Project Scale Talking Points

- **114 Python files** across 15 backend subsystems
- **28+ TypeScript files** for the frontend with 8 clinical pages
- **11 specialized clinical tools** with dependency resolution
- **5 independent safety validators** in a defense-in-depth pattern
- **6 clinical evaluation scenarios** with expected outputs
- **79 traced requirements** — 100% implemented
- **Built in 10 phases** following a formal architecture blueprint

---

## Key Differentiators

| Feature | DischargePilot AI | Typical LLM Demo |
|---------|-------------------|------------------|
| Fabrication prevention | Explicit blocking | Prompting only |
| Safety validation | 5 independent validators | None |
| Conflict detection | Real-time with escalation | None |
| Learning system | RLHF + correction memory | One-shot prompt |
| Explainability | Full execution trace | Black box |
| Clinical scenarios | 6 tested scenarios | Ad-hoc testing |
| Requirement traceability | 79 requirements tracked | None |
