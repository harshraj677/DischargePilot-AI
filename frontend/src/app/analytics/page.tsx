"use client";

import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { TrendingUp, Shield, CheckCircle2, Clock, BarChart3, PieChart as PieChartIcon } from "lucide-react";

// Mock data — no analytics endpoint yet
const processingTrendData = [
  { date: "May 27", runs: 3, success: 3 },
  { date: "May 28", runs: 5, success: 4 },
  { date: "May 29", runs: 4, success: 4 },
  { date: "May 30", runs: 7, success: 6 },
  { date: "May 31", runs: 6, success: 5 },
  { date: "Jun 1", runs: 9, success: 9 },
  { date: "Jun 2", runs: 8, success: 7 },
  { date: "Jun 3", runs: 11, success: 10 },
  { date: "Jun 4", runs: 10, success: 10 },
  { date: "Jun 5", runs: 13, success: 12 },
];

const toolUsageData = [
  { tool: "Diagnosis", uses: 89 },
  { tool: "Medications", uses: 84 },
  { tool: "Lab Results", uses: 78 },
  { tool: "Admission Note", uses: 72 },
  { tool: "Completeness", uses: 65 },
  { tool: "Conflict Detect", uses: 42 },
  { tool: "KB Synthesis", uses: 38 },
];

const safetyDistData = [
  { name: "Approved", value: 42, color: "#059669" },
  { name: "Review Required", value: 18, color: "#d97706" },
  { name: "Blocked", value: 5, color: "#dc2626" },
];

const safetyScoreTrendData = [
  { date: "May 27", score: 72, completeness: 68 },
  { date: "May 28", score: 75, completeness: 71 },
  { date: "May 29", score: 74, completeness: 73 },
  { date: "May 30", score: 79, completeness: 76 },
  { date: "May 31", score: 81, completeness: 78 },
  { date: "Jun 1", score: 84, completeness: 82 },
  { date: "Jun 2", score: 83, completeness: 81 },
  { date: "Jun 3", score: 87, completeness: 85 },
  { date: "Jun 4", score: 88, completeness: 87 },
  { date: "Jun 5", score: 91, completeness: 89 },
];

const CustomTooltipStyle = {
  borderRadius: 8,
  border: "1px solid #e2e8f0",
  boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
  fontSize: 12,
};

export default function AnalyticsPage() {
  const totalRuns = processingTrendData.reduce((s, d) => s + d.runs, 0);
  const successRuns = processingTrendData.reduce((s, d) => s + d.success, 0);
  const avgSafety = safetyScoreTrendData.reduce((s, d) => s + d.score, 0) / safetyScoreTrendData.length;
  const avgCompleteness = safetyScoreTrendData.reduce((s, d) => s + d.completeness, 0) / safetyScoreTrendData.length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics Dashboard"
        subtitle="Platform performance and clinical quality metrics"
      />

      <p className="text-xs text-slate-400 bg-amber-50 border border-amber-100 px-3 py-2 rounded-lg inline-block">
        Showing mock data — analytics endpoints will be wired in a future phase.
      </p>

      {/* Summary Metrics */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard
          title="Total Runs (10d)"
          value={totalRuns}
          icon={<BarChart3 className="h-5 w-5" />}
          variant="blue"
        />
        <StatCard
          title="Success Rate"
          value={`${Math.round((successRuns / totalRuns) * 100)}%`}
          icon={<CheckCircle2 className="h-5 w-5" />}
          variant="green"
          trend={{ value: 4, label: "vs last week" }}
        />
        <StatCard
          title="Avg Safety Score"
          value={`${Math.round(avgSafety)}%`}
          icon={<Shield className="h-5 w-5" />}
          variant="default"
          trend={{ value: 7, label: "improvement" }}
        />
        <StatCard
          title="Avg Completeness"
          value={`${Math.round(avgCompleteness)}%`}
          icon={<TrendingUp className="h-5 w-5" />}
          variant="default"
          trend={{ value: 5, label: "improvement" }}
        />
        <StatCard
          title="Avg Processing"
          value="4.2 min"
          icon={<Clock className="h-5 w-5" />}
          variant="default"
          trend={{ value: -8, label: "faster" }}
        />
      </div>

      {/* Charts Row 1 */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Processing Trend */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-1 text-sm font-semibold text-slate-900">Processing Trend (10 days)</h2>
          <p className="mb-4 text-xs text-slate-400">Total runs vs successful completions</p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={processingTrendData} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={CustomTooltipStyle} />
              <Legend iconSize={10} wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="runs" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} name="Total Runs" />
              <Line type="monotone" dataKey="success" stroke="#059669" strokeWidth={2} dot={{ r: 3 }} name="Successful" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Tool Usage Frequency */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-1 text-sm font-semibold text-slate-900">Tool Usage Frequency</h2>
          <p className="mb-4 text-xs text-slate-400">How often each tool is invoked per run</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={toolUsageData} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="tool" tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={CustomTooltipStyle} />
              <Bar dataKey="uses" fill="#2563eb" radius={[4, 4, 0, 0]} name="Uses" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Safety Score Trend */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-1 text-sm font-semibold text-slate-900">Quality Score Trends</h2>
          <p className="mb-4 text-xs text-slate-400">Safety and completeness improving over time</p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={safetyScoreTrendData} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <YAxis domain={[50, 100]} tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={CustomTooltipStyle} />
              <Legend iconSize={10} wrapperStyle={{ fontSize: 12 }} />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#059669"
                strokeWidth={2.5}
                dot={{ r: 3 }}
                name="Safety Score"
              />
              <Line
                type="monotone"
                dataKey="completeness"
                stroke="#2563eb"
                strokeWidth={2.5}
                dot={{ r: 3 }}
                name="Completeness"
                strokeDasharray="5 3"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Safety Status Distribution */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-1 text-sm font-semibold text-slate-900">Safety Status Distribution</h2>
          <p className="mb-4 text-xs text-slate-400">How summaries are classified after safety validation</p>
          <div className="flex items-center">
            <ResponsiveContainer width="50%" height={200}>
              <PieChart>
                <Pie
                  data={safetyDistData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {safetyDistData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={CustomTooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-3">
              {safetyDistData.map((item) => (
                <div key={item.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="h-3 w-3 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
                    <span className="text-sm text-slate-600">{item.name}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-semibold text-slate-900">{item.value}</span>
                    <span className="ml-1 text-xs text-slate-400">
                      ({Math.round((item.value / safetyDistData.reduce((s, d) => s + d.value, 0)) * 100)}%)
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
