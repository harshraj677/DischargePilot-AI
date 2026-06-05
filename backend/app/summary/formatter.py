from __future__ import annotations

from typing import Any, Dict

from app.summary.models import DischargeSummary, SummaryStatus

_DIVIDER = "=" * 60
_SECTION_DIVIDER = "-" * 40


def format_as_text(summary: DischargeSummary) -> str:
    """
    Render a DischargeSummary as plain text suitable for clinical display or printing.
    Sections with MISSING status are omitted or shown as 'Not documented'.
    Review flags are appended in a dedicated REVIEW FLAGS section.
    """
    lines = []

    lines.append(_DIVIDER)
    lines.append("DISCHARGE SUMMARY")
    lines.append(f"Generated: {summary.generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"Status: {summary.status.value.upper().replace('_', ' ')}")
    lines.append(f"Safety Score: {summary.safety_score:.0%} | Completeness: {summary.completeness_score:.0%}")
    lines.append(_DIVIDER)

    _add_section(lines, "PATIENT INFORMATION", summary.patient_info)
    _add_section(lines, "HOSPITAL INFORMATION", summary.hospital_info)
    _add_section(lines, "PRINCIPAL DIAGNOSIS", summary.principal_diagnosis)
    _add_section(lines, "SECONDARY DIAGNOSES", summary.secondary_diagnoses)
    _add_section(lines, "ALLERGIES", summary.allergies)
    _add_section(lines, "HOSPITAL COURSE", summary.hospital_course)
    _add_section(lines, "PROCEDURES", summary.procedures)
    _add_section(lines, "ADMISSION MEDICATIONS", summary.admission_medications)
    _add_section(lines, "DISCHARGE MEDICATIONS", summary.discharge_medications)
    _add_section(lines, "MEDICATION CHANGES", summary.medication_changes)
    _add_section(lines, "LABORATORY RESULTS", summary.lab_results)
    _add_section(lines, "PENDING RESULTS", summary.pending_results)
    _add_section(lines, "FOLLOW-UP INSTRUCTIONS", summary.follow_up)
    _add_section(lines, "CONDITION AT DISCHARGE", summary.discharge_condition)

    if summary.review_flags:
        lines.append("")
        lines.append(_DIVIDER)
        lines.append("REVIEW FLAGS — CLINICIAN ACTION REQUIRED")
        lines.append(_DIVIDER)
        for flag in summary.review_flags:
            lines.append(f"[{flag.severity.value}] {flag.category.value.upper()}")
            lines.append(f"  Section: {flag.affected_section.value}")
            lines.append(f"  Issue: {flag.description}")
            lines.append(f"  Recommendation: {flag.recommendation}")
            if flag.requires_acknowledgment:
                lines.append("  *** REQUIRES CLINICIAN ACKNOWLEDGMENT ***")
            lines.append("")

    lines.append(_DIVIDER)
    lines.append("END OF DISCHARGE SUMMARY")
    lines.append("This is an AI-generated draft. A licensed clinician must review and approve before use.")
    lines.append(_DIVIDER)

    return "\n".join(lines)


def format_as_dict(summary: DischargeSummary) -> Dict[str, Any]:
    """Structured dictionary representation suitable for JSON serialization."""
    return summary.to_dict()


def _add_section(lines: list, title: str, section) -> None:
    if section.status == SummaryStatus.MISSING:
        return
    lines.append("")
    lines.append(_SECTION_DIVIDER)
    lines.append(title)
    lines.append(_SECTION_DIVIDER)
    if section.content:
        lines.append(section.content)
    else:
        lines.append("Not documented")
    if section.status == SummaryStatus.REVIEW_REQUIRED and section.section_flags:
        lines.append(f"  ⚠ {len(section.section_flags)} review flag(s) in this section")
