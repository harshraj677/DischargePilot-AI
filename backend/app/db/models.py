import uuid
from datetime import datetime
from sqlalchemy import (
    String, Integer, Float, Text, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


# ── New Phase 8 tables ────────────────────────────────────────────────────────


class LearningRun(Base):
    """Records a single doctor review cycle with reward scores."""
    __tablename__ = "learning_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    strategy_id: Mapped[str] = mapped_column(String(50), nullable=False)
    reward_total: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    edit_distance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    section_accuracy_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    review_burden_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_learning_runs_run_id", "run_id"),
        Index("idx_learning_runs_strategy", "strategy_id"),
        Index("idx_learning_runs_created", "created_at"),
    )


class LearningStrategy(Base):
    """Prompt strategy variants tracked by the epsilon-greedy engine."""
    __tablename__ = "learning_strategies"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    total_uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_reward: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class CorrectionMemoryEntry(Base):
    """Stored correction patterns used as prompt hints in future generations."""
    __tablename__ = "correction_memory_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pattern: Mapped[str] = mapped_column(String(500), nullable=False)
    correction: Mapped[str] = mapped_column(Text, nullable=False)
    section_name: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_correction_memory_section", "section_name"),
        Index("idx_correction_memory_freq", "frequency"),
    )


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.utcnow()


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    mrn: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[str | None] = mapped_column(String(20), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    admission_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    discharge_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attending_md: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ward: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    documents: Mapped[list["Document"]] = relationship("Document", back_populates="patient", lazy="select")

    __table_args__ = (
        Index("idx_patients_mrn", "mrn"),
        Index("idx_patients_created", "created_at"),
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    declared_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="UPLOADED", index=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_chunks: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    clinical_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    processing_logs: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="documents")

    __table_args__ = (
        Index("idx_documents_patient", "patient_id"),
        Index("idx_documents_type", "document_type"),
        Index("idx_documents_status", "status"),
        Index("idx_documents_created", "created_at"),
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[str | None] = mapped_column(Text, nullable=True)
    memory_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    failed_component: Mapped[str | None] = mapped_column(String(100), nullable=True)
    iteration_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        Index("idx_agent_runs_patient", "patient_id"),
        Index("idx_agent_runs_status", "status"),
    )


class TraceStep(Base):
    __tablename__ = "trace_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    component: Mapped[str] = mapped_column(String(100), nullable=False)
    input: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        Index("idx_trace_steps_run", "run_id"),
        Index("idx_trace_steps_step", "step"),
    )



class DischargeReport(Base):
    __tablename__ = "discharge_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # "DRAFT" | "PENDING_REVIEW" | "APPROVED" | "REJECTED" (DischargeSummaryStatus)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_REVIEW", index=True)
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)       # JSON-serialized DischargeSummary
    safety_report_json: Mapped[str | None] = mapped_column(Text, nullable=True) # JSON-serialized SafetyReport
    completeness_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    safety_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        Index("idx_discharge_reports_patient", "patient_id"),
        Index("idx_discharge_reports_run", "agent_run_id"),
        Index("idx_discharge_reports_status", "status"),
    )
