"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams, useSearchParams } from "next/navigation";
import {
  Activity,
  Search,
  X,
  ChevronDown,
  ChevronRight,
  Clock,
  Zap,
  Stethoscope,
  Pill,
  FlaskConical,
  ClipboardList,
  Brain,
  AlertTriangle,
  CheckCircle2,
  Filter,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { agent as agentApi, patients as patientsApi } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import type { TraceStep, Patient } from "@/lib/types";

const TOOL_CATEGORIES: Record<string, { color: string; bgColor: string; label: string; icon: React.ReactNode }> = {
  diagnosis: { color: "text-blue-700", bgColor: "bg-blue-100", label: "Diagnosis", icon: <Stethoscope className="h-3.5 w-3.5" /> },
  medication: { color: "text-purple-700", bgColor: "bg-purple-100", label: "Medication", icon: <Pill className="h-3.5 w-3.5" /> },
  lab: { color: "text-green-700", bgColor: "bg-green-100", label: "Lab", icon: <FlaskConical className="h-3.5 w-3.5" /> },
  admission: { color: "text-amber-700", bgColor: "bg-amber-100", label: "Admission", icon: <ClipboardList className="h-3.5 w-3.5" /> },
  knowledge: { color: "text-indigo-700", bgColor: "bg-indigo-100", label: "Knowledge", icon: <Brain className="h-3.5 w-3.5" /> },
  completeness: { color: "text-teal-700", bgColor: "bg-teal-100", label: "Completeness", icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
  conflict: { color: "text-red-700", bgColor: "bg-red-100", label: "Conflict", icon: <AlertTriangle className="h-3.5 w-3.5" /> },
  default: { color: "text-slate-700", bgColor: "bg-slate-100", label: "General", icon: <Zap className="h-3.5 w-3.5" /> },
};

function getCategory(toolName: string | undefined) {
  if (!toolName) return TOOL_CATEGORIES.default;
  const lower = toolName.toLowerCase();
  if (lower.includes("diagnos")) return TOOL_CATEGORIES.diagnosis;
  if (lower.includes("medic") || lower.includes("pharma")) return TOOL_CATEGORIES.medication;
  if (lower.includes("lab") || lower.includes("result")) return TOOL_CATEGORIES.lab;
  if (lower.includes("admission") || lower.includes("note")) return TOOL_CATEGORIES.admission;
  if (lower.includes("knowledge") || lower.includes("synthes")) return TOOL_CATEGORIES.knowledge;
  if (lower.includes("complet")) return TOOL_CATEGORIES.completeness;
  if (lower.includes("conflict") || lower.includes("safety")) return TOOL_CATEGORIES.conflict;
  return TOOL_CATEGORIES.default;
}

function StepCard({ step, expanded, onToggle }: { step: TraceStep; expanded: boolean; onToggle: () => void }) {
  const cat = getCategory(step.selected_tool);

  return (
    <div className={`rounded-xl border transition-colors ${expanded ? "border-slate-300 bg-white shadow-sm" : "border-slate-100 bg-white hover:border-slate-200"}`}>
      <button
        className="flex w-full items-start gap-3 px-5 py-4 text-left"
        onClick={onToggle}
      >
        <div className="flex-shrink-0 flex items-center gap-2 mt-0.5">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-500">
            {step.step}
          </span>
          <div className={`flex h-7 w-7 items-center justify-center rounded-lg ${cat.bgColor} ${cat.color}`}>
            {cat.icon}
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-semibold text-slate-900">{step.selected_tool}</p>
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${cat.bgColor} ${cat.color}`}>
              {cat.label}
            </span>
          </div>
          {step.reasoning && (
            <p className="mt-0.5 text-xs text-slate-500 leading-relaxed line-clamp-2">{step.reasoning}</p>
          )}
          <div className="mt-1.5 flex items-center gap-3 text-xs text-slate-400">
            {step.duration_ms != null && (
              <span className="flex items-center gap-0.5">
                <Clock className="h-3 w-3" />
                {step.duration_ms}ms
              </span>
            )}
            {step.tokens_in != null && (
              <span>{step.tokens_in} in</span>
            )}
            {step.tokens_out != null && (
              <span>{step.tokens_out} out</span>
            )}
            {step.timestamp && (
              <span>{formatDateTime(step.timestamp)}</span>
            )}
          </div>
        </div>
        <div className="flex-shrink-0 text-slate-400 mt-1">
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-slate-100 px-5 pb-5 pt-4 space-y-4">
          {step.reasoning && (
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Reasoning</p>
              <p className="text-sm text-slate-700 leading-relaxed">{step.reasoning}</p>
            </div>
          )}

          {step.tool_input && Object.keys(step.tool_input).length > 0 && (
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Tool Input</p>
              <pre className="overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700 leading-relaxed max-h-48">
                {JSON.stringify(step.tool_input, null, 2)}
              </pre>
            </div>
          )}

          {step.tool_output && Object.keys(step.tool_output).length > 0 && (
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Tool Output</p>
              <pre className="overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700 leading-relaxed max-h-48">
                {JSON.stringify(step.tool_output, null, 2)}
              </pre>
            </div>
          )}

          {step.state_changes && Object.keys(step.state_changes).length > 0 && (
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">State Changes</p>
              <pre className="overflow-auto rounded-lg bg-clinical-green-50 p-3 text-xs text-clinical-green-800 leading-relaxed max-h-32">
                {JSON.stringify(step.state_changes, null, 2)}
              </pre>
            </div>
          )}

          {step.next_action && (
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Next Action</p>
              <p className="flex items-center gap-1.5 text-sm text-medical-blue-600">
                <ChevronRight className="h-4 w-4" />
                {step.next_action}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function TracePage() {
  const { id: patientId } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const runId = searchParams.get("run_id");

  const [patient, setPatient] = useState<Patient | null>(null);
  const [trace, setTrace] = useState<TraceStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set([0]));
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  useEffect(() => {
    patientsApi.get(patientId).then(setPatient).catch(() => null);
  }, [patientId]);

  useEffect(() => {
    if (!runId) {
      setError("No run_id specified in URL");
      setLoading(false);
      return;
    }
    agentApi
      .getTrace(runId)
      .then((steps) => setTrace(steps))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [runId]);

  function toggleStep(index: number) {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  const filteredTrace = useMemo(() => {
    return trace.filter((step) => {
      const matchesSearch =
        !searchQuery ||
        (step.selected_tool ?? "").toLowerCase().includes(searchQuery.toLowerCase()) ||
        (step.reasoning ?? "").toLowerCase().includes(searchQuery.toLowerCase());

      const cat = getCategory(step.selected_tool);
      const matchesCategory = categoryFilter === "all" || cat.label.toLowerCase() === categoryFilter;

      return matchesSearch && matchesCategory;
    });
  }, [trace, searchQuery, categoryFilter]);

  const categories = useMemo(() => {
    const seen = new Set<string>();
    trace.forEach((step) => seen.add(getCategory(step.selected_tool).label.toLowerCase()));
    return Array.from(seen);
  }, [trace]);

  const totalDuration = trace.reduce((sum, s) => sum + (s.duration_ms ?? 0), 0);
  const totalTokens = trace.reduce((sum, s) => sum + (s.tokens_in ?? 0) + (s.tokens_out ?? 0), 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agent Trace Viewer"
        subtitle={runId ? `Run ID: ${runId}` : "Select a run to view trace"}
        breadcrumbs={[
          { label: "Patients", href: "/patients" },
          {
            label: patient ? `${patient.first_name} ${patient.last_name}` : "Patient",
            href: `/patients/${patientId}`,
          },
          { label: "Trace" },
        ]}
      />

      {/* Stats bar */}
      {trace.length > 0 && (
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: "Total Steps", value: trace.length },
            { label: "Filtered Steps", value: filteredTrace.length },
            { label: "Total Duration", value: `${totalDuration}ms` },
            { label: "Total Tokens", value: totalTokens.toLocaleString() },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</p>
              <p className="mt-1 text-xl font-bold text-slate-900">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Search + Filter */}
      {trace.length > 0 && (
        <div className="flex gap-3 flex-wrap">
          <div className="relative min-w-[280px]">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              className="input pl-9 pr-4"
              placeholder="Search tool name or reasoning..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-slate-400" />
            <select
              className="input py-2 pr-8 text-sm"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="all">All categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c.charAt(0).toUpperCase() + c.slice(1)}
                </option>
              ))}
            </select>
          </div>

          {(searchQuery || categoryFilter !== "all") && (
            <button
              onClick={() => { setSearchQuery(""); setCategoryFilter("all"); }}
              className="btn-ghost"
            >
              <X className="h-4 w-4" />
              Clear filters
            </button>
          )}

          <button
            onClick={() => setExpandedSteps(new Set(filteredTrace.map((_, i) => i)))}
            className="btn-secondary text-xs py-1.5"
          >
            Expand All
          </button>
          <button
            onClick={() => setExpandedSteps(new Set())}
            className="btn-ghost text-xs py-1.5"
          >
            Collapse All
          </button>
        </div>
      )}

      {/* Trace */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-xl bg-slate-100" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-600">
          {error}
        </div>
      ) : trace.length === 0 ? (
        <EmptyState
          icon={<Activity className="h-8 w-8" />}
          title="No trace available"
          description="This run either has no trace data or is still in progress."
        />
      ) : filteredTrace.length === 0 ? (
        <EmptyState
          icon={<Search className="h-8 w-8" />}
          title="No steps match your filters"
          description="Try adjusting your search query or category filter."
        />
      ) : (
        <div className="space-y-2">
          {filteredTrace.map((step, index) => (
            <StepCard
              key={index}
              step={step}
              expanded={expandedSteps.has(index)}
              onToggle={() => toggleStep(index)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
