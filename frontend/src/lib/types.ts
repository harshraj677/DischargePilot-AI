// ── Enums ─────────────────────────────────────────────────────────────────────

export type DocumentType =
  | "admission_note"
  | "progress_note"
  | "lab_report"
  | "medication_record"
  | "discharge_instruction"
  | "unknown";

export type DocumentStatus =
  | "UPLOADED"
  | "PROCESSING"
  | "PROCESSED"
  | "FAILED"
  | "EMPTY"
  | "REVIEW_REQUIRED";

export type ClassificationMethod =
  | "rule_based"
  | "llm_assisted"
  | "user_declared";

export type SummaryStatus =
  | "PENDING_REVIEW"
  | "IN_REVIEW"
  | "APPROVED"
  | "ESCALATED"
  | "INCOMPLETE";

// ── Patient ────────────────────────────────────────────────────────────────────

export interface PatientCreate {
  mrn: string;
  first_name: string;
  last_name: string;
  date_of_birth?: string;
  gender?: string;
  admission_date?: string;
  discharge_date?: string;
  attending_md?: string;
  ward?: string;
}

export interface PatientDocumentSummary {
  id: string;
  document_type: DocumentType;
  file_name: string;
  status: DocumentStatus;
  page_count: number | null;
  created_at: string;
}

export interface Patient {
  id: string;
  mrn: string;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  gender: string | null;
  admission_date: string | null;
  discharge_date: string | null;
  attending_md: string | null;
  ward: string | null;
  document_count: number;
  documents: PatientDocumentSummary[];
  summary_status: SummaryStatus | null;
  created_at: string;
  updated_at: string;
}

export interface PatientListItem {
  id: string;
  mrn: string;
  first_name: string;
  last_name: string;
  ward: string | null;
  admission_date: string | null;
  document_count: number;
  summary_status: SummaryStatus | null;
  created_at: string;
}

export interface PatientListResponse {
  items: PatientListItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

// ── Document ───────────────────────────────────────────────────────────────────

export interface EvidenceRef {
  document_id: string;
  document_name: string;
  document_type: DocumentType;
  page_number: number;
  excerpt: string;
  char_start?: number;
  char_end?: number;
}

export interface ClinicalMetadata {
  patient_name?: string;
  mrn?: string;
  date_of_birth?: string;
  admission_date?: string;
  discharge_date?: string;
  provider_name?: string;
  document_date?: string;
  facility_name?: string;
}

export interface OcrMetadata {
  provider: string;
  confidence: number;
  requires_review: boolean;
  extraction_method: string;
}

export interface PageChunk {
  page_number: number;
  text: string;
  char_count: number;
  word_count: number;
  is_empty: boolean;
  document_id: string;
  document_name: string;
  ocr_metadata?: OcrMetadata | null;
}

export interface ProcessingLog {
  event: string;
  timestamp: string;
  message: string;
  details: Record<string, unknown>;
  is_error: boolean;
}

export interface DocumentResponse {
  id: string;
  patient_id: string;
  document_type: DocumentType;
  file_name: string;
  file_size_bytes: number | null;
  page_count: number | null;
  status: DocumentStatus;
  classification_confidence: number | null;
  classification_method: ClassificationMethod | null;
  processing_error: string | null;
  metadata?: ClinicalMetadata;
  created_at: string;
  updated_at: string;
}

export interface DocumentDetailResponse extends DocumentResponse {
  page_chunks: PageChunk[];
  processing_logs: ProcessingLog[];
}

export interface ProcessingStatus {
  patient_id: string;
  total_documents: number;
  processed: number;
  processing: number;
  failed: number;
  uploaded: number;
  all_ready: boolean;
  documents: DocumentResponse[];
}

export interface DocumentListResponse {
  items: DocumentResponse[];
  total: number;
}

// ── Upload UI State ────────────────────────────────────────────────────────────

export type UploadState =
  | "idle"
  | "uploading"
  | "processing"
  | "processed"
  | "failed";

export interface UploadingFile {
  id: string;
  file: File;
  declaredType: DocumentType | null;
  uploadState: UploadState;
  progress: number;
  documentId?: string;
  error?: string;
  document?: DocumentResponse;
}

export const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  admission_note: "Admission Note",
  progress_note: "Progress Note",
  lab_report: "Lab Report",
  medication_record: "Medication Record",
  discharge_instruction: "Discharge Instruction",
  unknown: "Unknown",
};

export const STATUS_LABELS: Record<DocumentStatus, string> = {
  UPLOADED: "Uploaded",
  PROCESSING: "Processing",
  PROCESSED: "Processed",
  FAILED: "Failed",
  EMPTY: "Empty",
  REVIEW_REQUIRED: "Needs Review",
};

// ── Agent Types ────────────────────────────────────────────────────────────────

export type AgentRunStatus =
  | "PENDING"
  | "RUNNING"
  | "COMPLETED"
  | "ESCALATED"
  | "FAILED"
  | "TIMED_OUT";

export interface AgentRunSummary {
  run_id: string;
  patient_id: string;
  status: AgentRunStatus;
  iteration_count: number;
  total_tokens: number;
  completeness_score: number | null;
  escalation_required: boolean;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export interface AgentRunDetail extends AgentRunSummary {
  knowledge_base: Record<string, unknown> | null;
  trace: TraceStep[] | null;
  escalation_reasons: string[];
  missing_information: string[];
}

export interface TraceStep {
  step: number;
  selected_tool: string;
  tool_input?: Record<string, unknown>;
  tool_output?: Record<string, unknown>;
  reasoning?: string;
  duration_ms?: number;
  tokens_in?: number;
  tokens_out?: number;
  state_changes?: Record<string, unknown>;
  next_action?: string;
  timestamp?: string;
}

// ── Safety Types ───────────────────────────────────────────────────────────────

export type SafetyStatus = "APPROVED" | "REVIEW_REQUIRED" | "BLOCKED";
export type FlagSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";
export type FlagCategory =
  | "MEDICATION_SAFETY"
  | "DIAGNOSIS_CONFLICT"
  | "MISSING_INFORMATION"
  | "COMPLETENESS"
  | "DOCUMENTATION_QUALITY"
  | "CLINICAL_ACCURACY"
  | "FOLLOWUP_REQUIRED";

export interface ReviewFlag {
  flag_id: string;
  category: FlagCategory;
  severity: FlagSeverity;
  description: string;
  section: string;
  recommendation: string;
  requires_acknowledgment: boolean;
}

export interface SafetyReportResponse {
  report_id: string;
  overall_status: SafetyStatus;
  can_generate_summary: boolean;
  safety_score: number;
  completeness_score: number;
  blocking_issues: string[];
  warnings: string[];
  flag_count: number;
  critical_flag_count: number;
}

// ── Summary Types ──────────────────────────────────────────────────────────────

export type SummaryReviewStatus = "PENDING_REVIEW" | "IN_REVIEW" | "APPROVED" | "REJECTED" | "ESCALATED";

export interface SummarySectionResponse {
  name: string;
  content: string;
  status: string;
  flag_count: number;
}

export interface SummaryResponse {
  summary_id: string;
  patient_id: string;
  agent_run_id: string;
  status: SummaryReviewStatus;
  completeness_score: number;
  safety_score: number;
  generated_at: string;
  sections: SummarySectionResponse[];
  review_flags: ReviewFlag[];
  total_flags: number;
  requires_acknowledgment_count: number;
}

// ── Learning Types (Phase 8) ───────────────────────────────────────────────────

export interface EditRecord {
  original_text: string;
  edited_text: string;
  section_name: string;
  edit_type: string;
  edit_distance: number;
}

export interface RewardScore {
  total: number;
  edit_distance_score: number;
  section_accuracy_score: number;
  review_burden_score: number;
  breakdown: Record<string, number>;
}

export interface DoctorReview {
  review_id: string;
  run_id: string;
  draft_summary_id: string | null;
  edited_sections: Record<string, string>;
  review_notes: string;
  reward_score: RewardScore | null;
  strategy_used: string | null;
  created_at: string;
}

export interface PromptStrategy {
  strategy_id: string;
  name: string;
  prompt_template: string;
  variant: string;
  total_uses: number;
  avg_reward: number;
  description: string;
}

export interface LearningMetrics {
  total_reviews: number;
  avg_reward: number;
  avg_edit_distance: number;
  improvement_rate: number;
  best_strategy: string | null;
  sessions_by_date: Array<{ date: string; avg_reward: number; count: number }>;
}

// ── System / Claude status ──────────────────────────────────────────────────

export interface ClaudeStatus {
  provider: "claude";
  status: "connected" | "degraded" | "not_configured";
  configured: boolean;
  text_model: string;
  vision_model: string;
  requests: {
    total: number;
    text: number;
    vision: number;
    ocr: number;
    errors: number;
    last_request_at: string | null;
    last_error: string | null;
    last_error_at: string | null;
  };
  cache: {
    enabled: boolean;
    hits: number;
    misses: number;
  };
  ocr: {
    enabled: boolean;
    primary_provider: string;
    status: "active" | "inactive";
    requests: number;
  };
}
