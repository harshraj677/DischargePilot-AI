"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Upload,
  Bot,
  FileText,
  ShieldCheck,
  ScrollText,
  Calendar,
  User,
  MapPin,
  Hash,
  Activity,
  Clock,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { DocumentStatusBadge, AgentStatusBadge, SummaryStatusBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { patients as patientsApi, agent as agentApi } from "@/lib/api";
import { formatDate, formatDateTime, formatRelativeTime } from "@/lib/utils";
import type { Patient, AgentRunSummary } from "@/lib/types";

export default function PatientDetailPage() {
  const { id: patientId } = useParams<{ id: string }>();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [runs, setRuns] = useState<AgentRunSummary[]>([]);
  const [loadingPatient, setLoadingPatient] = useState(true);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    patientsApi
      .get(patientId)
      .then(setPatient)
      .catch((err) => setError(err.message))
      .finally(() => setLoadingPatient(false));

    agentApi
      .listRuns(patientId)
      .then(setRuns)
      .catch(() => setRuns([]))
      .finally(() => setLoadingRuns(false));
  }, [patientId]);

  if (loadingPatient) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-slate-200" />
        <div className="h-40 animate-pulse rounded-xl bg-slate-200" />
      </div>
    );
  }

  if (error || !patient) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center text-sm text-red-600">
        {error ?? "Patient not found."}
      </div>
    );
  }

  const latestRun = runs[0] ?? null;
  const canRunAgent = patient.document_count > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${patient.first_name} ${patient.last_name}`}
        subtitle={`MRN: ${patient.mrn}`}
        breadcrumbs={[
          { label: "Patients", href: "/patients" },
          { label: `${patient.first_name} ${patient.last_name}` },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Link href={`/patients/${patientId}/upload`} className="btn-secondary">
              <Upload className="h-4 w-4" />
              Upload Documents
            </Link>
            {canRunAgent && (
              <Link href={`/patients/${patientId}/agent`} className="btn-primary">
                <Bot className="h-4 w-4" />
                Run Agent
              </Link>
            )}
          </div>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Patient Info */}
        <div className="lg:col-span-1 space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="mb-4 flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-medical-blue-100 text-lg font-bold text-medical-blue-600">
                {patient.first_name[0]}{patient.last_name[0]}
              </div>
              <div>
                <h2 className="font-semibold text-slate-900">{patient.first_name} {patient.last_name}</h2>
                {patient.summary_status && <SummaryStatusBadge status={patient.summary_status} />}
              </div>
            </div>

            <div className="space-y-2.5 text-sm">
              <InfoRow icon={<Hash className="h-3.5 w-3.5" />} label="MRN" value={patient.mrn} mono />
              {patient.date_of_birth && (
                <InfoRow icon={<Calendar className="h-3.5 w-3.5" />} label="DOB" value={formatDate(patient.date_of_birth)} />
              )}
              {patient.gender && (
                <InfoRow icon={<User className="h-3.5 w-3.5" />} label="Gender" value={patient.gender} />
              )}
              {patient.ward && (
                <InfoRow icon={<MapPin className="h-3.5 w-3.5" />} label="Ward" value={patient.ward} />
              )}
              {patient.attending_md && (
                <InfoRow icon={<User className="h-3.5 w-3.5" />} label="Attending" value={patient.attending_md} />
              )}
              {patient.admission_date && (
                <InfoRow icon={<Calendar className="h-3.5 w-3.5" />} label="Admitted" value={formatDate(patient.admission_date)} />
              )}
              {patient.discharge_date && (
                <InfoRow icon={<Calendar className="h-3.5 w-3.5" />} label="Discharged" value={formatDate(patient.discharge_date)} />
              )}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Quick Actions</h3>
            <div className="space-y-2">
              <Link
                href={`/patients/${patientId}/upload`}
                className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
              >
                <Upload className="h-4 w-4 text-slate-400" />
                Upload Documents
              </Link>
              <Link
                href={`/patients/${patientId}/agent`}
                className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
              >
                <Bot className="h-4 w-4 text-slate-400" />
                Agent Execution Center
              </Link>
              {latestRun && (
                <>
                  <Link
                    href={`/patients/${patientId}/trace?run_id=${latestRun.run_id}`}
                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <Activity className="h-4 w-4 text-slate-400" />
                    View Trace
                  </Link>
                  <Link
                    href={`/patients/${patientId}/safety?run_id=${latestRun.run_id}`}
                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <ShieldCheck className="h-4 w-4 text-slate-400" />
                    Safety Review
                  </Link>
                  <Link
                    href={`/patients/${patientId}/summary?run_id=${latestRun.run_id}`}
                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <ScrollText className="h-4 w-4 text-slate-400" />
                    View Summary
                  </Link>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="lg:col-span-2 space-y-4">
          {/* Documents */}
          <div className="rounded-xl border border-slate-200 bg-white">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-slate-400" />
                <h3 className="text-sm font-semibold text-slate-900">Documents</h3>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                  {patient.document_count}
                </span>
              </div>
              <Link href={`/patients/${patientId}/upload`} className="btn-ghost text-xs py-1.5 px-2.5 h-auto">
                <Upload className="h-3.5 w-3.5" />
                Upload
              </Link>
            </div>
            {patient.documents.length === 0 ? (
              <EmptyState
                icon={<FileText className="h-6 w-6" />}
                title="No documents yet"
                description="Upload clinical documents to enable AI summary generation."
                action={
                  <Link href={`/patients/${patientId}/upload`} className="btn-primary text-xs py-1.5">
                    <Upload className="h-3.5 w-3.5" />
                    Upload Documents
                  </Link>
                }
              />
            ) : (
              <div className="divide-y divide-slate-50">
                {patient.documents.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between px-5 py-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <FileText className="h-4 w-4 flex-shrink-0 text-slate-400" />
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-700">{doc.file_name}</p>
                        <p className="text-xs text-slate-400">
                          {doc.document_type.replace("_", " ")} · {doc.page_count ?? "?"} pages
                        </p>
                      </div>
                    </div>
                    <DocumentStatusBadge status={doc.status} />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Agent Runs */}
          <div className="rounded-xl border border-slate-200 bg-white">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
              <div className="flex items-center gap-2">
                <Bot className="h-4 w-4 text-slate-400" />
                <h3 className="text-sm font-semibold text-slate-900">Agent Runs</h3>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                  {runs.length}
                </span>
              </div>
              <Link href={`/patients/${patientId}/agent`} className="btn-ghost text-xs py-1.5 px-2.5 h-auto">
                <Bot className="h-3.5 w-3.5" />
                New Run
              </Link>
            </div>
            {loadingRuns ? (
              <div className="p-4 space-y-2">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-10 animate-pulse rounded bg-slate-100" />
                ))}
              </div>
            ) : runs.length === 0 ? (
              <EmptyState
                icon={<Bot className="h-6 w-6" />}
                title="No agent runs yet"
                description="Run the AI agent to generate a discharge summary."
              />
            ) : (
              <div className="divide-y divide-slate-50">
                {runs.map((run) => (
                  <div key={run.run_id} className="flex items-center justify-between px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <AgentStatusBadge status={run.status} />
                          {run.completeness_score != null && (
                            <span className="text-xs text-slate-400">
                              Completeness: {Math.round(run.completeness_score * 100)}%
                            </span>
                          )}
                        </div>
                        <div className="mt-0.5 flex items-center gap-3 text-xs text-slate-400">
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatRelativeTime(run.created_at)}
                          </span>
                          <span>{run.iteration_count} iterations</span>
                          <span>{run.total_tokens.toLocaleString()} tokens</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {(run.status === "COMPLETED" || run.status === "ESCALATED") && (
                        <>
                          <Link
                            href={`/patients/${patientId}/safety?run_id=${run.run_id}`}
                            className="text-xs font-medium text-medical-blue-600 hover:text-medical-blue-700"
                          >
                            Safety
                          </Link>
                          <Link
                            href={`/patients/${patientId}/summary?run_id=${run.run_id}`}
                            className="text-xs font-medium text-medical-blue-600 hover:text-medical-blue-700"
                          >
                            Summary
                          </Link>
                        </>
                      )}
                      <Link
                        href={`/patients/${patientId}/trace?run_id=${run.run_id}`}
                        className="text-xs font-medium text-slate-500 hover:text-slate-700"
                      >
                        Trace
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoRow({ icon, label, value, mono = false }: { icon: React.ReactNode; label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start gap-2">
      <span className="mt-0.5 flex-shrink-0 text-slate-400">{icon}</span>
      <span className="w-20 flex-shrink-0 text-xs text-slate-400">{label}</span>
      <span className={`text-slate-700 ${mono ? "font-mono text-xs" : ""}`}>{value}</span>
    </div>
  );
}
