# DischargePilot AI — Agent Architecture

---

## Design Philosophy

The DischargePilot AI agent is not a pipeline. It is not a chain of prompts. It is a **goal-directed, stateful, self-correcting reasoning system.**

The agent:
- Has a **goal**: produce a complete, evidence-grounded, safety-validated discharge summary
- Maintains **state**: everything it has learned across tool executions
- Uses **tools**: discrete functions that extract, reconcile, validate, and generate
- **Re-plans**: if extraction is incomplete or conflicts are found, it revises its execution plan
- Has **termination conditions**: it only stops when the goal is met or explicitly escalated

This design mirrors how a careful, methodical clinician would synthesize a complex patient record — not by reading once and writing, but by iteratively gathering information, identifying gaps, resolving conflicts, and then generating a structured output.

---

## Agent State Machine

```
                        ┌─────────────────────────────────┐
                        │          AGENT STATE             │
                        │                                  │
   START ──────────────►│  INITIALIZING                    │
                        │  └── Load patient documents      │
                        │  └── Create initial memory       │
                        └──────────────┬──────────────────┘
                                       │
                        ┌──────────────▼──────────────────┐
                        │         PLANNING                 │
                        │  └── Claude: "Given these docs,  │
                        │      generate an extraction plan"│
                        │  └── Returns ordered tool list   │
                        └──────────────┬──────────────────┘
                                       │
                        ┌──────────────▼──────────────────┐
                        │         EXECUTING                │◄────┐
                        │  └── Pick next tool from plan    │     │
                        │  └── Run tool                    │     │
                        │  └── Store result in memory      │     │
                        │  └── Log trace                   │     │
                        └──────────────┬──────────────────┘     │
                                       │                         │
                        ┌──────────────▼──────────────────┐     │
                        │         RE-PLANNING              │     │
                        │  └── Check: gaps in extraction?  │     │
                        │  └── Check: conflicts found?     │     │
                        │  └── If yes → revise plan ───────┼─────┘
                        │  └── If no  → proceed            │
                        └──────────────┬──────────────────┘
                                       │
                        ┌──────────────▼──────────────────┐
                        │      SAFETY VALIDATING           │
                        │  └── Run all safety checks       │
                        │  └── Create safety flag records  │
                        │  └── CRITICAL flag? → ESCALATING │
                        └──────────────┬──────────────────┘
                                       │
                        ┌──────────────▼──────────────────┐
                        │         GENERATING               │
                        │  └── Build each summary section  │
                        │  └── Link evidence to text       │
                        │  └── Mark missing fields         │
                        └──────────────┬──────────────────┘
                                       │
                        ┌──────────────▼──────────────────┐
                        │         TERMINATING              │
                        │  └── All required sections done? │
                        │  └── All safety checks passed?   │
                        │  └── Create final summary record │
                        └──────────────┬──────────────────┘
                                       │
                                  COMPLETED
                            (or ESCALATED / FAILED)
```

---

## Agent Components — Detailed Design

### 1. Agent Memory

The memory is the agent's working state for a single run. It is an in-memory data structure (not persistent) that accumulates information as tools execute. At run completion, the final state is serialized into the database summary record.

```python
@dataclass
class AgentMemory:
    run_id: str
    patient_id: str

    # Document corpus
    documents: List[ProcessedDocument]

    # Extracted clinical entities
    demographics: Optional[PatientDemographics]
    diagnoses: List[Diagnosis]
    medications: List[Medication]
    procedures: List[Procedure]
    lab_results: List[LabResult]
    allergies: List[str]

    # Reconciliation and conflict state
    medication_reconciliation: Optional[MedicationReconciliation]
    conflicts: List[Conflict]
    missing_fields: List[MissingField]

    # Safety state
    safety_flags: List[SafetyFlag]
    escalations: List[EscalationRecord]

    # Generated output
    summary_sections: Dict[str, SummarySection]

    # Execution state
    current_plan: List[ToolCallSpec]
    completed_steps: List[str]
    current_step_index: int
    iteration_count: int

    # Metadata
    started_at: datetime
    last_updated_at: datetime
```

**Key Properties:**
- Memory is scoped to a single agent run — no cross-run contamination
- All extracted data retains evidence references (source doc ID, page number, excerpt)
- `completed_steps` tracks which tools have already run — prevents re-execution of redundant steps
- `iteration_count` enforces a maximum iteration limit to prevent infinite loops

---

### 2. Planner

The Planner generates the initial execution plan by analyzing the available document types.

**Input:** List of available documents with their types and page counts

**Claude API Call:**
```
System: You are a clinical documentation planning system. Given the available 
clinical documents for a patient, create an ordered extraction plan. Return 
a structured JSON list of tool calls in the optimal order for generating a 
complete discharge summary.

User: Available documents:
- Admission Note (12 pages)
- Progress Note Day 1 (4 pages)
- Progress Note Day 3 (5 pages)
- Lab Report (8 pages)
- Medication Administration Record (6 pages)

Generate the extraction plan.
```

**Output Schema:**
```python
class ExecutionPlan(BaseModel):
    steps: List[ToolCallSpec]
    reasoning: str

class ToolCallSpec(BaseModel):
    step_id: str
    tool_name: str
    priority: int
    input_sources: List[str]  # document types to use as input
    rationale: str
    required: bool
```

**Default Plan Structure** (when Claude generates):
```
1. extract_demographics        (from: Admission Note)
2. extract_diagnoses           (from: Admission Note, all Progress Notes)
3. extract_medications         (from: Admission Note, MAR)
4. extract_procedures          (from: all documents)
5. extract_labs                (from: Lab Report)
6. reconcile_medications       (from: Memory — medications list)
7. detect_conflicts            (from: Memory — all extracted entities)
8. check_completeness          (from: Memory — all sections)
9. validate_safety             (from: Memory — medications, conflicts, labs)
10. build_section × N          (one per required summary section)
11. link_evidence              (from: all sections + document corpus)
```

---

### 3. Tool Selector

The Tool Selector reads the current plan and memory state to determine which tool to execute next.

**Logic:**
```python
def select_next_tool(memory: AgentMemory) -> Optional[ToolCallSpec]:
    plan = memory.current_plan
    completed = set(memory.completed_steps)

    for step in plan:
        if step.step_id not in completed:
            # Check if dependencies are satisfied
            if all(dep in completed for dep in step.dependencies):
                return step

    return None  # Plan complete
```

**Re-planning Trigger:**
If the Tool Selector encounters a state where:
- A required section has no supporting evidence in memory
- A critical conflict was found that requires additional extraction
- Completeness check found missing fields that may be in unprocessed document sections

...it signals the Re-Planner to insert additional steps.

---

### 4. Executor

The Executor calls the selected tool, handles errors, stores the result in memory, and writes a trace record.

```python
async def execute_tool(tool_spec: ToolCallSpec, memory: AgentMemory, db: Session) -> ToolResult:
    tool = tool_registry[tool_spec.tool_name]

    # Prepare input from memory + documents
    tool_input = tool.prepare_input(tool_spec, memory)

    # Execute
    start_time = time.time()
    try:
        result = await tool.run(tool_input)
    except ToolExecutionError as e:
        result = ToolResult(success=False, error=str(e))

    latency_ms = (time.time() - start_time) * 1000

    # Update memory
    tool.update_memory(result, memory)

    # Write trace
    trace_record = AgentTrace(
        run_id=memory.run_id,
        step_id=tool_spec.step_id,
        tool_name=tool_spec.tool_name,
        input_summary=tool_input.summary(),
        output_summary=result.summary(),
        success=result.success,
        latency_ms=latency_ms,
        timestamp=datetime.utcnow()
    )
    db.add(trace_record)
    db.commit()

    # Mark completed
    memory.completed_steps.append(tool_spec.step_id)
    memory.last_updated_at = datetime.utcnow()

    return result
```

---

### 5. Re-Planner

The Re-Planner runs after each major extraction phase (after all diagnosis tools, after all medication tools, after completeness check). It evaluates the current memory state and decides whether additional steps are needed.

**Trigger Conditions:**

| Condition | Re-planning Action |
|---|---|
| Missing required field detected | Insert targeted extraction step for that field's source document type |
| Conflict between documents detected | Insert `detect_conflicts` step across specific document pairs |
| Medication in one document not in another | Insert targeted `reconcile_medications` pass |
| Safety flag requires clarification | Insert additional extraction step |
| Iteration limit approaching (N-2 steps) | Escalate all unresolved issues and begin summary generation |

**Re-Planner Logic:**
```python
def replan(memory: AgentMemory) -> List[ToolCallSpec]:
    new_steps = []

    # Check for missing critical fields
    for missing_field in memory.missing_fields:
        if missing_field.severity == "CRITICAL":
            new_steps.append(ToolCallSpec(
                tool_name="extract_from_section",
                rationale=f"Retry extraction for missing field: {missing_field.field_name}",
                input_sources=[missing_field.likely_source_doc_type]
            ))

    # Check for unresolved conflicts
    for conflict in memory.conflicts:
        if not conflict.resolution_attempted:
            new_steps.append(ToolCallSpec(
                tool_name="detect_conflicts",
                rationale=f"Deep conflict resolution for: {conflict.description}",
            ))

    return new_steps
```

---

### 6. Safety Validator

The Safety Validator runs as a separate pass after all extractions are complete and before summary generation. It is the gatekeeper between raw clinical data and the clinician's review.

**Validation Modules:**

```
SafetyValidator
├── FabricationGuard
│   └── Cross-checks every extracted statement against source chunks
│   └── Blocks any statement that cannot be traced to a source
│
├── ConflictChecker
│   └── Compares all diagnoses across all documents — flags inconsistencies
│   └── Compares all medications across all documents — flags discrepancies
│   └── Checks allergy list against prescribed medications — CRITICAL flag if conflict
│
├── MedicationSafetyChecker
│   └── Checks for known high-risk drug combinations (rule-based)
│   └── Checks for dose outside normal range markers
│   └── Checks for medications without clear indication in notes
│
├── CompletenessChecker
│   └── Verifies all required discharge summary sections have content
│   └── Marks missing fields as [NOT DOCUMENTED IN SOURCE]
│
└── PendingResultsGuard
    └── Scans lab reports for pending/awaited markers
    └── Ensures these remain flagged as pending in the summary
```

---

### 7. Summary Generator

The Summary Generator builds each section of the discharge summary using the data in agent memory and the Claude API.

**Section Generation Pattern:**
```python
async def build_section(section_type: SectionType, memory: AgentMemory) -> SummarySection:
    # Gather relevant evidence from memory
    evidence = gather_evidence_for_section(section_type, memory)

    # Build grounded prompt — only use what's in memory
    prompt = build_section_prompt(section_type, evidence)

    # Call Claude with structured output schema
    raw_output = await claude_client.generate_structured(
        prompt=prompt,
        output_schema=SectionOutputSchema
    )

    # Link evidence references
    linked_text = link_evidence(raw_output.content, evidence)

    return SummarySection(
        section_type=section_type,
        content=linked_text.content,
        evidence_refs=linked_text.refs,
        confidence=raw_output.confidence,
        missing_info=raw_output.missing_info,
        needs_review=raw_output.needs_review
    )
```

**Anti-Hallucination Enforcement in Prompts:**
Every section-building prompt includes:
```
CRITICAL INSTRUCTIONS:
1. Use ONLY information explicitly present in the provided evidence text below.
2. If a required field is not found in the evidence, write: [NOT DOCUMENTED IN SOURCE DOCUMENTS]
3. Do NOT infer, assume, or add clinical information not explicitly stated.
4. If you are uncertain about any statement, mark it with [NEEDS CLINICIAN REVIEW]
5. Every medication name, dose, and frequency must match exactly as written in source text.
```

---

### 8. Termination Logic

The agent terminates when one of three conditions is met:

**Condition 1 — SUCCESS:**
- All required summary sections have been built
- All safety checks have been run
- Summary record created with status `PENDING_REVIEW`

**Condition 2 — ESCALATED:**
- A CRITICAL safety flag was found (e.g., allergy-drug conflict)
- Agent creates an escalation record and stops
- Summary is marked `ESCALATED` — clinician must resolve before summary can proceed
- Notification sent to clinician

**Condition 3 — MAX ITERATIONS REACHED:**
- Agent has run more than the configured maximum iterations (default: 25)
- All incomplete sections are marked `[EXTRACTION INCOMPLETE - MANUAL REVIEW REQUIRED]`
- Summary is created with status `INCOMPLETE`
- Full trace is available for clinician review

---

## Information Flow Diagram

```
DOCUMENTS
    │
    ▼
[PDF Extractor] ──────────────────► Document Chunks (page-indexed)
                                          │
                                          ▼
                                    [Agent Memory]
                                    ┌────────────┐
  [Planner] ──────────────────────► │  .plan     │
                                    │  .docs     │
  [extract_demographics] ─────────► │  .demographics│
  [extract_diagnoses]    ─────────► │  .diagnoses│
  [extract_medications]  ─────────► │  .medications│
  [extract_procedures]   ─────────► │  .procedures│
  [extract_labs]         ─────────► │  .labs     │
  [reconcile_medications]─────────► │  .med_rec  │
  [detect_conflicts]     ─────────► │  .conflicts│
  [check_completeness]   ─────────► │  .missing  │
  [validate_safety]      ─────────► │  .flags    │
  [build_section] × N    ─────────► │  .sections │
  [link_evidence]        ─────────► │  .sections │
                                    └────────────┘
                                          │
                                          ▼
                                [DischargeSummary Record]
                                ├── sections[] (with evidence)
                                ├── safety_flags[]
                                ├── conflicts[]
                                ├── missing_fields[]
                                └── agent_run_id (→ full trace)
```

---

## Agent Configuration

```python
class AgentConfig(BaseModel):
    max_iterations: int = 25
    max_replanning_cycles: int = 3
    claude_model: str = "claude-sonnet-4-6"
    extraction_temperature: float = 0.0   # Deterministic extraction
    generation_temperature: float = 0.2  # Slight variation for natural language
    timeout_seconds: int = 180
    enable_safety_layer: bool = True
    require_evidence_for_all_statements: bool = True
    missing_field_placeholder: str = "[NOT DOCUMENTED IN SOURCE DOCUMENTS]"
    uncertainty_placeholder: str = "[NEEDS CLINICIAN REVIEW]"
```
