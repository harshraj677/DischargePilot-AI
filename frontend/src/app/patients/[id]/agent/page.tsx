"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Bot,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  Zap,
  AlertTriangle,
  ShieldCheck,
  ScrollText,
  Activity,
  Loader2,
  ChevronRight,
  Stethoscope,
  Pill,
  FlaskConical,
  ClipboardList,
  Brain,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { AgentStatusBadge } from "@/components/ui/Badge";
import { patients as patientsApi, agent as agentApi } from "@/lib/api";
import { formatRelativeTime, formatScore } from "@/lib/utils";
import type { Patient, AgentRunSummary, AgentRunDetail } from "@/lib/types";

const TOOL_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  diagnosis_extractor: { label: "Diagnosis Extractor", icon: <Stethoscope className="h-4 w-4" />, color: "text-blue-600 bg-blue-100" },
  medication_extractor: { label: "Medication Extractor", icon: <Pill className="h-4 w-4" />, color: "text-purple-600 bg-purple-100" },
  lab_extractor: { label: "Lab Extractor", icon: <FlaskConical className="h-4 w-4" />, color: "text-green-600 bg-green-100" },
  admission_note_reader: { label: "Admission Note Reader", icon: <ClipboardList className="h-4 w-4" />, color: "text-amber-600 bg-amber-100" },
  completeness_checker: { label: "Completeness Checker", icon: <CheckCircle2 className="h-4 w-4" />, color: "text-clinical-green-600 bg-clinical-green-100" },
  conflict_detector: { label: "Conflict Detector", icon: <AlertTriangle className="h-4 w-4" />, color: "text-red-600 bg-red-100" },
  knowledge_synthesizer: { label: "Knowledge Synthesizer", icon: <Brain className="h-4 w-4" />, color: "text-indigo-600 bg-indigo-100" },
};

function getToolMeta(toolName: string | undefined) {
  if (!toolName || typeof toolName !== 'string') {
    return { label: "Unknown Tool", icon: <Zap className="h-4 w-4" />, color: "text-slate-600 bg-slate-100" };
  }
  const key = Object.keys(TOOL_META).find((k) => toolName.toLowerCase().includes(k.toLowerCase()));
  return key ? TOOL_META[key] : { label: toolName, icon: <Zap className="h-4 w-4" />, color: "text-slate-600 bg-slate-100" };
}

const RUNNING_MESSAGES = [
  "Parsing admission notes...",
  "Extracting diagnoses from clinical records...",
  "Analyzing medication records for interactions...",
  "Processing lab results and trends...",
  "Cross-referencing clinical findings...",
  "Computing completeness score...",
  "Running conflict detection...",
  "Synthesizing knowledge base...",
  "Finalizing clinical summary data...",
];

export default function AgentPage() {
  const { id: patientId } = useParams<{ id: string }>();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [runs, setRuns] = useState<AgentRunSummary[]>([]);
  const [activeRun, setActiveRun] = useState<AgentRunDetail | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progressMessage, setProgressMessage] = useState(RUNNING_MESSAGES[0]);
  const [messageIndex, setMessageIndex] = useState(0);
  const pollRef = useRef<NodeJS.Timeout | null>(null);
  const msgRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    patientsApi.get(patientId).then(setPatient).catch(() => null);
    agentApi.listRuns(patientId).then(setRuns).catch(() => null);
  }, [patientId]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (msgRef.current) clearInterval(msgRef.current);
    };
  }, []);

  function startMessageCycling() {
    let idx = 0;
    msgRef.current = setInterval(() => {
      idx = (idx + 1) % RUNNING_MESSAGES.length;
      setMessageIndex(idx);
      setProgressMessage(RUNNING_MESSAGES[idx]);
    }, 2500);
  }

  function stopMessageCycling() {
    if (msgRef.current) {
      clearInterval(msgRef.current);
      msgRef.current = null;
    }
  }

  function startPolling(runId: string) {
    setIsPolling(true);
    pollRef.current = setInterval(async () => {
      try {
        const detail = await agentApi.getRun(runId);
        setActiveRun(detail);
        if (
          detail.status === "COMPLETED" ||
          detail.status === "FAILED" ||
          detail.status === "TIMED_OUT" ||
          detail.status === "ESCALATED"
        ) {
          if (pollRef.current) clearInterval(pollRef.current);
          setIsPolling(false);
          stopMessageCycling();
          agentApi.listRuns(patientId).then(setRuns).catch(() => null);
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current);
        setIsPolling(false);
        stopMessageCycling();
      }
    }, 2000);
  }

  async function handleStartRun() {
    setError(null);
    setIsStarting(true);
    try {
      const res = await agentApi.startRun(patientId);
      const detail = await agentApi.getRun(res.run_id);
      setActiveRun(detail);
      if (detail.status === "RUNNING" || detail.status === "PENDING") {
        startMessageCycling();
        startPolling(res.run_id);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start agent run");
    } finally {
      setIsStarting(false);
    }
  }

  const isRunning = isPolling || activeRun?.status === "RUNNING" || activeRun?.status === "PENDING";
  const isComplete = activeRun?.status === "COMPLETED" || activeRun?.status === "ESCALATED";
  const isFailed = activeRun?.status === "FAILED" || activeRun?.status === "TIMED_OUT";

  const traceSteps = activeRun?.trace ?? [];
  const completeness = activeRun?.completeness_score ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agent Execution Center"
        subtitle="Clinical knowledge extraction and summary preparation"
        breadcrumbs={[
          { label: "Patients", href: "/patients" },
          { label: patient ? `${patient.first_name} ${patient.last_name}` : "Patient", href: `/patients/${patientId}` },
          { label: "Agent" },
        ]}
      />

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left: Control + Status */}
        <div className="space-y-4">
          {/* Start Agent Card */}
          <div className={`rounded-xl border p-5 transition-colors ${
            isRunning
              ? "border-medical-blue-200 bg-medical-blue-50"
              : isComplete
              ? "border-clinical-green-200 bg-clinical-green-50"
              : isFailed
              ? "border-red-200 bg-red-50"
              : "border-slate-200 bg-white"
          }`}>
            <div className="mb-3 flex items-center gap-2">
              <div className={`flex h-8 w-8 items-center justify-center rounded-full ${
                isRunning ? "bg-medical-blue-200" : isComplete ? "bg-clinical-green-200" : "bg-slate-100"
              }`}>
                {isRunning ? (
                  <Loader2 className="h-4 w-4 animate-spin text-medical-blue-600" />
                ) : isComplete ? (
                  <CheckCircle2 className="h-4 w-4 text-clinical-green-600" />
                ) : (
                  <Bot className="h-4 w-4 text-slate-500" />
                )}
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-900">
                  {isRunning ? "Agent Running" : isComplete ? "Run Complete" : isFailed ? "Run Failed" : "Start Agent Run"}
                </p>
                {activeRun && <AgentStatusBadge status={activeRun.status} />}
              </div>
            </div>

            {isRunning && (
              <div className="mb-3">
                <p className="mb-1 text-xs text-medical-blue-700 animate-pulse">{progressMessage}</p>
                <div className="h-1.5 overflow-hidden rounded-full bg-medical-blue-200">
                  <div
                    className="h-full rounded-full bg-medical-blue-600 transition-all duration-1000"
                    style={{ width: `${((messageIndex + 1) / RUNNING_MESSAGES.length) * 100}%` }}
                  />
                </div>
              </div>
            )}

            {!isRunning && !isComplete && (
              <p className="mb-3 text-xs text-slate-500">
                The agent will extract clinical knowledge from all uploaded documents and build a comprehensive knowledge base for summary generation.
              </p>
            )}

            {error && (
              <div className="mb-3 rounded-lg bg-red-100 px-3 py-2 text-xs text-red-700">
                {error}
              </div>
            )}

            {!isRunning && !isComplete && (
              <button
                onClick={handleStartRun}
                disabled={isStarting}
                className="btn-primary w-full"
              >
                {isStarting ? (
                  <><Loader2 className="h-4 w-4 animate-spin" /> Starting...</>
                ) : (
                  <><Play className="h-4 w-4" /> Start Agent Run</>
                )}
              </button>
            )}

            {isComplete && (
              <div className="space-y-2">
                <Link
                  href={`/patients/${patientId}/safety?run_id=${activeRun!.run_id}`}
                  className="btn-primary w-full"
                >
                  <ShieldCheck className="h-4 w-4" />
                  Safety Review
                </Link>
                <Link
                  href={`/patients/${patientId}/trace?run_id=${activeRun!.run_id}`}
                  className="btn-secondary w-full"
                >
                  <Activity className="h-4 w-4" />
                  View Trace
                </Link>
              </div>
            )}
          </div>

          {/* Completeness Score */}
          {activeRun && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Completeness Score</h3>
              <div className="flex items-end gap-2">
                <span className="text-3xl font-bold text-slate-900">
                  {completeness != null ? `${Math.round(completeness * 100)}` : "—"}
                </span>
                <span className="mb-1 text-base text-slate-400">%</span>
              </div>
              {completeness != null && (
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      completeness >= 0.8 ? "bg-clinical-green-500" :
                      completeness >= 0.6 ? "bg-amber-500" : "bg-red-500"
                    }`}
                    style={{ width: `${completeness * 100}%` }}
                  />
                </div>
              )}
            </div>
          )}

          {/* Safety Status */}
          {activeRun && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Safety Indicators</h3>
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Escalation Required</span>
                  {activeRun.escalation_required ? (
                    <span className="flex items-center gap-1 text-xs font-medium text-red-600">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      Yes
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs font-medium text-clinical-green-600">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      No
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Iterations</span>
                  <span className="font-medium text-slate-700">{activeRun.iteration_count}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Tokens Used</span>
                  <span className="font-medium text-slate-700">{activeRun.total_tokens.toLocaleString()}</span>
                </div>
              </div>
              {activeRun.escalation_reasons.length > 0 && (
                <div className="mt-3 rounded-lg bg-red-50 p-3">
                  <p className="mb-1 text-xs font-semibold text-red-700">Escalation Reasons:</p>
                  <ul className="space-y-1">
                    {activeRun.escalation_reasons.map((r, i) => (
                      <li key={i} className="text-xs text-red-600 flex items-start gap-1">
                        <ChevronRight className="h-3 w-3 mt-0.5 flex-shrink-0" />
                        {r}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right: Tool Feed */}
        <div className="lg:col-span-2 space-y-4">
          {/* Tool Execution Feed */}
          <div className="rounded-xl border border-slate-200 bg-white">
            <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-3.5">
              <Activity className="h-4 w-4 text-slate-400" />
              <h3 className="text-sm font-semibold text-slate-900">Tool Execution Feed</h3>
              {isRunning && (
                <span className="ml-auto flex items-center gap-1.5 text-xs text-medical-blue-600">
                  <span className="h-1.5 w-1.5 rounded-full bg-medical-blue-600 animate-pulse" />
                  Live
                </span>
              )}
            </div>

            {traceSteps.length === 0 && !isRunning ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Bot className="mb-3 h-10 w-10 text-slate-200" />
                <p className="text-sm text-slate-400">Start a run to see tool execution</p>
              </div>
            ) : isRunning && traceSteps.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Loader2 className="mb-3 h-8 w-8 animate-spin text-medical-blue-400" />
                <p className="text-sm font-medium text-slate-700">Agent initializing...</p>
                <p className="text-xs text-slate-400 mt-1">{progressMessage}</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-50">
                {traceSteps.map((step, i) => {
                  const meta = getToolMeta(step.selected_tool);
                  return (
                    <div key={i} className="flex items-start gap-3 px-5 py-3.5">
                      <div className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg text-xs ${meta.color}`}>
                        {meta.icon}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-slate-900">{meta.label}</p>
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">
                            Step {step.step}
                          </span>
                          {step.duration_ms != null && (
                            <span className="flex items-center gap-0.5 text-xs text-slate-400">
                              <Clock className="h-3 w-3" />
                              {step.duration_ms}ms
                            </span>
                          )}
                        </div>
                        {step.reasoning && (
                          <p className="mt-0.5 text-xs text-slate-500 leading-relaxed">{step.reasoning}</p>
                        )}
                        {step.next_action && (
                          <p className="mt-0.5 text-xs text-medical-blue-500 flex items-center gap-1">
                            <ChevronRight className="h-3 w-3" />
                            Next: {step.next_action}
                          </p>
                        )}
                      </div>
                      <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-clinical-green-500" />
                    </div>
                  );
                })}
                {isRunning && (
                  <div className="flex items-center gap-3 px-5 py-3.5 bg-medical-blue-50">
                    <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-medical-blue-200">
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-medical-blue-600" />
                    </div>
                    <p className="text-sm text-medical-blue-700 animate-pulse">{progressMessage}</p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Previous Runs */}
          {runs.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white">
              <div className="border-b border-slate-100 px-5 py-3.5">
                <h3 className="text-sm font-semibold text-slate-900">Run History</h3>
              </div>
              <div className="divide-y divide-slate-50">
                {runs.slice(0, 5).map((run) => (
                  <div key={run.run_id} className="flex items-center justify-between px-5 py-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <AgentStatusBadge status={run.status} />
                        {run.completeness_score != null && (
                          <span className="text-xs text-slate-400">
                            {formatScore(run.completeness_score)} complete
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 text-xs text-slate-400">{formatRelativeTime(run.created_at)}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {(run.status === "COMPLETED" || run.status === "ESCALATED") && (
                        <>
                          <Link
                            href={`/patients/${patientId}/safety?run_id=${run.run_id}`}
                            className="flex items-center gap-1 text-xs font-medium text-medical-blue-600 hover:text-medical-blue-700"
                          >
                            <ShieldCheck className="h-3.5 w-3.5" />
                            Safety
                          </Link>
                          <Link
                            href={`/patients/${patientId}/summary?run_id=${run.run_id}`}
                            className="flex items-center gap-1 text-xs font-medium text-medical-blue-600 hover:text-medical-blue-700"
                          >
                            <ScrollText className="h-3.5 w-3.5" />
                            Summary
                          </Link>
                        </>
                      )}
                      <Link
                        href={`/patients/${patientId}/trace?run_id=${run.run_id}`}
                        className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
                      >
                        <Activity className="h-3.5 w-3.5" />
                        Trace
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
