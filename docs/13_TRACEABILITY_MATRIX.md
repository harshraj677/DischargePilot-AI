# Requirement Traceability Matrix — DischargePilot AI

Maps every system requirement to its implementation location in the codebase.

---

## Part 1: Core Functional Requirements

| Requirement ID | Requirement | Implementation | File(s) |
|---------------|-------------|----------------|---------|
| REQ-F01 | Accept PDF clinical documents as input | `upload_service.py`, `pdf_extractor.py` | `backend/app/services/upload_service.py`, `backend/app/processing/pdf_extractor.py` |
| REQ-F02 | Extract text from multi-page PDFs with page indexing | `pdf_extractor.py` | `backend/app/processing/pdf_extractor.py` |
| REQ-F03 | Classify document type (admission note, lab report, MAR, etc.) | `document_classifier.py` | `backend/app/processing/document_classifier.py` |
| REQ-F04 | Chunk documents for context-window management | `chunker.py` | `backend/app/processing/chunker.py` |
| REQ-F05 | Support multiple document types per patient | `document_repo.py`, `models.py` | `backend/app/db/repositories/document_repo.py` |
| REQ-F06 | Extract clinical diagnoses with ICD codes | `diagnosis.py` | `backend/app/agent/tools/diagnosis.py` |
| REQ-F07 | Extract admission and discharge medications | `medication.py` | `backend/app/agent/tools/medication.py` |
| REQ-F08 | Extract allergies with severity classification | `allergy.py` | `backend/app/agent/tools/allergy.py` |
| REQ-F09 | Extract lab results with critical value flagging | `lab.py` | `backend/app/agent/tools/lab.py` |
| REQ-F10 | Extract procedures performed during admission | `procedure.py` | `backend/app/agent/tools/procedure.py` |
| REQ-F11 | Detect clinical conflicts (diagnosis, medication, allergy) | `conflict_detection.py` | `backend/app/agent/tools/conflict_detection.py` |
| REQ-F12 | Check drug-drug interactions | `drug_interaction.py` | `backend/app/agent/tools/drug_interaction.py` |
| REQ-F13 | Perform medication reconciliation (admission vs discharge) | `medication_reconciliation.py` | `backend/app/agent/tools/medication_reconciliation.py` |
| REQ-F14 | Detect pending lab results and studies | `pending_result.py` | `backend/app/agent/tools/pending_result.py` |
| REQ-F15 | Evaluate need for physician escalation | `escalation.py` | `backend/app/agent/tools/escalation.py` |
| REQ-F16 | Generate structured discharge summary | `generator.py`, `formatter.py` | `backend/app/summary/generator.py`, `backend/app/summary/formatter.py` |
| REQ-F17 | Store patient data persistently | `patient_repo.py`, `models.py` | `backend/app/db/repositories/patient_repo.py` |
| REQ-F18 | Support REST API for all operations | `router.py`, `api/*.py` | `backend/app/api/` |

---

## Part 2: Clinical Safety Requirements

| Requirement ID | Requirement | Implementation | File(s) |
|---------------|-------------|----------------|---------|
| REQ-S01 | **No Fabrication** — Every fact must have source document evidence | `EvidenceValidator` | `backend/app/safety/validators/evidence.py` |
| REQ-S02 | **Confidence Threshold** — Facts below 0.70 confidence flagged | `EvidenceValidator` | `backend/app/safety/validators/evidence.py` |
| REQ-S03 | **Allergy-Medication Check** — Discharge meds cross-referenced with allergies | `MedicationValidator` | `backend/app/safety/validators/medication.py` |
| REQ-S04 | **High-Risk Medication Dose** — Warfarin, insulin, etc. must have dose | `MedicationValidator` | `backend/app/safety/validators/medication.py` |
| REQ-S05 | **Conflict Detection** — Unresolved conflicts block generation | `ConflictValidator` | `backend/app/safety/validators/conflict.py` |
| REQ-S06 | **Completeness Check** — Required fields must be present | `CompletenessValidator` | `backend/app/safety/validators/completeness.py` |
| REQ-S07 | **Pending Results Flagged** — All pending results surfaced in summary | `PendingResultValidator` | `backend/app/safety/validators/pending.py` |
| REQ-S08 | **Critical Lab Flagging** — Critical lab values require review flag | `PendingResultValidator` | `backend/app/safety/validators/pending.py` |
| REQ-S09 | **Safety Score Formula** — score = max(0, 1 - critical×0.3 - high×0.1) | `SafetyValidationEngine` | `backend/app/safety/engine.py` |
| REQ-S10 | **BLOCKED status** — Critical findings prevent summary generation | `SafetyValidationEngine` | `backend/app/safety/engine.py` |
| REQ-S11 | **REVIEW_REQUIRED status** — High findings allow generation with flags | `SafetyValidationEngine` | `backend/app/safety/engine.py` |
| REQ-S12 | **Review Flags** — Generated for medication changes, critical conditions | `ReviewFlagGenerator` | `backend/app/safety/review_flags.py` |
| REQ-S13 | **Escalation** — Critical unresolved conflicts trigger physician alert | `escalation.py`, `DecisionEngine` | `backend/app/agent/tools/escalation.py` |

---

## Part 3: Agent Architecture Requirements

| Requirement ID | Requirement | Implementation | File(s) |
|---------------|-------------|----------------|---------|
| REQ-A01 | **Planning** — Generate ordered task graph from document types | `AgentPlanner` | `backend/app/agent/planner.py` |
| REQ-A02 | **Tool Registry** — Centralized tool registration and retrieval | `ToolRegistry` | `backend/app/agent/tool_registry.py` |
| REQ-A03 | **Tool Selector** — Pick highest-priority ready task | `ToolSelector` | `backend/app/agent/tool_selector.py` |
| REQ-A04 | **Dependency Resolution** — Tasks only run when dependencies complete | `AgentState.is_task_ready()`, `ToolSelector` | `backend/app/agent/models.py` |
| REQ-A05 | **Decision Engine** — Evaluate result and decide next action | `DecisionEngine` | `backend/app/agent/decision_engine.py` |
| REQ-A06 | **Replanning** — Critical findings trigger plan revision | `DecisionEngine`, `AgentLoop` | `backend/app/agent/loop.py` |
| REQ-A07 | **Termination Controller** — Stop on completion or iteration limit | `TerminationController` | `backend/app/agent/terminator.py` |
| REQ-A08 | **Execution Trace** — Full step-by-step trace recorded | `TraceGenerator` | `backend/app/agent/tracer.py` |
| REQ-A09 | **Agent Memory** — In-memory state across iterations | `AgentMemory` | `backend/app/agent/memory.py` |
| REQ-A10 | **Max Iterations** — Agent bounded to 15 iterations maximum | `AgentState.max_iterations` | `backend/app/agent/models.py` |

---

## Part 4: Knowledge Repository Requirements

| Requirement ID | Requirement | Implementation | File(s) |
|---------------|-------------|----------------|---------|
| REQ-K01 | **Structured Knowledge Storage** — Typed fact storage per patient | `KnowledgeRepository` | `backend/app/knowledge/repository.py` |
| REQ-K02 | **Evidence-Grounded Facts** — Every fact carries source + page + confidence | `EvidencedFact` | `backend/app/knowledge/models.py` |
| REQ-K03 | **Completeness Score** — 0.0–1.0 score for knowledge coverage | `KnowledgeRepository.completeness_score()` | `backend/app/knowledge/repository.py` |
| REQ-K04 | **Source Search** — Find facts by source document | `search_by_source()` | `backend/app/knowledge/repository.py` |
| REQ-K05 | **Page Search** — Find facts by page number | `search_by_page()` | `backend/app/knowledge/repository.py` |
| REQ-K06 | **Missing Information Tracking** — Mark fields as known-missing | `mark_missing()` | `backend/app/knowledge/repository.py` |
| REQ-K07 | **Agent Context Export** — KB → text for Claude prompt context | `to_agent_context()` | `backend/app/knowledge/repository.py` |

---

## Part 5: Learning System Requirements (RLHF)

| Requirement ID | Requirement | Implementation | File(s) |
|---------------|-------------|----------------|---------|
| REQ-L01 | **Edit Distance Computation** — Normalized Levenshtein per section | `EditPolicy` | `backend/app/learning/edit_policy.py` |
| REQ-L02 | **Reward Score** — Composite score from edits, completeness, burden | `RewardCalculator` | `backend/app/learning/reward.py` |
| REQ-L03 | **Correction Memory** — Store frequent edit patterns | `CorrectionMemory` | `backend/app/learning/memory.py` |
| REQ-L04 | **Prompt Hints** — Top patterns injected into future prompts | `CorrectionMemory.build_hint_string()` | `backend/app/learning/memory.py` |
| REQ-L05 | **Strategy Engine** — UCB algorithm for strategy selection | `StrategyEngine` | `backend/app/learning/strategy.py` |
| REQ-L06 | **Doctor Review Simulation** — AI reviewer simulates physician | `DoctorReviewer` | `backend/app/learning/reviewer.py` |
| REQ-L07 | **Learning Sessions** — Each review creates a learning record | `LearningSession` | `backend/app/learning/models.py` |
| REQ-L08 | **Improvement Tracking** — Reward trend tracked over sessions | `LearningMetrics` | `backend/app/learning/models.py` |

---

## Part 6: Observability Requirements

| Requirement ID | Requirement | Implementation | File(s) |
|---------------|-------------|----------------|---------|
| REQ-O01 | **Structured Logging** — JSON-structured logs with context | `get_logger()`, `loguru` | `backend/app/utils/logging.py` |
| REQ-O02 | **Audit Trail** — Immutable audit log for all clinical decisions | `AuditLogger` | `backend/app/utils/logging.py` |
| REQ-O03 | **Metrics Collection** — Token usage, timing, tool call counts | `MetricsCollector` | `backend/app/observability/collector.py` |
| REQ-O04 | **Execution Trace Export** — Full trace viewable in UI | `TraceGenerator`, `agent.py` API | `backend/app/agent/tracer.py` |
| REQ-O05 | **Safety Audit** — Safety validation events logged with evidence | `AuditLogger` in `engine.py` | `backend/app/safety/engine.py` |

---

## Part 7: Frontend Requirements

| Requirement ID | Requirement | Implementation | File(s) |
|---------------|-------------|----------------|---------|
| REQ-UI01 | **Patient Management** — Create, view, list patients | `patients/page.tsx`, `patients/[id]/page.tsx` | `frontend/src/app/patients/` |
| REQ-UI02 | **Document Upload** — Drag-and-drop PDF upload with type selection | `upload/page.tsx`, `DropZone.tsx` | `frontend/src/app/patients/[id]/upload/` |
| REQ-UI03 | **Agent Execution** — Start agent run, view progress | `agent/page.tsx` | `frontend/src/app/patients/[id]/agent/` |
| REQ-UI04 | **Execution Trace Viewer** — Step-by-step agent trace | `trace/page.tsx` | `frontend/src/app/patients/[id]/trace/` |
| REQ-UI05 | **Safety Report** — View validation results and flags | `safety/page.tsx` | `frontend/src/app/patients/[id]/safety/` |
| REQ-UI06 | **Summary Viewer** — Read generated discharge summary | `summary/page.tsx` | `frontend/src/app/patients/[id]/summary/` |
| REQ-UI07 | **Analytics Dashboard** — System-wide metrics and charts | `analytics/page.tsx` | `frontend/src/app/analytics/` |
| REQ-UI08 | **Learning Dashboard** — RLHF metrics and improvement charts | `learning/page.tsx` | `frontend/src/app/learning/` |

---

## Part 8: Testing Requirements

| Requirement ID | Requirement | Implementation | Coverage |
|---------------|-------------|----------------|---------|
| REQ-T01 | Unit tests for PDF processing | `test_pdf_extractor.py`, `test_chunker.py` | Processing layer |
| REQ-T02 | Unit tests for document classification | `test_classifier.py` | Classification |
| REQ-T03 | Unit tests for knowledge repository | `test_agent_loop.py` (KnowledgeRepository section) | Knowledge layer |
| REQ-T04 | Unit tests for agent components | `test_agent_loop.py`, `test_tools.py` | Agent engine |
| REQ-T05 | Unit tests for all safety validators | `test_safety_engine.py` | Safety layer |
| REQ-T06 | Unit tests for summary generation | `test_summary_generator.py` | Summary layer |
| REQ-T07 | Unit tests for learning system | `test_learning_system.py` | RLHF system |
| REQ-T08 | Integration test — full discharge workflow | `test_full_workflow.py` | End-to-end |
| REQ-T09 | Clinical scenario evaluation | `evaluation/runner.py` (6 scenarios) | Clinical safety |
| REQ-T10 | Performance benchmarks | `evaluation/performance_benchmarks.py` | Performance |

---

## Traceability Summary

| Requirement Category | Total Requirements | Implemented | Coverage |
|---------------------|-------------------|-------------|---------|
| Functional (F) | 18 | 18 | 100% |
| Clinical Safety (S) | 13 | 13 | 100% |
| Agent Architecture (A) | 10 | 10 | 100% |
| Knowledge Repository (K) | 7 | 7 | 100% |
| Learning System (L) | 8 | 8 | 100% |
| Observability (O) | 5 | 5 | 100% |
| Frontend (UI) | 8 | 8 | 100% |
| Testing (T) | 10 | 10 | 100% |
| **TOTAL** | **79** | **79** | **100%** |
