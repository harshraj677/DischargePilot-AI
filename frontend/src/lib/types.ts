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
  stack_trace: string | null;
  failed_component: string | null;
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

// ── System / Groq status ─────────────────────────────────────────────────────

export interface GroqStatus {
  provider: "groq";
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
  rate_limit: {
    hits: number;
  };
}

// ── System / LLM auth status ─────────────────────────────────────────────────

export interface LLMStatus {
  provider: "groq";
  status: "healthy" | "failed";
  authenticated: boolean;
  model: string;
  error?: string;
}

// ── Analytics Dashboard (Phase 1/2) ───────────────────────────────────────────

export type DashboardSeverity = "HIGH" | "MEDIUM" | "LOW" | "INFO";

export interface SeverityDistribution {
  HIGH: number;
  MEDIUM: number;
  LOW: number;
  INFO: number;
}

export interface TopMissingField {
  field: string;
  count: number;
}

export interface TopConflict {
  title: string;
  count: number;
}

export interface DashboardMetrics {
  total_patients: number;
  total_documents: number;
  total_summaries: number;
  total_findings: number;
  average_safety_score: number;
  average_completeness_score: number;
  high_risk_findings: number;
  approval_rate: number;
  rejection_rate: number;
  acknowledgment_rate: number;
  severity_distribution: SeverityDistribution;
  top_missing_fields: TopMissingField[];
  top_conflicts: TopConflict[];
}

export const MISSING_FIELD_LABELS: Record<string, string> = {
  allergy_status: "Allergy Status",
  admission_date: "Admission Date",
  hospital_course: "Hospital Course",
  discharge_condition: "Discharge Condition",
  medication_dose: "Medication Dose",
};

// ── Review History (Phase 2) ──────────────────────────────────────────────────

export type ReviewActionType = "APPROVED" | "REJECTED" | "ACKNOWLEDGED";

export interface ReviewHistoryEntry {
  id: string;
  finding_id: string;
  reviewer: string;
  action: ReviewActionType;
  comments: string | null;
  timestamp: string;
  severity: DashboardSeverity | null;
  category: string | null;
  finding_title: string | null;
  summary_id: string | null;
  patient_id: string | null;
  patient_name: string | null;
}

export interface ReviewHistoryResponse {
  items: ReviewHistoryEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface ReviewHistoryFilters {
  page?: number;
  page_size?: number;
  severity?: string;
  action?: ReviewActionType;
  reviewer?: string;
  date_from?: string;
  date_to?: string;
}

// ── Global Search (Phase 2) ───────────────────────────────────────────────────

export interface SearchResultItem {
  patient_id: string;
  patient_name: string;
  mrn: string | null;
  summary_id: string | null;
  status: string | null;
  safety_score: number | null;
  completeness_score: number | null;
  created_at: string | null;
}

export interface SearchResponse {
  items: SearchResultItem[];
  total: number;
}

// ── Patient Timeline (Phase 2) ────────────────────────────────────────────────

export type TimelineEventType =
  | "patient_created"
  | "document_uploaded"
  | "summary_generated"
  | "finding_created"
  | "finding_approved"
  | "finding_rejected"
  | "finding_acknowledged";

export interface TimelineEvent {
  type: TimelineEventType;
  timestamp: string;
  title: string;
  description: string | null;
  severity: DashboardSeverity | null;
  metadata: Record<string, unknown>;
}

export interface PatientTimelineInfo {
  id: string;
  name: string;
  mrn: string | null;
  dob: string | null;
  gender: string | null;
  created_at: string;
}

export interface PatientTimelineResponse {
  patient: PatientTimelineInfo;
  latest_safety_score: number | null;
  latest_completeness_score: number | null;
  events: TimelineEvent[];
}
