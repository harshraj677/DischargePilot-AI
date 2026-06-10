"use client";

import {
  FileText, CheckCircle2, AlertCircle, Loader2, X, RefreshCw, Eye, FileSearch
} from "lucide-react";
import type { DocumentResponse, UploadingFile } from "@/lib/types";
import { DOCUMENT_TYPE_LABELS, STATUS_LABELS } from "@/lib/types";

// ── Uploading file card (during upload / processing) ─────────────────────────

interface UploadingFileCardProps {
  entry: UploadingFile;
  onRemove: (id: string) => void;
}

export function UploadingFileCard({ entry, onRemove }: UploadingFileCardProps) {
  const { file, uploadState, progress, error, document } = entry;
  const sizeMB = (file.size / (1024 * 1024)).toFixed(1);

  const stateConfig = {
    idle: { icon: <FileText className="h-4 w-4 text-slate-400" />, label: "Ready", color: "text-slate-500" },
    uploading: { icon: <Loader2 className="h-4 w-4 animate-spin text-blue-500" />, label: `Uploading ${progress}%`, color: "text-blue-600" },
    processing: { icon: <Loader2 className="h-4 w-4 animate-spin text-amber-500" />, label: "Processing…", color: "text-amber-600" },
    processed: { icon: <CheckCircle2 className="h-4 w-4 text-green-500" />, label: "Processed", color: "text-green-600" },
    failed: { icon: <AlertCircle className="h-4 w-4 text-red-500" />, label: "Failed", color: "text-red-600" },
  };

  const config = stateConfig[uploadState];

  return (
    <div className={[
      "flex items-center gap-3 rounded-lg border px-3 py-3 text-sm transition-colors",
      uploadState === "failed" ? "border-red-200 bg-red-50" : "border-slate-200 bg-white",
    ].join(" ")}>
      <div className="flex-shrink-0">{config.icon}</div>

      <div className="min-w-0 flex-1">
        <p className="truncate font-500 text-slate-700">{file.name}</p>
        <div className="mt-0.5 flex items-center gap-2 text-xs">
          <span className={config.color}>{config.label}</span>
          <span className="text-slate-300">·</span>
          <span className="text-slate-400">{sizeMB} MB</span>
          {entry.declaredType && (
            <>
              <span className="text-slate-300">·</span>
              <span className="text-slate-400">{DOCUMENT_TYPE_LABELS[entry.declaredType]}</span>
            </>
          )}
        </div>

        {uploadState === "uploading" && (
          <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-blue-500 transition-all duration-200"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}

        {uploadState === "failed" && error && (
          <p className="mt-1 text-xs text-red-600">{error}</p>
        )}
      </div>

      {(uploadState === "idle" || uploadState === "failed") && (
        <button
          onClick={() => onRemove(entry.id)}
          aria-label={`Remove ${file.name}`}
          className="flex-shrink-0 rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

// ── Processed document card (from API) ──────────────────────────────────────

interface DocumentCardProps {
  doc: DocumentResponse;
  onDelete?: (id: string) => void;
  onRetry?: (id: string) => void;
  onView?: (id: string) => void;
}

export function DocumentCard({ doc, onDelete, onRetry, onView }: DocumentCardProps) {
  const sizeMB = doc.file_size_bytes ? (doc.file_size_bytes / (1024 * 1024)).toFixed(1) : null;

  const statusConfig: Record<string, { icon: React.ReactNode; color: string; bg: string }> = {
    UPLOADED: {
      icon: <Loader2 className="h-4 w-4 animate-spin text-slate-400" />,
      color: "text-slate-500",
      bg: "bg-slate-50 border-slate-200",
    },
    PROCESSING: {
      icon: <Loader2 className="h-4 w-4 animate-spin text-amber-500" />,
      color: "text-amber-600",
      bg: "bg-amber-50 border-amber-200",
    },
    PROCESSED: {
      icon: <CheckCircle2 className="h-4 w-4 text-green-500" />,
      color: "text-green-700",
      bg: "bg-white border-slate-200",
    },
    FAILED: {
      icon: <AlertCircle className="h-4 w-4 text-red-500" />,
      color: "text-red-600",
      bg: "bg-red-50 border-red-200",
    },
    EMPTY: {
      icon: <AlertCircle className="h-4 w-4 text-amber-400" />,
      color: "text-amber-600",
      bg: "bg-amber-50 border-amber-200",
    },
    REVIEW_REQUIRED: {
      icon: <FileSearch className="h-4 w-4 text-amber-500" />,
      color: "text-amber-700",
      bg: "bg-amber-50 border-amber-200",
    },
  };

  const cfg = statusConfig[doc.status] ?? statusConfig.UPLOADED;

  return (
    <div className={`flex items-start gap-3 rounded-lg border px-3 py-3 text-sm ${cfg.bg}`}>
      <div className="mt-0.5 flex-shrink-0">{cfg.icon}</div>

      <div className="min-w-0 flex-1">
        <p className="truncate font-500 text-slate-800">{doc.file_name}</p>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-slate-500">
          <span className={`font-500 ${cfg.color}`}>{STATUS_LABELS[doc.status]}</span>
          <span className="text-slate-300">·</span>
          <span>{DOCUMENT_TYPE_LABELS[doc.document_type]}</span>
          {doc.page_count && (
            <>
              <span className="text-slate-300">·</span>
              <span>{doc.page_count} pages</span>
            </>
          )}
          {sizeMB && (
            <>
              <span className="text-slate-300">·</span>
              <span>{sizeMB} MB</span>
            </>
          )}
          {doc.classification_confidence !== null && doc.classification_confidence !== undefined && (
            <>
              <span className="text-slate-300">·</span>
              <span>{Math.round(doc.classification_confidence * 100)}% confidence</span>
            </>
          )}
        </div>

        {doc.status === "FAILED" && doc.processing_error && (
          <p className="mt-1 text-xs text-red-600">{doc.processing_error}</p>
        )}
        {doc.status === "REVIEW_REQUIRED" && (
          <p className="mt-1 text-xs text-amber-700">
            {doc.processing_error ?? "Scanned document detected — Claude Vision OCR ran but the result needs a clinician's review."}
          </p>
        )}
      </div>

      <div className="flex flex-shrink-0 items-center gap-1">
        {(doc.status === "PROCESSED" || doc.status === "REVIEW_REQUIRED") && onView && (
          <button
            onClick={() => onView(doc.id)}
            aria-label="View document"
            className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-blue-600"
            title="View extracted content"
          >
            <Eye className="h-4 w-4" />
          </button>
        )}
        {(doc.status === "FAILED" || doc.status === "EMPTY" || doc.status === "REVIEW_REQUIRED") && onRetry && (
          <button
            onClick={() => onRetry(doc.id)}
            aria-label="Retry processing"
            className="rounded p-1.5 text-slate-400 hover:bg-amber-50 hover:text-amber-600"
            title="Retry processing"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        )}
        {doc.status !== "PROCESSING" && onDelete && (
          <button
            onClick={() => onDelete(doc.id)}
            aria-label="Delete document"
            className="rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600"
            title="Delete document"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
