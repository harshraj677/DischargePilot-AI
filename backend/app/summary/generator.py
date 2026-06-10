from __future__ import annotations

from typing import Optional

from app.gemini.client import GeminiClient

from app.config import Settings
from app.knowledge.repository import KnowledgeRepository
from app.safety.models import SafetyReport, SectionName
from app.summary.models import DischargeSummary, SummarySection, SummaryStatus
from app.summary.prompts import (
    DISCHARGE_CONDITION_PROMPT,
    HOSPITAL_COURSE_PROMPT,
    MEDICATION_CHANGES_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
)
from app.utils.logging import AuditLogger, get_logger

logger = get_logger(__name__)
audit = AuditLogger(module="summary_generator")

_CLAUDE_MAX_TOKENS = 1500


class DischargeSummaryGenerator:
    """
    Hybrid discharge summary generator.

    Structured sections (demographics, medications, labs) use template-based
    generation with zero hallucination risk. Narrative sections (hospital course,
    discharge condition) call Claude with ONLY KB facts injected as context.
    """

    def __init__(self, client: GeminiClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.CLAUDE_MODEL

    async def generate(
        self,
        kb: KnowledgeRepository,
        safety_report: SafetyReport,
        run_id: str,
    ) -> DischargeSummary:
        patient_id = kb.kb.patient_id

        if not safety_report.can_generate_summary:
            raise ValueError(
                f"Cannot generate summary: safety validation returned BLOCKED. "
                f"Blocking issues: {safety_report.blocking_issues}"
            )

        logger.info("Starting summary generation", patient_id=patient_id, run_id=run_id)

        summary = DischargeSummary(
            patient_id=patient_id,
            agent_run_id=run_id,
            safety_report=safety_report,
            completeness_score=safety_report.completeness_score,
            safety_score=safety_report.safety_score,
            review_flags=safety_report.review_flags,
        )

        # Template-based sections
        summary.patient_info = self._build_patient_info(kb)
        summary.hospital_info = self._build_hospital_info(kb)
        summary.principal_diagnosis = self._build_principal_diagnosis(kb)
        summary.secondary_diagnoses = self._build_secondary_diagnoses(kb)
        summary.procedures = self._build_procedures(kb)
        summary.allergies = self._build_allergies(kb)
        summary.admission_medications = self._build_admission_meds(kb)
        summary.discharge_medications = self._build_discharge_meds(kb)
        summary.lab_results = self._build_lab_results(kb)
        summary.pending_results = self._build_pending_results(kb)
        summary.follow_up = self._build_follow_up(kb)

        # Claude-assisted narrative sections
        summary.hospital_course = await self._generate_hospital_course(kb)
        summary.discharge_condition = await self._generate_discharge_condition(kb)
        summary.medication_changes = await self._generate_medication_changes(kb)

        # Attach section-level flags
        for flag in safety_report.review_flags:
            section = self._flag_section_to_summary_section(summary, flag.affected_section)
            if section:
                section.section_flags.append(flag)

        # Mark review_required sections
        for sec in summary.sections:
            if sec.section_flags and sec.status == SummaryStatus.POPULATED:
                sec.status = SummaryStatus.REVIEW_REQUIRED

        audit.log(
            "summary_generated",
            patient_id=patient_id,
            run_id=run_id,
            populated_sections=summary.populated_section_count,
            total_flags=len(summary.review_flags),
        )

        return summary

    # ── Template-based sections ───────────────────────────────────────────────

    def _build_patient_info(self, kb: KnowledgeRepository) -> SummarySection:
        demo = kb.kb.demographics
        lines = []
        if demo.name:
            lines.append(f"Name: {demo.name.value}")
        if demo.mrn:
            lines.append(f"MRN: {demo.mrn.value}")
        if demo.date_of_birth:
            lines.append(f"Date of Birth: {demo.date_of_birth.value}")
        if demo.age:
            lines.append(f"Age: {demo.age.value}")
        if demo.gender:
            lines.append(f"Gender: {demo.gender.value}")
        return self._section("patient_info", lines, "template")

    def _build_hospital_info(self, kb: KnowledgeRepository) -> SummarySection:
        info = kb.kb.hospital_info
        lines = []
        if info.facility:
            lines.append(f"Facility: {info.facility.value}")
        if info.ward:
            lines.append(f"Ward: {info.ward.value}")
        if info.admission_date:
            lines.append(f"Admission Date: {info.admission_date.value}")
        if info.discharge_date:
            lines.append(f"Discharge Date: {info.discharge_date.value}")
        if info.attending_physician:
            lines.append(f"Attending Physician: {info.attending_physician.value}")
        return self._section("hospital_info", lines, "template")

    def _build_principal_diagnosis(self, kb: KnowledgeRepository) -> SummarySection:
        principal = [d for d in kb.kb.diagnoses if d.is_principal]
        if not principal:
            return SummarySection(name="principal_diagnosis", status=SummaryStatus.MISSING)
        dx = principal[0]
        text = dx.name.value
        if dx.icd_code:
            text += f" ({dx.icd_code})"
        if dx.description:
            text += f"\n{dx.description.value}"
        return SummarySection(
            name="principal_diagnosis",
            content=text,
            status=SummaryStatus.POPULATED,
            generated_by="template",
            source_facts_count=1,
        )

    def _build_secondary_diagnoses(self, kb: KnowledgeRepository) -> SummarySection:
        secondary = [d for d in kb.kb.diagnoses if not d.is_principal]
        if not secondary:
            return SummarySection(name="secondary_diagnoses", content="None documented", status=SummaryStatus.POPULATED)
        lines = []
        for dx in secondary:
            line = f"• {dx.name.value}"
            if dx.icd_code:
                line += f" ({dx.icd_code})"
            lines.append(line)
        return self._section("secondary_diagnoses", lines, "template")

    def _build_procedures(self, kb: KnowledgeRepository) -> SummarySection:
        if not kb.kb.procedures:
            return SummarySection(name="procedures", content="None documented", status=SummaryStatus.POPULATED)
        lines = []
        for proc in kb.kb.procedures:
            line = f"• {proc.name.value}"
            if proc.date:
                line += f" — {proc.date.value}"
            if proc.outcome:
                line += f" (Outcome: {proc.outcome.value})"
            lines.append(line)
        return self._section("procedures", lines, "template")

    def _build_allergies(self, kb: KnowledgeRepository) -> SummarySection:
        if not kb.kb.allergies:
            return SummarySection(name="allergies", content="Not documented", status=SummaryStatus.MISSING)
        lines = []
        for a in kb.kb.allergies:
            line = f"• {a.allergen.value}"
            if a.reaction:
                line += f" — Reaction: {a.reaction.value}"
            if a.severity:
                line += f" ({a.severity})"
            lines.append(line)
        return self._section("allergies", lines, "template")

    def _build_admission_meds(self, kb: KnowledgeRepository) -> SummarySection:
        meds = kb.kb.medications_admission
        if not meds:
            return SummarySection(name="admission_medications", content="None documented", status=SummaryStatus.POPULATED)
        return self._section("admission_medications", self._format_med_list(meds), "template")

    def _build_discharge_meds(self, kb: KnowledgeRepository) -> SummarySection:
        meds = kb.kb.medications_discharge
        if not meds:
            return SummarySection(name="discharge_medications", status=SummaryStatus.MISSING)
        return self._section("discharge_medications", self._format_med_list(meds), "template")

    def _build_lab_results(self, kb: KnowledgeRepository) -> SummarySection:
        labs = kb.kb.lab_results
        if not labs:
            return SummarySection(name="lab_results", content="No results documented", status=SummaryStatus.POPULATED)
        lines = []
        for lab in sorted(labs, key=lambda l: l.is_critical, reverse=True):
            flag = " ⚠ CRITICAL" if lab.is_critical else (" (Abnormal)" if lab.is_abnormal else "")
            line = f"• {lab.test_name.value}: {lab.value.value}"
            if lab.unit:
                line += f" {lab.unit}"
            if lab.reference_range:
                line += f" (Ref: {lab.reference_range})"
            line += flag
            lines.append(line)
        return self._section("lab_results", lines, "template")

    def _build_pending_results(self, kb: KnowledgeRepository) -> SummarySection:
        pending = kb.kb.pending_results
        if not pending:
            return SummarySection(name="pending_results", content="None at time of discharge", status=SummaryStatus.POPULATED)
        lines = []
        for pr in pending:
            line = f"• {pr.description.value}"
            if pr.expected_by:
                line += f" (Expected by: {pr.expected_by})"
            if pr.action_if_abnormal:
                line += f"\n  Action if abnormal: {pr.action_if_abnormal}"
            lines.append(line)
        return self._section("pending_results", lines, "template")

    def _build_follow_up(self, kb: KnowledgeRepository) -> SummarySection:
        follow_ups = kb.kb.follow_ups
        if not follow_ups:
            return SummarySection(name="follow_up", status=SummaryStatus.MISSING)
        lines = []
        for fu in follow_ups:
            line = f"• {fu.instruction.value}"
            if fu.specialist:
                line += f" (With: {fu.specialist})"
            if fu.timeframe:
                line += f" — {fu.timeframe}"
            if fu.contact:
                line += f" | Contact: {fu.contact}"
            lines.append(line)
        return self._section("follow_up", lines, "template")

    # ── Claude-assisted narrative sections ────────────────────────────────────

    async def _generate_hospital_course(self, kb: KnowledgeRepository) -> SummarySection:
        course = kb.kb.hospital_course
        if not course:
            return SummarySection(name="hospital_course", status=SummaryStatus.MISSING)

        kb_ctx = kb.to_agent_context()
        course_text = f"Value: {course.value}\nEvidence: {course.short_evidence(400)}"

        prompt = HOSPITAL_COURSE_PROMPT.format(
            system_context=SUMMARY_SYSTEM_PROMPT,
            kb_context=kb_ctx,
            hospital_course_facts=course_text,
        )

        try:
            narrative = await self._client.generate_content(
                prompt=prompt,
                model_type="text",
                config={"max_output_tokens": _CLAUDE_MAX_TOKENS}
            )
            narrative = narrative.strip()
            return SummarySection(
                name="hospital_course",
                content=narrative,
                status=SummaryStatus.POPULATED,
                generated_by="claude",
                source_facts_count=1,
            )
        except Exception as exc:
            logger.warning("Hospital course generation failed, using raw value", error=str(exc))
            return SummarySection(
                name="hospital_course",
                content=course.value,
                status=SummaryStatus.PARTIAL,
                generated_by="template",
                source_facts_count=1,
            )

    async def _generate_discharge_condition(self, kb: KnowledgeRepository) -> SummarySection:
        condition = kb.kb.discharge_condition
        if not condition:
            return SummarySection(name="discharge_condition", status=SummaryStatus.MISSING)

        kb_ctx = kb.to_agent_context()
        condition_text = f"Value: {condition.value}\nEvidence: {condition.short_evidence(300)}"

        prompt = DISCHARGE_CONDITION_PROMPT.format(
            system_context=SUMMARY_SYSTEM_PROMPT,
            kb_context=kb_ctx,
            condition_facts=condition_text,
        )

        try:
            text = await self._client.generate_content(
                prompt=prompt,
                model_type="text",
                config={"max_output_tokens": 300}
            )
            text = text.strip()
            return SummarySection(
                name="discharge_condition",
                content=text,
                status=SummaryStatus.POPULATED,
                generated_by="claude",
                source_facts_count=1,
            )
        except Exception as exc:
            logger.warning("Discharge condition generation failed", error=str(exc))
            return SummarySection(
                name="discharge_condition",
                content=condition.value,
                status=SummaryStatus.PARTIAL,
                generated_by="template",
                source_facts_count=1,
            )

    async def _generate_medication_changes(self, kb: KnowledgeRepository) -> SummarySection:
        admission_meds = kb.kb.medications_admission
        discharge_meds = kb.kb.medications_discharge

        if not admission_meds and not discharge_meds:
            return SummarySection(name="medication_changes", content="No medications documented", status=SummaryStatus.MISSING)

        admission_text = "\n".join(self._format_med_list(admission_meds)) or "None documented"
        discharge_text = "\n".join(self._format_med_list(discharge_meds)) or "None documented"

        prompt = MEDICATION_CHANGES_PROMPT.format(
            system_context=SUMMARY_SYSTEM_PROMPT,
            admission_meds=admission_text,
            discharge_meds=discharge_text,
        )

        try:
            text = await self._client.generate_content(
                prompt=prompt,
                model_type="text",
                config={"max_output_tokens": 800}
            )
            text = text.strip()
            return SummarySection(
                name="medication_changes",
                content=text,
                status=SummaryStatus.POPULATED,
                generated_by="claude",
                source_facts_count=len(admission_meds) + len(discharge_meds),
            )
        except Exception as exc:
            logger.warning("Medication changes generation failed", error=str(exc))
            return SummarySection(
                name="medication_changes",
                content="See admission and discharge medication sections for details.",
                status=SummaryStatus.PARTIAL,
                generated_by="template",
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _format_med_list(self, meds) -> list:
        lines = []
        for med in meds:
            parts = [f"• {med.name.value}"]
            if med.dose:
                parts.append(med.dose.value)
            if med.route:
                parts.append(med.route.value)
            if med.frequency:
                parts.append(med.frequency.value)
            if med.is_discontinued:
                parts.append("[DISCONTINUED]")
            lines.append(" — ".join(parts))
        return lines

    def _section(self, name: str, lines: list, generated_by: str) -> SummarySection:
        content = "\n".join(lines) if lines else "Not documented"
        status = SummaryStatus.POPULATED if lines else SummaryStatus.MISSING
        return SummarySection(
            name=name,
            content=content,
            status=status,
            generated_by=generated_by,
            source_facts_count=len(lines),
        )

    def _flag_section_to_summary_section(
        self, summary: DischargeSummary, section_name: SectionName
    ) -> Optional[SummarySection]:
        mapping = {
            SectionName.DEMOGRAPHICS: summary.patient_info,
            SectionName.HOSPITAL_INFO: summary.hospital_info,
            SectionName.PRINCIPAL_DIAGNOSIS: summary.principal_diagnosis,
            SectionName.SECONDARY_DIAGNOSES: summary.secondary_diagnoses,
            SectionName.HOSPITAL_COURSE: summary.hospital_course,
            SectionName.PROCEDURES: summary.procedures,
            SectionName.ALLERGIES: summary.allergies,
            SectionName.ADMISSION_MEDICATIONS: summary.admission_medications,
            SectionName.DISCHARGE_MEDICATIONS: summary.discharge_medications,
            SectionName.MEDICATION_CHANGES: summary.medication_changes,
            SectionName.LAB_RESULTS: summary.lab_results,
            SectionName.PENDING_RESULTS: summary.pending_results,
            SectionName.FOLLOW_UP: summary.follow_up,
            SectionName.DISCHARGE_CONDITION: summary.discharge_condition,
        }
        return mapping.get(section_name)
