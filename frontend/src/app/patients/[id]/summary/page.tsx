"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import {
  ScrollText,
  CheckCircle2,
  XCircle,
  Download,
  AlertTriangle,
  Shield,
  Loader2,
  Info,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { SeverityBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { summary as summaryApi, patients as patientsApi } from "@/lib/api";
import { formatDateTime, cn } from "@/lib/utils";
import type { Patient, SummaryResponse, ReviewFlag, FlagSeverity, SummaryReviewStatus } from "@/lib/types";

const STATUS_CONFIG: Record<SummaryReviewStatus, { label: string; color: string; bg: string }> = {
  PENDING_REVIEW: { label: "Pending Review", color: "text-amber-700", bg: "bg-amber-50 border-amber-200" },
  IN_REVIEW: { label: "In Review", color: "text-blue-700", bg: "bg-blue-50 border-blue-200" },
  APPROVED: { label: "Approved", color: "text-clinical-green-700", bg: "bg-clinical-green-50 border-clinical-green-200" },
  REJECTED: { label: "Rejected", color: "text-red-700", bg: "bg-red-50 border-red-200" },
  ESCALATED: { label: "Escalated", color: "text-orange-700", bg: "bg-orange-50 border-orange-200" },
};

const SECTION_FLAG_COLORS: Record<FlagSeverity, string> = {
  CRITICAL: "border-l-4 border-l-red-500 bg-red-50",
  HIGH: "border-l-4 border-l-orange-400 bg-orange-50",
  MEDIUM: "border-l-4 border-l-yellow-400 bg-yellow-50",
  LOW: "border-l-4 border-l-sky-400 bg-sky-50",
  INFO: "border-l-4 border-l-blue-400 bg-blue-50",
};

function FlagCard({ flag }: { flag: ReviewFlag }) {
  const [expanded, setExpanded] = useState(flag.severity === "CRITICAL" || flag.severity === "HIGH");

  return (
    <div className={cn("rounded-r-lg py-2.5 px-3 mb-2", SECTION_FLAG_COLORS[flag.severity])}>
      <button
        className="flex w-full items-center justify-between text-left gap-2"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex items-center gap-2">
          <SeverityBadge severity={flag.severity} />
          <span className="text-xs font-medium text-slate-700">{flag.category.replace(/_/g, " ")}</span>
          {flag.requires_acknowledgment && (
            <span className="rounded-full bg-red-200 px-1.5 py-0.5 text-[10px] font-semibold text-red-700">
              ACK REQUIRED
            </span>
          )}
        </div>
        {expanded ? <ChevronUp className="h-3.5 w-3.5 text-slate-400" /> : <ChevronDown className="h-3.5 w-3.5 text-slate-400" />}
      </button>
      {expanded && (
        <div className="mt-2 space-y-1">
          <p className="text-xs text-slate-700 leading-relaxed">{flag.description}</p>
          {flag.recommendation && (
            <p className="text-xs text-slate-500 italic">
              <span className="font-medium not-italic">Recommendation:</span> {flag.recommendation}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function SectionBlock({ section, flags }: { section: { name: string; content: string; status: string; flag_count: number }; flags: ReviewFlag[] }) {
  const [collapsed, setCollapsed] = useState(false);
  const sectionFlags = flags.filter((f) => f.section.toLowerCase() === section.name.toLowerCase());
  const hasFlags = sectionFlags.length > 0;
  const hasCritical = sectionFlags.some((f) => f.severity === "CRITICAL");

  return (
    <div className={cn(
      "rounded-xl border bg-white",
      hasCritical ? "border-red-200" : hasFlags ? "border-amber-100" : "border-slate-200"
    )}>
      <button
        className="flex w-full items-center justify-between px-5 py-3.5 text-left"
        onClick={() => setCollapsed((v) => !v)}
      >
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-900 capitalize">
            {section.name.replace(/_/g, " ")}
          </h3>
          {hasFlags && (
            <span className={cn(
              "rounded-full px-2 py-0.5 text-xs font-medium",
              hasCritical ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"
            )}>
              {sectionFlags.length} flag{sectionFlags.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        {collapsed ? <ChevronDown className="h-4 w-4 text-slate-400" /> : <ChevronUp className="h-4 w-4 text-slate-400" />}
      </button>

      {!collapsed && (
        <div className="border-t border-slate-100 px-5 pb-5 pt-4">
          {sectionFlags.length > 0 && (
            <div className="mb-4">
              {sectionFlags.map((flag) => (
                <FlagCard key={flag.flag_id} flag={flag} />
              ))}
            </div>
          )}
          <div className="prose prose-sm max-w-none text-slate-700 leading-relaxed whitespace-pre-wrap text-sm">
            {section.content || <span className="text-slate-400 italic">No content available.</span>}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SummaryPage() {
  const { id: patientId } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const runId = searchParams.get("run_id");

  const [patient, setPatient] = useState<Patient | null>(null);
  const [summaryData, setSummaryData] = useState<SummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [approver, setApprover] = useState("");
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    patientsApi.get(patientId).then(setPatient).catch(() => null);
  }, [patientId]);

  useEffect(() => {
    if (!runId) {
      setError("No run_id in URL.");
      setLoading(false);
      return;
    }
    summaryApi
      .getSummary(patientId, runId)
      .then(setSummaryData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [patientId, runId]);

  async function handleApprove() {
    if (!runId || !approver.trim()) return;
    setApproving(true);
    setActionError(null);
    try {
      await summaryApi.approve(patientId, runId, approver.trim());
      const updated = await summaryApi.getSummary(patientId, runId);
      setSummaryData(updated);
      setShowApproveModal(false);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setApproving(false);
    }
  }

  async function handleReject() {
    if (!runId || !rejectReason.trim()) return;
    setRejecting(true);
    setActionError(null);
    try {
      await summaryApi.reject(patientId, runId, rejectReason.trim());
      const updated = await summaryApi.getSummary(patientId, runId);
      setSummaryData(updated);
      setShowRejectModal(false);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Rejection failed");
    } finally {
      setRejecting(false);
    }
  }

  async function handleDownload() {
    if (!runId) return;
    setDownloading(true);
    try {
      const res = await summaryApi.getSummaryText(patientId, runId);
      const blob = new Blob([res.text], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `discharge-summary-${patientId}-${runId.slice(0, 8)}.txt`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // silently fail
    } finally {
      setDownloading(false);
    }
  }

  const statusCfg = summaryData ? STATUS_CONFIG[summaryData.status] : null;
  const requiresAck = summaryData?.requires_acknowledgment_count ?? 0;
  const canApprove = summaryData?.status === "PENDING_REVIEW" || summaryData?.status === "IN_REVIEW";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Discharge Summary"
        subtitle={patient ? `${patient.first_name} ${patient.last_name} · MRN: ${patient.mrn}` : "Loading..."}
        breadcrumbs={[
          { label: "Patients", href: "/patients" },
          {
            label: patient ? `${patient.first_name} ${patient.last_name}` : "Patient",
            href: `/patients/${patientId}`,
          },
          { label: "Summary" },
        ]}
        actions={
          summaryData && (
            <div className="flex items-center gap-2">
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="btn-secondary"
              >
                {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                Download Text
              </button>
              {canApprove && (
                <>
                  <button onClick={() => setShowRejectModal(true)} className="btn-secondary text-red-600 border-red-200 hover:bg-red-50">
                    <XCircle className="h-4 w-4" />
                    Reject
                  </button>
                  <button onClick={() => setShowApproveModal(true)} className="btn-primary bg-clinical-green-600 hover:bg-clinical-green-700">
                    <CheckCircle2 className="h-4 w-4" />
                    Approve
                  </button>
                </>
              )}
            </div>
          )
        }
      />

      {loading ? (
        <div className="space-y-4">
          <div className="h-20 animate-pulse rounded-xl bg-slate-100" />
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-xl bg-slate-100" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-600">
          {error}
        </div>
      ) : !summaryData ? (
        <EmptyState
          icon={<ScrollText className="h-8 w-8" />}
          title="No summary found"
          description="Generate a summary from the Safety Review page first."
        />
      ) : (
        <>
          {/* Status Banner */}
          <div className={cn("rounded-xl border p-4", statusCfg!.bg)}>
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <Shield className={cn("h-5 w-5", statusCfg!.color)} />
                <div>
                  <span className={cn("font-semibold", statusCfg!.color)}>{statusCfg!.label}</span>
                  <span className="ml-2 text-xs text-slate-500">
                    Generated {formatDateTime(summaryData.generated_at)}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-4 text-xs text-slate-500">
                <span>Safety: {Math.round(summaryData.safety_score * 100)}%</span>
                <span>Completeness: {Math.round(summaryData.completeness_score * 100)}%</span>
                <span className="flex items-center gap-1">
                  {summaryData.total_flags} flag{summaryData.total_flags !== 1 ? "s" : ""}
                </span>
              </div>
            </div>

            {/* Safety score bar */}
            <div className="mt-3">
              <div className="flex items-center justify-between mb-1 text-xs">
                <span className="text-slate-500">Overall Safety Score</span>
                <span className={cn("font-medium", statusCfg!.color)}>
                  {Math.round(summaryData.safety_score * 100)}%
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-white/50">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    summaryData.safety_score >= 0.8 ? "bg-clinical-green-500" :
                    summaryData.safety_score >= 0.6 ? "bg-amber-500" : "bg-red-500"
                  )}
                  style={{ width: `${summaryData.safety_score * 100}%` }}
                />
              </div>
            </div>
          </div>

          {/* Acknowledgment Warning */}
          {requiresAck > 0 && (
            <div className="flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-5 py-3.5">
              <AlertTriangle className="h-5 w-5 flex-shrink-0 text-amber-600" />
              <div>
                <p className="text-sm font-semibold text-amber-800">
                  {requiresAck} flag{requiresAck !== 1 ? "s" : ""} require acknowledgment before approval
                </p>
                <p className="text-xs text-amber-600">
                  Review all flags marked "ACK REQUIRED" in the sections below.
                </p>
              </div>
            </div>
          )}

          {actionError && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-3 text-sm text-red-700">
              {actionError}
            </div>
          )}

          {/* Summary Sections */}
          <div className="space-y-3">
            {summaryData.sections.map((section) => (
              <SectionBlock
                key={section.name}
                section={section}
                flags={summaryData.review_flags}
              />
            ))}
          </div>

          {/* All Flags Summary */}
          {summaryData.review_flags.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <h3 className="text-sm font-semibold text-slate-900">
                  All Review Flags ({summaryData.review_flags.length})
                </h3>
              </div>
              <div className="space-y-2">
                {summaryData.review_flags
                  .sort((a, b) => {
                    const severityMap: Record<FlagSeverity, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, INFO: 4 };
                    return severityMap[a.severity] - severityMap[b.severity];
                  })
                  .map((flag) => (
                    <FlagCard key={flag.flag_id} flag={flag} />
                  ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Approve Modal */}
      {showApproveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h2 className="mb-3 text-base font-semibold text-slate-900">Approve Summary</h2>
            <p className="mb-4 text-sm text-slate-500">
              Enter your name to approve this discharge summary. This action is logged.
            </p>
            <input
              className="input mb-4"
              placeholder="Your name (e.g. Dr. Jane Smith)"
              value={approver}
              onChange={(e) => setApprover(e.target.value)}
            />
            <div className="flex justify-end gap-3">
              <button onClick={() => setShowApproveModal(false)} className="btn-secondary">Cancel</button>
              <button
                onClick={handleApprove}
                disabled={approving || !approver.trim()}
                className="btn-primary bg-clinical-green-600 hover:bg-clinical-green-700"
              >
                {approving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                Approve
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h2 className="mb-3 text-base font-semibold text-slate-900">Reject Summary</h2>
            <p className="mb-4 text-sm text-slate-500">
              Provide a reason for rejection. This will be logged and used to improve future generations.
            </p>
            <textarea
              className="input min-h-[100px] resize-none"
              placeholder="e.g. Missing follow-up instructions, incorrect medication doses..."
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
            />
            <div className="mt-4 flex justify-end gap-3">
              <button onClick={() => setShowRejectModal(false)} className="btn-secondary">Cancel</button>
              <button
                onClick={handleReject}
                disabled={rejecting || !rejectReason.trim()}
                className="btn-danger"
              >
                {rejecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                Reject
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
