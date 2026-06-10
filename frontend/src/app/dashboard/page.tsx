"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Users,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Percent,
  Timer,
  Plus,
  ArrowRight,
  Bot,
  FileText,
  ShieldCheck,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { SummaryStatusBadge } from "@/components/ui/Badge";
import { ClaudeStatusPanel } from "@/components/dashboard/ClaudeStatusPanel";
import { patients as patientsApi } from "@/lib/api";
import { formatDate, formatRelativeTime } from "@/lib/utils";
import type { PatientListItem } from "@/lib/types";

const activityData = [
  { date: "Jun 1", processed: 4, pending: 2, flags: 1 },
  { date: "Jun 2", processed: 7, pending: 3, flags: 2 },
  { date: "Jun 3", processed: 5, pending: 4, flags: 1 },
  { date: "Jun 4", processed: 9, pending: 2, flags: 3 },
  { date: "Jun 5", processed: 6, pending: 5, flags: 0 },
  { date: "Jun 6", processed: 11, pending: 3, flags: 2 },
  { date: "Jun 7", processed: 8, pending: 2, flags: 1 },
];

export default function DashboardPage() {
  const [patients, setPatients] = useState<PatientListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    patientsApi
      .list({ page_size: 10 })
      .then((res) => {
        setPatients(res.items);
        setTotal(res.total);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const processed = patients.filter((p) => p.summary_status === "APPROVED").length;
  const pending = patients.filter((p) =>
    p.summary_status === "PENDING_REVIEW" || p.summary_status === "IN_REVIEW"
  ).length;
  const escalated = patients.filter((p) => p.summary_status === "ESCALATED").length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Executive Dashboard"
        subtitle="Clinical discharge summary pipeline overview"
        actions={
          <Link href="/patients" className="btn-primary">
            <Plus className="h-4 w-4" />
            New Patient
          </Link>
        }
      />

      {/* Stat Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        <StatCard
          title="Total Patients"
          value={loading ? "—" : total}
          icon={<Users className="h-5 w-5" />}
          variant="blue"
          loading={loading}
        />
        <StatCard
          title="Processed Cases"
          value={loading ? "—" : processed}
          icon={<CheckCircle2 className="h-5 w-5" />}
          variant="green"
          loading={loading}
        />
        <StatCard
          title="Pending Reviews"
          value={loading ? "—" : pending}
          icon={<Clock className="h-5 w-5" />}
          variant="amber"
          loading={loading}
        />
        <StatCard
          title="Safety Flags"
          value={loading ? "—" : escalated}
          icon={<AlertTriangle className="h-5 w-5" />}
          variant={escalated > 0 ? "red" : "default"}
          loading={loading}
        />
        <StatCard
          title="Agent Success Rate"
          value={loading ? "—" : total > 0 ? `${Math.round((processed / Math.max(total, 1)) * 100)}%` : "—"}
          icon={<Percent className="h-5 w-5" />}
          variant="default"
          loading={loading}
        />
        <StatCard
          title="Avg Processing"
          value="4.2 min"
          icon={<Timer className="h-5 w-5" />}
          variant="default"
          loading={false}
        />
      </div>

      {/* Claude Status */}
      <ClaudeStatusPanel />

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Activity Chart */}
        <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Processing Activity</h2>
              <p className="text-xs text-slate-400">Last 7 days</p>
            </div>
            <div className="flex items-center gap-4 text-xs text-slate-500">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-medical-blue-500" />
                Processed
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-clinical-amber-400" />
                Pending
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-red-400" />
                Flags
              </span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={activityData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorProcessed" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563eb" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorPending" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0", boxShadow: "0 2px 8px rgba(0,0,0,0.08)" }}
              />
              <Area type="monotone" dataKey="processed" stroke="#2563eb" strokeWidth={2} fill="url(#colorProcessed)" />
              <Area type="monotone" dataKey="pending" stroke="#f59e0b" strokeWidth={2} fill="url(#colorPending)" />
              <Area type="monotone" dataKey="flags" stroke="#ef4444" strokeWidth={2} fill="none" strokeDasharray="4 2" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Quick Actions */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-900">Quick Actions</h2>
          <div className="space-y-2">
            <Link
              href="/patients"
              className="flex items-center gap-3 rounded-lg border border-slate-100 p-3 text-sm text-slate-700 transition-colors hover:bg-slate-50"
            >
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-medical-blue-100 text-medical-blue-600">
                <Users className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-medium">Manage Patients</p>
                <p className="text-xs text-slate-400">View all patients & upload docs</p>
              </div>
              <ArrowRight className="h-4 w-4 text-slate-300" />
            </Link>

            <Link
              href="/patients"
              className="flex items-center gap-3 rounded-lg border border-slate-100 p-3 text-sm text-slate-700 transition-colors hover:bg-slate-50"
            >
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-clinical-green-100 text-clinical-green-600">
                <Bot className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-medium">Run Agent</p>
                <p className="text-xs text-slate-400">Generate discharge summaries</p>
              </div>
              <ArrowRight className="h-4 w-4 text-slate-300" />
            </Link>

            <Link
              href="/analytics"
              className="flex items-center gap-3 rounded-lg border border-slate-100 p-3 text-sm text-slate-700 transition-colors hover:bg-slate-50"
            >
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-purple-100 text-purple-600">
                <FileText className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-medium">View Analytics</p>
                <p className="text-xs text-slate-400">Performance & safety metrics</p>
              </div>
              <ArrowRight className="h-4 w-4 text-slate-300" />
            </Link>

            <Link
              href="/learning"
              className="flex items-center gap-3 rounded-lg border border-slate-100 p-3 text-sm text-slate-700 transition-colors hover:bg-slate-50"
            >
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-600">
                <ShieldCheck className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-medium">Learning System</p>
                <p className="text-xs text-slate-400">AI improvement & reviews</p>
              </div>
              <ArrowRight className="h-4 w-4 text-slate-300" />
            </Link>
          </div>
        </div>
      </div>

      {/* Recent Patients */}
      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Recent Patients</h2>
            <p className="text-xs text-slate-400">Latest {patients.length} of {total} patients</p>
          </div>
          <Link href="/patients" className="flex items-center gap-1 text-xs font-medium text-medical-blue-600 hover:text-medical-blue-700">
            View all
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {loading ? (
          <div className="p-6 space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-10 animate-pulse rounded bg-slate-100" />
            ))}
          </div>
        ) : error ? (
          <div className="p-8 text-center text-sm text-red-500">{error}</div>
        ) : patients.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-400">No patients found. Add your first patient to get started.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Patient</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">MRN</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Ward</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Docs</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Status</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Admitted</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {patients.map((patient) => (
                  <tr key={patient.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-medical-blue-100 text-xs font-semibold text-medical-blue-600">
                          {patient.first_name[0]}{patient.last_name[0]}
                        </div>
                        <span className="text-sm font-medium text-slate-900">
                          {patient.first_name} {patient.last_name}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-3 font-mono text-xs text-slate-500">{patient.mrn}</td>
                    <td className="px-5 py-3 text-sm text-slate-500">{patient.ward ?? "—"}</td>
                    <td className="px-5 py-3 text-sm text-slate-700">{patient.document_count}</td>
                    <td className="px-5 py-3">
                      {patient.summary_status ? (
                        <SummaryStatusBadge status={patient.summary_status} />
                      ) : (
                        <span className="text-xs text-slate-400">No summary</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-xs text-slate-400">
                      {formatRelativeTime(patient.admission_date ?? patient.created_at)}
                    </td>
                    <td className="px-5 py-3">
                      <Link
                        href={`/patients/${patient.id}`}
                        className="text-xs font-medium text-medical-blue-600 hover:text-medical-blue-700"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
