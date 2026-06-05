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
  | "EMPTY";

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

export interface PageChunk {
  page_number: number;
  text: string;
  char_count: number;
  word_count: number;
  is_empty: boolean;
  document_id: string;
  document_name: string;
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
};
