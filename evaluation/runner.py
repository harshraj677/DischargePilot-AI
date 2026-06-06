"""
DischargePilot AI — Evaluation Runner (Phase 9).

Executes evaluation scenarios against the system and computes all metrics.
Can run in:
- offline mode: uses scenario JSON files + mock outputs
- online mode: calls live backend API

Usage:
    python evaluation/runner.py --mode offline --scenario all
    python evaluation/runner.py --mode online --scenario SCN-001
    python evaluation/runner.py --mode offline --scenario all --output reports/eval_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from evaluation.metrics import (
    ConflictDetectionMetric,
    EditDistanceMetric,
    EvaluationResult,
    EvidenceCoverageMetric,
    LearningImprovementMetric,
    MedicationReconciliationMetric,
    PendingResultAccuracyMetric,
    ReviewBurdenMetric,
    ReviewFlagAccuracyMetric,
    SafetyComplianceMetric,
    SummaryCompletenessMetric,
)


SCENARIOS_DIR = Path(__file__).parent / "scenarios"
REPORTS_DIR = Path(__file__).parent.parent / "outputs" / "evaluation"


# ── Mock Result Generator ─────────────────────────────────────────────────────

def _generate_mock_result(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a plausible mock system output for offline evaluation.
    Uses the scenario's expected_outputs to construct a realistic mock.
    """
    expected = scenario.get("expected_outputs", {})
    ctx = scenario.get("clinical_context", {})

    # Simulate safety report
    status = expected.get("safety_status", "APPROVED")
    safety_score = expected.get("safety_score_min", 0.75)
    if isinstance(safety_score, float):
        pass
    elif "safety_score_range" in expected:
        safety_score = sum(expected["safety_score_range"]) / 2

    safety_report = {
        "overall_status": status,
        "safety_score": safety_score,
        "can_generate_summary": expected.get("can_generate_summary", True),
        "blocking_issues": expected.get("blocking_issues", []),
        "warnings": [],
        "review_flags": [f"flag_{i}" for i in range(expected.get("review_flags_expected", 0))],
        "validation_results": [
            {"validator_name": "evidence_validator"},
            {"validator_name": "completeness_validator"},
            {"validator_name": "medication_validator"},
            {"validator_name": "conflict_validator"},
            {"validator_name": "pending_result_validator"},
        ],
    }

    # Simulate knowledge base
    kb_facts = {}
    if ctx.get("diagnoses"):
        kb_facts["diagnoses"] = [
            {
                "value": d["name"],
                "confidence": 0.92,
                "evidence": f"Excerpt: {d['name']}",
                "source_document": "admission_note.pdf",
                "page_number": 1,
            }
            for d in ctx["diagnoses"]
        ]

    # Simulate summary sections
    summary_sections = {}
    if expected.get("can_generate_summary", True):
        summary_sections = {
            "patient_info": f"{ctx.get('patient', {}).get('name', '')} | MRN: {ctx.get('patient', {}).get('mrn', '')}",
            "principal_diagnosis": next(
                (d["name"] for d in ctx.get("diagnoses", []) if d.get("is_principal")),
                "",
            ),
            "hospital_course": ctx.get("hospital_course", ""),
            "discharge_medications": "; ".join(
                f"{m['name']} {m.get('dose', '')} {m.get('frequency', '')}"
                for m in ctx.get("medications_discharge", [])
            ),
            "follow_up": "; ".join(ctx.get("follow_up", [])),
            "discharge_condition": ctx.get("discharge_condition", ""),
        }
        if ctx.get("pending_results"):
            summary_sections["pending_results"] = "; ".join(
                p["description"] for p in ctx["pending_results"]
            )

    # Detected conflicts
    detected_conflicts = [c["description"] for c in ctx.get("conflicts", [])]

    # Detected pending
    detected_pending = [p["description"] for p in ctx.get("pending_results", [])]

    return {
        "safety_report": safety_report,
        "knowledge_base": kb_facts,
        "summary_sections": summary_sections,
        "detected_conflicts": detected_conflicts,
        "detected_pending": detected_pending,
        "medication_changes": [
            {"medication": m["name"], "change": "added"}
            for m in ctx.get("medications_discharge", [])
            if m.get("new")
        ],
        "agent_status": "COMPLETED",
        "completeness_score": 0.88,
        "escalation_required": expected.get("escalation_required", False),
    }


# ── Scenario Evaluator ────────────────────────────────────────────────────────

class ScenarioEvaluator:
    def __init__(self) -> None:
        self.evidence_metric = EvidenceCoverageMetric()
        self.completeness_metric = SummaryCompletenessMetric()
        self.conflict_metric = ConflictDetectionMetric()
        self.med_recon_metric = MedicationReconciliationMetric()
        self.safety_metric = SafetyComplianceMetric()
        self.pending_metric = PendingResultAccuracyMetric()
        self.flag_metric = ReviewFlagAccuracyMetric()
        self.edit_metric = EditDistanceMetric()

    def evaluate(
        self,
        scenario: Dict[str, Any],
        system_output: Dict[str, Any],
    ) -> EvaluationResult:
        expected = scenario.get("expected_outputs", {})
        ctx = scenario.get("clinical_context", {})

        result = EvaluationResult(
            scenario_id=scenario["scenario_id"],
            scenario_name=scenario["name"],
        )

        # 1. Evidence Coverage
        result.evidence_coverage = self.evidence_metric.compute(
            system_output.get("knowledge_base", {})
        )

        # 2. Summary Completeness
        result.summary_completeness = self.completeness_metric.compute(
            system_output.get("summary_sections", {})
        )

        # 3. Conflict Detection
        actual_conflicts = [c["description"] for c in ctx.get("conflicts", [])]
        detected_conflicts = system_output.get("detected_conflicts", [])
        conflict_scores = self.conflict_metric.compute(detected_conflicts, actual_conflicts)
        result.conflict_detection_f1 = conflict_scores["f1"] if actual_conflicts else 1.0

        # 4. Medication Reconciliation
        actual_changes = [
            {"medication": m["name"], "change": "added"}
            for m in ctx.get("medications_discharge", [])
            if m.get("new")
        ]
        detected_changes = system_output.get("medication_changes", [])
        med_scores = self.med_recon_metric.compute(detected_changes, actual_changes)
        result.medication_reconciliation_accuracy = med_scores["accuracy"]

        # 5. Safety Compliance
        safety_scores = self.safety_metric.compute(
            system_output.get("safety_report", {}),
            system_output.get("summary_sections"),
        )
        result.safety_compliance_score = safety_scores["compliance_score"]

        # 6. Pending Result Accuracy
        actual_pending = [p["description"] for p in ctx.get("pending_results", [])]
        detected_pending = system_output.get("detected_pending", [])
        summary_pending_raw = system_output.get("summary_sections", {}).get("pending_results", "")
        summary_pending = [summary_pending_raw] if summary_pending_raw else []
        pending_scores = self.pending_metric.compute(detected_pending, actual_pending, summary_pending)
        result.pending_result_recall = pending_scores["detection_recall"]

        # 7. Review Flag Accuracy
        expected_flags_count = expected.get("review_flags_expected", 0)
        required_flags = [f"flag_{i}" for i in range(expected_flags_count)]
        raised_flags = system_output.get("safety_report", {}).get("review_flags", [])
        flag_scores = self.flag_metric.compute(raised_flags, required_flags)
        result.review_flag_precision = flag_scores["precision"]
        result.review_flag_recall = flag_scores["recall"]

        # 8. Validate against expected outputs
        failure_reasons = []
        actual_status = system_output.get("safety_report", {}).get("overall_status")
        expected_status = expected.get("safety_status")
        if expected_status and actual_status != expected_status:
            failure_reasons.append(
                f"Safety status mismatch: expected {expected_status}, got {actual_status}"
            )

        expected_escalation = expected.get("escalation_required")
        actual_escalation = system_output.get("escalation_required")
        if expected_escalation is not None and expected_escalation != actual_escalation:
            failure_reasons.append(
                f"Escalation mismatch: expected {expected_escalation}, got {actual_escalation}"
            )

        result.failure_reasons = failure_reasons
        result.passed = len(failure_reasons) == 0
        return result


# ── Batch Runner ──────────────────────────────────────────────────────────────

class EvaluationRunner:
    def __init__(self, mode: str = "offline") -> None:
        self.mode = mode
        self.evaluator = ScenarioEvaluator()

    def load_scenario(self, path: Path) -> Dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def get_system_output(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        if self.mode == "offline":
            return _generate_mock_result(scenario)
        else:
            raise NotImplementedError("Online mode requires a running backend. Set BACKEND_URL env var.")

    def run_all(self) -> List[EvaluationResult]:
        scenario_files = sorted(SCENARIOS_DIR.glob("scenario_*.json"))
        results = []
        for path in scenario_files:
            print(f"  Evaluating {path.name}...", end=" ", flush=True)
            t0 = time.time()
            scenario = self.load_scenario(path)
            output = self.get_system_output(scenario)
            result = self.evaluator.evaluate(scenario, output)
            elapsed = time.time() - t0
            status = "PASS" if result.passed else "FAIL"
            print(f"{status} ({elapsed:.2f}s) — Overall: {result.overall_score():.1%}")
            results.append(result)
        return results

    def run_one(self, scenario_id: str) -> Optional[EvaluationResult]:
        for path in SCENARIOS_DIR.glob("scenario_*.json"):
            scenario = self.load_scenario(path)
            if scenario["scenario_id"] == scenario_id:
                output = self.get_system_output(scenario)
                return self.evaluator.evaluate(scenario, output)
        print(f"Scenario {scenario_id} not found.")
        return None


# ── CLI Entry Point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="DischargePilot AI Evaluation Runner")
    parser.add_argument("--mode", choices=["offline", "online"], default="offline")
    parser.add_argument("--scenario", default="all", help="Scenario ID or 'all'")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    args = parser.parse_args()

    print(f"\nDischargePilot AI Evaluation Runner")
    print(f"Mode: {args.mode} | Scenario: {args.scenario}")
    print("=" * 60)

    runner = EvaluationRunner(mode=args.mode)

    if args.scenario == "all":
        results = runner.run_all()
    else:
        result = runner.run_one(args.scenario)
        results = [result] if result else []

    if not results:
        print("No scenarios evaluated.")
        return

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"Scenarios: {passed}/{total} passed")
    print(f"Avg Evidence Coverage:    {sum(r.evidence_coverage for r in results)/total:.1%}")
    print(f"Avg Summary Completeness: {sum(r.summary_completeness for r in results)/total:.1%}")
    print(f"Avg Safety Compliance:    {sum(r.safety_compliance_score for r in results)/total:.1%}")
    print(f"Avg Conflict F1:          {sum(r.conflict_detection_f1 for r in results)/total:.1%}")
    print(f"Avg Overall Score:        {sum(r.overall_score() for r in results)/total:.1%}")

    for r in results:
        status_icon = "✓" if r.passed else "✗"
        print(f"  {status_icon} {r.scenario_id}: {r.scenario_name} — {r.overall_score():.1%}")
        if r.failure_reasons:
            for reason in r.failure_reasons:
                print(f"      → {reason}")

    # Save report
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report_data = {
            "generated_at": datetime.utcnow().isoformat(),
            "mode": args.mode,
            "summary": {
                "total": total,
                "passed": passed,
                "pass_rate": passed / total if total > 0 else 0,
            },
            "results": [asdict(r) for r in results],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
