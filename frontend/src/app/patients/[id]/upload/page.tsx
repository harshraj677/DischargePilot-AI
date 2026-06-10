"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Bot, FileText, CheckCircle2, Info } from "lucide-react";
import { DropZone } from "@/components/upload/DropZone";
import { DocumentTypeSelector } from "@/components/upload/DocumentTypeSelector";
import { UploadingFileCard, DocumentCard } from "@/components/upload/DocumentCard";
import { ProcessingStatusBar } from "@/components/upload/ProcessingStatusBar";
import { useDocumentUpload, useProcessingStatus, useDocumentList } from "@/hooks/useDocuments";
import { patients as patientsApi } from "@/lib/api";
import type { Patient, DocumentType, UploadingFile } from "@/lib/types";

const REQUIRED_DOC_TYPES = [
  { type: "admission_note" as DocumentType, label: "Admission Note" },
  { type: "progress_note" as DocumentType, label: "Progress Notes (≥1)" },
  { type: "lab_report" as DocumentType, label: "Lab Reports" },
  { type: "medication_record" as DocumentType, label: "Medication Record" },
];

export default function UploadPage() {
  const { id: patientId } = useParams<{ id: string }>();
  const router = useRouter();

  const [patient, setPatient] = useState<Patient | null>(null);
  const [loadingPatient, setLoadingPatient] = useState(true);
  const [declaredType, setDeclaredType] = useState<DocumentType | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const { uploadingFiles, addFiles, uploadAll, removeFile } = useDocumentUpload(patientId);
  const { docs, loading: docsLoading, fetch: fetchDocs, deleteDoc, retryDoc } = useDocumentList(patientId);
  const { status, startPolling, stopPolling, refresh } = useProcessingStatus(patientId, false);

  useEffect(() => {
    patientsApi.get(patientId).then(setPatient).catch(console.error).finally(() => setLoadingPatient(false));
    fetchDocs();
  }, [patientId]);

  useEffect(() => {
    if (docs.some((d) => d.status === "PROCESSING" || d.status === "UPLOADED")) {
      startPolling();
    } else {
      stopPolling();
    }
    return () => stopPolling();
  }, [docs]);

  const handleFilesSelected = useCallback(
    (files: File[]) => {
      addFiles(files, declaredType);
    },
    [addFiles, declaredType]
  );

  const handleUploadAll = useCallback(async () => {
    const pending = uploadingFiles.filter((f) => f.uploadState === "idle");
    if (pending.length === 0) return;
    setIsUploading(true);
    await uploadAll(pending);
    setIsUploading(false);
    await fetchDocs();
    startPolling();
  }, [uploadingFiles, uploadAll, fetchDocs, startPolling]);

  const presentTypes = new Set(docs.map((d) => d.document_type));
  const allReady = status?.all_ready ?? false;
  const hasPending = uploadingFiles.some((f) => f.uploadState === "idle");

  if (loadingPatient) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-slate-400">
        Loading patient…
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-red-500">
        Patient not found.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
        <span className="text-slate-300">/</span>
        <span className="text-sm font-500 text-slate-700">
          {patient.first_name} {patient.last_name}
        </span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
          {patient.mrn}
        </span>
      </div>

      <h1 className="text-xl font-700 text-slate-900">Upload Clinical Documents (PDF / Image)</h1>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main Upload Panel */}
        <div className="space-y-4 lg:col-span-2">
          {/* Document type declaration */}
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <DocumentTypeSelector
              value={declaredType}
              onChange={setDeclaredType}
              disabled={isUploading}
            />
          </div>

          {/* Drop zone */}
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-600 text-slate-700">Upload Files</h2>
            <DropZone onFilesSelected={handleFilesSelected} disabled={isUploading} />
          </div>

          {/* Pending uploads */}
          {uploadingFiles.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-600 text-slate-700">
                  Files to Upload ({uploadingFiles.length})
                </h2>
                {hasPending && (
                  <button
                    onClick={handleUploadAll}
                    disabled={isUploading}
                    className="rounded-md bg-blue-600 px-4 py-1.5 text-xs font-500 text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {isUploading ? "Uploading…" : "Upload All"}
                  </button>
                )}
              </div>
              <div className="space-y-2">
                {uploadingFiles.map((entry) => (
                  <UploadingFileCard
                    key={entry.id}
                    entry={entry}
                    onRemove={removeFile}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Uploaded documents */}
          {docs.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-sm font-600 text-slate-700">
                Uploaded Documents ({docs.length})
              </h2>
              <div className="space-y-2">
                {docs.map((doc) => (
                  <DocumentCard
                    key={doc.id}
                    doc={doc}
                    onDelete={deleteDoc}
                    onRetry={retryDoc}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Processing status */}
          {docs.length > 0 && (
            <ProcessingStatusBar status={status} loading={docsLoading} />
          )}
        </div>

        {/* Right Sidebar */}
        <div className="space-y-4">
          {/* Patient summary */}
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-xs font-600 uppercase tracking-wide text-slate-500">
              Patient Details
            </h2>
            <div className="space-y-2 text-sm">
              <Row label="Name" value={`${patient.first_name} ${patient.last_name}`} />
              <Row label="MRN" value={patient.mrn} mono />
              {patient.date_of_birth && <Row label="DOB" value={patient.date_of_birth} />}
              {patient.gender && <Row label="Gender" value={patient.gender} />}
              {patient.ward && <Row label="Ward" value={patient.ward} />}
              {patient.attending_md && <Row label="Attending" value={patient.attending_md} />}
            </div>
          </div>

          {/* Document checklist */}
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-xs font-600 uppercase tracking-wide text-slate-500">
              Document Checklist
            </h2>
            <div className="space-y-2">
              {REQUIRED_DOC_TYPES.map(({ type, label }) => {
                const present = presentTypes.has(type);
                return (
                  <div key={type} className="flex items-center gap-2 text-sm">
                    {present ? (
                      <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-green-500" />
                    ) : (
                      <div className="h-4 w-4 flex-shrink-0 rounded-full border-2 border-slate-200" />
                    )}
                    <span className={present ? "text-slate-700" : "text-slate-400"}>{label}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Agent CTA */}
          <div className={[
            "rounded-lg border p-4 shadow-sm",
            allReady ? "border-green-200 bg-green-50" : "border-slate-200 bg-slate-50",
          ].join(" ")}>
            <h2 className="mb-1 text-xs font-600 uppercase tracking-wide text-slate-500">
              Agent Status
            </h2>
            {allReady ? (
              <>
                <p className="mb-3 text-sm text-green-700">
                  All documents processed. Ready to generate summary.
                </p>
                <button
                  onClick={() => router.push(`/patients/${patientId}/agent`)}
                  className="flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-4 py-2.5 text-sm font-500 text-white hover:bg-blue-700"
                >
                  <Bot className="h-4 w-4" />
                  Generate Discharge Summary
                </button>
              </>
            ) : (
              <p className="text-sm text-slate-500">
                {docs.length === 0
                  ? "Upload at least one clinical document to begin."
                  : "Upload and process all required documents to enable summary generation."}
              </p>
            )}
          </div>

          {/* Info */}
          <div className="flex gap-2 rounded-lg border border-blue-100 bg-blue-50 p-3">
            <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-500" />
            <p className="text-xs text-blue-700 leading-relaxed">
              Declaring the document type before uploading improves classification accuracy
              and reduces processing time. Auto-detection uses keyword analysis.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start gap-2">
      <span className="w-20 flex-shrink-0 text-xs text-slate-400">{label}</span>
      <span className={`text-slate-700 ${mono ? "font-mono text-xs" : ""}`}>{value}</span>
    </div>
  );
}
