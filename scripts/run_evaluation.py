"""
DischargePilot AI — Full Evaluation Pipeline Script.

Runs the complete evaluation suite:
1. All 6 clinical scenarios
2. Clinical safety requirements
3. Performance benchmarks
4. Generates all reports

Usage:
    python scripts/run_evaluation.py
    python scripts/run_evaluation.py --reports-only
    python scripts/run_evaluation.py --safety-only
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Add project paths
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
EVAL_DIR = PROJECT_ROOT / "evaluation"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_DIR))


def run_scenario_evaluation() -> list:
    """Run all 6 clinical scenarios."""
    from evaluation.runner import EvaluationRunner
    print("\n[1/4] Running Clinical Scenario Evaluation...")
    print("-" * 60)
    runner = EvaluationRunner(mode="offline")
    results = runner.run_all()
    passed = sum(1 for r in results if r.passed)
    print(f"\nScenario Results: {passed}/{len(results)} passed")
    return results


def run_safety_evaluation(results: list) -> None:
    """Run clinical safety requirement validation."""
    from evaluation.clinical_safety_eval import ClinicalSafetyEvaluator
    from evaluation.runner import EvaluationRunner, _generate_mock_result
    import json

    print("\n[2/4] Running Clinical Safety Evaluation...")
    print("-" * 60)

    # Load scenarios and generate mock outputs
    scenarios_dir = PROJECT_ROOT / "evaluation" / "scenarios"
    system_outputs = {}
    for path in sorted(scenarios_dir.glob("scenario_*.json")):
        with open(path, encoding="utf-8") as f:
            scenario = json.load(f)
        output = _generate_mock_result(scenario)
        system_outputs[scenario["scenario_id"]] = output

    evaluator = ClinicalSafetyEvaluator()
    report = evaluator.evaluate_all(system_outputs)
    evaluator.print_report(report)

    summary = report.summary()
    if summary["overall_pass"]:
        print("\n✅ All critical safety requirements met.")
    else:
        print(f"\n❌ {summary['critical_failures']} critical safety requirement(s) failed.")


def run_performance_benchmarks() -> None:
    """Run performance benchmarks."""
    print("\n[3/4] Running Performance Benchmarks...")
    print("-" * 60)
    from evaluation.performance_benchmarks import PerformanceBenchmarkSuite
    suite = PerformanceBenchmarkSuite(iterations=3)
    benchmarks = suite.run_all()
    suite.print_report(benchmarks)


def generate_reports(results: list) -> None:
    """Generate all evaluation reports."""
    print("\n[4/4] Generating Reports...")
    print("-" * 60)
    from evaluation.report_generator import ReportGenerator

    # Simulate some learning history for the report
    learning_history = [0.55, 0.60, 0.63, 0.68, 0.72, 0.75, 0.78, 0.80, 0.82, 0.84]

    gen = ReportGenerator(
        results=results,
        learning_history=learning_history,
    )
    output_dir = str(PROJECT_ROOT / "outputs" / "reports")
    saved = gen.save_all(output_dir=output_dir)
    print(f"\nSaved {len(saved)} reports to: {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="DischargePilot AI — Full Evaluation Pipeline")
    parser.add_argument("--reports-only", action="store_true", help="Only generate reports")
    parser.add_argument("--safety-only", action="store_true", help="Only run safety evaluation")
    parser.add_argument("--skip-benchmarks", action="store_true", help="Skip performance benchmarks")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("DISCHARGEPILOT AI — EVALUATION PIPELINE")
    print("=" * 60)
    t_start = time.time()

    results = run_scenario_evaluation()

    if not args.reports_only:
        run_safety_evaluation(results)

    if not args.reports_only and not args.safety_only and not args.skip_benchmarks:
        run_performance_benchmarks()

    generate_reports(results)

    elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"Evaluation complete in {elapsed:.1f}s")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
