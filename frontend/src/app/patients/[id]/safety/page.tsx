"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  AlertTriangle,
  Info,
  CheckCircle2,
  XCircle,
  ScrollText,
  Loader2,
  ChevronRight,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { SeverityBadge, SafetyStatusBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { summary as summaryApi, patients as patientsApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Patient, SafetyReportResponse, FlagSeverity, SafetyStatus } from "@/lib/types";

const severityOrder: Record<FlagSeverity, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
  INFO: 4,
};

const statusConfig: Record<SafetyStatus, { icon: React.ReactNode; label: string; color: string; bg: string }> = {
  APPROVED: {
    icon: <ShieldCheck className="h-6 w-6" />,
    label: "Approved for Generation",
    color: "text-clinical-green-700",
    bg: "bg-clinical-green-50 border-clinical-green-200",
  },
  REVIEW_REQUIRED: {
    icon: <ShieldAlert className="h-6 w-6" />,
    label: "Review Required",
    color: "text-amber-700",
    bg: "bg-amber-50 border-amber-200",
  },
  BLOCKED: {
    icon: <ShieldX className="h-6 w-6" />,
    label: "Summary Blocked",
    color: "text-red-700",
    bg: "bg-red-50 border-red-200",
  },
};

function ScoreGauge({ score, label }: { score: number; label: string }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.8 ? "#059669" : score >= 0.6 ? "#d97706" : "#dc2626";
  const circumference = 2 * Math.PI * 40;
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative">
        <svg width="100" height="100" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" fill="none" stroke="#e2e8f0" strokeWidth="8" />
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform="rotate(-90 50 50)"
            style={{ transition: "stroke-dashoffset 1s ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-slate-900">{pct}</span>
          <span className="text-xs text-slate-400">%</span>
        </div>
      </div>
      <p className="text-xs font-medium text-slate-500">{label}</p>
    </div>
  );
}

export default function SafetyPage() {
  const { id: patientId } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const runId = searchParams.get("run_id");

  const [patient, setPatient] = useState<Patient | null>(null);
  const [report, setReport] = useState<SafetyReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  useEffect(() => {
    patientsApi.get(patientId).then(setPatient).catch(() => null);
  }, [patientId]);

  useEffect(() => {
    if (!runId) {
      setError("No run_id in URL. Navigate from the patient detail page.");
      setLoading(false);
      return;
    }
    summaryApi
      .getSafetyReport(patientId, runId)
      .then(setReport)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [patientId, runId]);

  async function handleGenerate() {
    if (!runId) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      await summaryApi.generate(patientId, runId);
      router.push(`/patients/${patientId}/summary?run_id=${runId}`);
    } catch (err: unknown) {
      setGenerateError(err instanceof Error ? err.message : "Generation failed");
      setGenerating(false);
    }
  }

  const statusCfg = report ? statusConfig[report.overall_status as SafetyStatus] : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Safety Review Center"
        subtitle="Clinical safety validation before summary generation"
        breadcrumbs={[
          { label: "Patients", href: "/patients" },
          {
            label: patient ? `${patient.first_name} ${patient.last_name}` : "Patient",
            href: `/patients/${patientId}`,
          },
          { label: "Safety Review" },
        ]}
      />

      {loading ? (
        <div className="space-y-4">
          <div className="h-32 animate-pulse rounded-xl bg-slate-100" />
          <div className="h-48 animate-pulse rounded-xl bg-slate-100" />
        </div>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-600">
          {error}
        </div>
      ) : !report ? (
        <EmptyState
          icon={<ShieldCheck className="h-8 w-8" />}
          title="No safety report available"
          description="Run the agent first to generate a safety report."
        />
      ) : (
        <>
          {/* Status Banner */}
          <div className={cn("rounded-xl border p-5", statusCfg!.bg)}>
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className={cn("flex h-12 w-12 items-center justify-center rounded-full", statusCfg!.bg.split(" ")[0])}>
                  <span className={statusCfg!.color}>{statusCfg!.icon}</span>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className={cn("text-lg font-bold", statusCfg!.color)}>{statusCfg!.label}</h2>
                    <SafetyStatusBadge status={report.overall_status as SafetyStatus} />
                  </div>
                  <p className="mt-0.5 text-sm text-slate-600">
                    {report.flag_count} flag{report.flag_count !== 1 ? "s" : ""} found
                    {report.critical_flag_count > 0 && (
                      <span className="ml-1 font-medium text-red-600">
                        · {report.critical_flag_count} critical
                      </span>
                    )}
                  </p>
                </div>
              </div>

              {/* Gauges */}
              <div className="flex items-center gap-8">
                <ScoreGauge score={report.safety_score} label="Safety Score" />
                <ScoreGauge score={report.completeness_score} label="Completeness" />
              </div>
            </div>
          </div>

          {/* Blocking Issues */}
          {report.blocking_issues.length > 0 && (
            <div className="rounded-xl border-2 border-red-300 bg-red-50 p-5">
              <div className="mb-3 flex items-center gap-2">
                <ShieldX className="h-5 w-5 text-red-600" />
                <h3 className="font-semibold text-red-700">Blocking Issues — Summary Cannot Be Generated</h3>
              </div>
              <ul className="space-y-2">
                {report.blocking_issues.map((issue, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-red-700">
                    <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500" />
                    {issue}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Warnings */}
          {report.warnings.length > 0 && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
              <div className="mb-3 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-600" />
                <h3 className="font-semibold text-amber-700">Warnings</h3>
              </div>
              <ul className="space-y-1">
                {report.warnings.map((w, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-amber-700">
                    <ChevronRight className="mt-0.5 h-4 w-4 flex-shrink-0" />
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Generate Summary */}
          {report.can_generate_summary && (
            <div className="rounded-xl border border-clinical-green-200 bg-clinical-green-50 p-5">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="h-6 w-6 text-clinical-green-600" />
                  <div>
                    <p className="font-semibold text-clinical-green-800">Ready to Generate Summary</p>
                    <p className="text-sm text-clinical-green-700">
                      Safety validation passed. You can now generate the discharge summary.
                    </p>
                  </div>
                </div>
                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  className="flex-shrink-0 btn-primary bg-clinical-green-600 hover:bg-clinical-green-700"
                >
                  {generating ? (
                    <><Loader2 className="h-4 w-4 animate-spin" /> Generating...</>
                  ) : (
                    <><ScrollText className="h-4 w-4" /> Generate Summary</>
                  )}
                </button>
              </div>
              {generateError && (
                <div className="mt-3 rounded-lg bg-red-100 px-4 py-2.5 text-sm text-red-700">
                  {generateError}
                </div>
              )}
            </div>
          )}

          {/* Already have summary link */}
          {runId && (
            <div className="flex items-center justify-end">
              <Link
                href={`/patients/${patientId}/summary?run_id=${runId}`}
                className="flex items-center gap-1.5 text-sm font-medium text-medical-blue-600 hover:text-medical-blue-700"
              >
                <ScrollText className="h-4 w-4" />
                View Existing Summary
              </Link>
            </div>
          )}

          {/* Safety Info Cards */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
              <p className="text-2xl font-bold text-slate-900">{report.flag_count}</p>
              <p className="text-xs text-slate-400 mt-0.5">Total Flags</p>
            </div>
            <div className={cn("rounded-xl border p-4 text-center", report.critical_flag_count > 0 ? "border-red-200 bg-red-50" : "border-slate-200 bg-white")}>
              <p className={cn("text-2xl font-bold", report.critical_flag_count > 0 ? "text-red-700" : "text-slate-900")}>
                {report.critical_flag_count}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">Critical</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
              <p className="text-2xl font-bold text-slate-900">{report.blocking_issues.length}</p>
              <p className="text-xs text-slate-400 mt-0.5">Blocking</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
              <p className="text-2xl font-bold text-slate-900">{report.warnings.length}</p>
              <p className="text-xs text-slate-400 mt-0.5">Warnings</p>
            </div>
          </div>

          <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 flex items-start gap-2">
            <Info className="h-4 w-4 flex-shrink-0 text-slate-400 mt-0.5" />
            <p className="text-xs text-slate-500 leading-relaxed">
              Safety validation checks for medication interactions, diagnostic conflicts, missing critical information, and documentation quality.
              Detailed review flags with recommendations are shown in the summary view.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
