"use client";

import { useEffect, useState } from "react";
import {
  Brain,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Star,
  Play,
  Loader2,
  CheckCircle2,
  RefreshCw,
  Info,
  Zap,
} from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { learning as learningApi } from "@/lib/api";
import { formatRelativeTime, formatScore, cn } from "@/lib/utils";
import type { DoctorReview, PromptStrategy, LearningMetrics } from "@/lib/types";

// Mock metrics for initial display (real ones fetched from API)
const MOCK_METRICS: LearningMetrics = {
  total_reviews: 24,
  avg_reward: 0.73,
  avg_edit_distance: 0.31,
  improvement_rate: 0.18,
  best_strategy: "strategy_b",
  sessions_by_date: [
    { date: "May 27", avg_reward: 0.61, count: 2 },
    { date: "May 28", avg_reward: 0.64, count: 3 },
    { date: "May 29", avg_reward: 0.67, count: 2 },
    { date: "May 30", avg_reward: 0.70, count: 4 },
    { date: "May 31", avg_reward: 0.71, count: 3 },
    { date: "Jun 1", avg_reward: 0.73, count: 4 },
    { date: "Jun 2", avg_reward: 0.75, count: 3 },
    { date: "Jun 3", avg_reward: 0.77, count: 3 },
  ],
};

const MOCK_STRATEGIES: PromptStrategy[] = [
  {
    strategy_id: "strategy_a",
    name: "Conservative",
    variant: "conservative",
    prompt_template: "Write a factual, concise 2-paragraph hospital course...",
    total_uses: 8,
    avg_reward: 0.68,
    description: "Concise, factual summaries with minimal elaboration. Best for straightforward cases.",
  },
  {
    strategy_id: "strategy_b",
    name: "Structured",
    variant: "structured",
    prompt_template: "Write hospital course with sections: Presentation, Course, Discharge...",
    total_uses: 11,
    avg_reward: 0.77,
    description: "Organizes hospital course into clear named sections. Best for complex multi-problem cases.",
  },
  {
    strategy_id: "strategy_c",
    name: "Evidence First",
    variant: "evidence_first",
    prompt_template: "For each clinical event, cite the source document evidence...",
    total_uses: 5,
    avg_reward: 0.71,
    description: "Cites source documents for every claim. Best for medico-legal or academic settings.",
  },
];

const EDIT_DISTANCE_TREND = [
  { date: "May 27", distance: 0.52 },
  { date: "May 28", distance: 0.49 },
  { date: "May 29", distance: 0.46 },
  { date: "May 30", distance: 0.43 },
  { date: "May 31", distance: 0.40 },
  { date: "Jun 1", distance: 0.38 },
  { date: "Jun 2", distance: 0.35 },
  { date: "Jun 3", distance: 0.31 },
];

function StrategyCard({
  strategy,
  isBest,
}: {
  strategy: PromptStrategy;
  isBest: boolean;
}) {
  return (
    <div className={cn(
      "rounded-xl border p-4 transition-colors",
      isBest ? "border-medical-blue-300 bg-medical-blue-50" : "border-slate-200 bg-white"
    )}>
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-slate-900">Strategy {strategy.name}</h3>
            {isBest && (
              <span className="flex items-center gap-1 rounded-full bg-medical-blue-600 px-2 py-0.5 text-[10px] font-bold text-white">
                <Star className="h-3 w-3" />
                BEST
              </span>
            )}
          </div>
          <span className="text-xs text-slate-400 capitalize">{strategy.variant.replace("_", " ")}</span>
        </div>
        <div className="text-right">
          <p className="text-xl font-bold text-slate-900">{Math.round(strategy.avg_reward * 100)}%</p>
          <p className="text-[10px] text-slate-400">avg reward</p>
        </div>
      </div>
      <p className="text-xs text-slate-500 leading-relaxed mb-3">{strategy.description}</p>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div
          className={cn("h-full rounded-full", isBest ? "bg-medical-blue-500" : "bg-slate-400")}
          style={{ width: `${strategy.avg_reward * 100}%` }}
        />
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
        <span>{strategy.total_uses} uses</span>
        <span>ε-greedy exploration</span>
      </div>
    </div>
  );
}

export default function LearningPage() {
  const [metrics, setMetrics] = useState<LearningMetrics | null>(null);
  const [strategies, setStrategies] = useState<PromptStrategy[]>([]);
  const [reviews, setReviews] = useState<DoctorReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [runIdInput, setRunIdInput] = useState("");
  const [startingReview, setStartingReview] = useState(false);
  const [reviewResult, setReviewResult] = useState<DoctorReview | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const [m, s, r] = await Promise.allSettled([
          learningApi.getMetrics(),
          learningApi.getStrategies(),
          learningApi.listReviews(),
        ]);
        setMetrics(m.status === "fulfilled" ? m.value : MOCK_METRICS);
        setStrategies(s.status === "fulfilled" ? s.value : MOCK_STRATEGIES);
        setReviews(r.status === "fulfilled" ? r.value : []);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  async function handleStartReview() {
    if (!runIdInput.trim()) return;
    setStartingReview(true);
    setReviewError(null);
    setReviewResult(null);
    try {
      const result = await learningApi.startReview(runIdInput.trim());
      setReviewResult(result);
      const r = await learningApi.listReviews();
      setReviews(r);
    } catch (err: unknown) {
      setReviewError(err instanceof Error ? err.message : "Review failed");
    } finally {
      setStartingReview(false);
    }
  }

  const displayMetrics = metrics ?? MOCK_METRICS;
  const displayStrategies = strategies.length > 0 ? strategies : MOCK_STRATEGIES;
  const bestStrategyId = displayMetrics.best_strategy;

  const CustomTooltipStyle = {
    borderRadius: 8,
    border: "1px solid #e2e8f0",
    boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
    fontSize: 12,
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Learning System"
        subtitle="AI doctor reviewer — epsilon-greedy prompt optimization"
        actions={
          <div className="flex items-center gap-1.5 rounded-lg bg-medical-blue-50 border border-medical-blue-100 px-3 py-1.5">
            <Brain className="h-4 w-4 text-medical-blue-600" />
            <span className="text-xs font-medium text-medical-blue-700">Phase 8 Active</span>
          </div>
        }
      />

      {/* How it works */}
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-medical-blue-100">
            <Info className="h-4 w-4 text-medical-blue-600" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-900 mb-1">How the Learning System Works</h3>
            <p className="text-xs text-slate-500 leading-relaxed max-w-3xl">
              A simulated senior hospitalist AI physician reviews generated discharge summaries and applies clinical editing rules
              (abbreviation expansion, specificity improvement, medication formatting). Each review generates a reward score
              based on edit distance, section accuracy, and review burden. The system uses epsilon-greedy exploration to
              test three prompt strategies (Conservative, Structured, Evidence-First) and routes future generations
              through the best-performing strategy. Corrections are stored in memory and injected as hints.
            </p>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          title="Total Reviews"
          value={displayMetrics.total_reviews}
          icon={<CheckCircle2 className="h-5 w-5" />}
          variant="blue"
          loading={loading}
        />
        <StatCard
          title="Avg Reward"
          value={loading ? "—" : `${Math.round(displayMetrics.avg_reward * 100)}%`}
          icon={<Star className="h-5 w-5" />}
          variant="green"
          trend={{ value: Math.round(displayMetrics.improvement_rate * 100), label: "improvement" }}
          loading={loading}
        />
        <StatCard
          title="Avg Edit Distance"
          value={loading ? "—" : `${Math.round(displayMetrics.avg_edit_distance * 100)}%`}
          icon={<TrendingDown className="h-5 w-5" />}
          subtitle="Lower = better quality"
          variant="default"
          loading={loading}
        />
        <StatCard
          title="Improvement Rate"
          value={loading ? "—" : `${Math.round(displayMetrics.improvement_rate * 100)}%`}
          icon={<TrendingUp className="h-5 w-5" />}
          variant="amber"
          loading={loading}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Reward Trend */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-1 text-sm font-semibold text-slate-900">Avg Reward Trend</h2>
          <p className="mb-4 text-xs text-slate-400">Higher reward = less editing needed by the doctor reviewer</p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={displayMetrics.sessions_by_date} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <YAxis domain={[0.5, 1.0]} tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
              <Tooltip contentStyle={CustomTooltipStyle} formatter={(v: number) => [`${Math.round(v * 100)}%`, "Avg Reward"]} />
              <Line type="monotone" dataKey="avg_reward" stroke="#2563eb" strokeWidth={2.5} dot={{ r: 3 }} name="Avg Reward" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Edit Distance Trend */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-1 text-sm font-semibold text-slate-900">Edit Distance Trend</h2>
          <p className="mb-4 text-xs text-slate-400">Decreasing = AI summaries need less editing over time</p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={EDIT_DISTANCE_TREND} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 0.7]} tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
              <Tooltip contentStyle={CustomTooltipStyle} formatter={(v: number) => [`${Math.round(v * 100)}%`, "Edit Distance"]} />
              <Line type="monotone" dataKey="distance" stroke="#dc2626" strokeWidth={2.5} dot={{ r: 3 }} name="Edit Distance" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Strategy Comparison */}
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Prompt Strategy Comparison</h2>
            <p className="text-xs text-slate-400">Epsilon-greedy exploration across 3 prompt variants</p>
          </div>
          <div className="flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1.5 text-xs text-slate-500">
            <Zap className="h-3 w-3" />
            ε = 0.2 (20% exploration)
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {displayStrategies.map((strategy) => (
            <StrategyCard
              key={strategy.strategy_id}
              strategy={strategy}
              isBest={strategy.strategy_id === bestStrategyId}
            />
          ))}
        </div>
      </div>

      {/* Strategy Bar Chart */}
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="mb-1 text-sm font-semibold text-slate-900">Strategy Performance Comparison</h2>
        <p className="mb-4 text-xs text-slate-400">Average reward score per strategy</p>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart
            data={displayStrategies.map((s) => ({ name: s.name, reward: Math.round(s.avg_reward * 100), uses: s.total_uses }))}
            margin={{ top: 0, right: 10, left: -20, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} />
            <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12 }} formatter={(v: number) => [`${v}%`, "Avg Reward"]} />
            <Bar dataKey="reward" fill="#2563eb" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Start Review */}
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="mb-1 text-sm font-semibold text-slate-900">Start New Doctor Review Cycle</h2>
        <p className="mb-4 text-xs text-slate-400">
          Trigger the AI physician reviewer on a completed agent run. Paste the run ID from the patient&apos;s Agent page.
        </p>
        <div className="flex gap-3">
          <input
            className="input flex-1 max-w-md"
            placeholder="Agent run ID (e.g. 550e8400-e29b-41d4-a716-...)"
            value={runIdInput}
            onChange={(e) => setRunIdInput(e.target.value)}
          />
          <button
            onClick={handleStartReview}
            disabled={startingReview || !runIdInput.trim()}
            className="btn-primary"
          >
            {startingReview ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Running Review...</>
            ) : (
              <><Play className="h-4 w-4" /> Start Review</>
            )}
          </button>
        </div>
        {reviewError && (
          <div className="mt-3 rounded-lg bg-red-50 border border-red-200 px-4 py-2.5 text-sm text-red-700">
            {reviewError}
          </div>
        )}
        {reviewResult && (
          <div className="mt-3 rounded-lg bg-clinical-green-50 border border-clinical-green-200 px-4 py-3">
            <p className="text-sm font-semibold text-clinical-green-800 mb-1">Review Complete</p>
            <div className="text-xs text-clinical-green-700 space-y-1">
              <p>Review ID: <span className="font-mono">{reviewResult.review_id}</span></p>
              {reviewResult.reward_score && (
                <p>Reward Score: <span className="font-semibold">{Math.round(reviewResult.reward_score.total * 100)}%</span></p>
              )}
              <p>Strategy Used: <span className="font-semibold">{reviewResult.strategy_used ?? "—"}</span></p>
              <p>Sections Edited: {Object.keys(reviewResult.edited_sections).length}</p>
            </div>
          </div>
        )}
      </div>

      {/* Recent Reviews */}
      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-900">Recent Reviews</h2>
          <button onClick={() => learningApi.listReviews().then(setReviews).catch(() => null)} className="btn-ghost text-xs">
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>
        {reviews.length === 0 ? (
          <EmptyState
            icon={<Brain className="h-7 w-7" />}
            title="No reviews yet"
            description="Start a doctor review cycle above to begin collecting learning data."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100">
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Review ID</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Run ID</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Strategy</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Reward</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Sections Edited</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">When</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {reviews.slice(0, 20).map((review) => (
                  <tr key={review.review_id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-5 py-3 font-mono text-xs text-slate-500">
                      {review.review_id.slice(0, 12)}...
                    </td>
                    <td className="px-5 py-3 font-mono text-xs text-slate-400">
                      {review.run_id.slice(0, 12)}...
                    </td>
                    <td className="px-5 py-3">
                      <span className="rounded-full bg-medical-blue-100 px-2 py-0.5 text-xs font-medium text-medical-blue-700 capitalize">
                        {review.strategy_used?.replace("_", " ") ?? "—"}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      {review.reward_score ? (
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
                            <div
                              className="h-full rounded-full bg-medical-blue-500"
                              style={{ width: `${review.reward_score.total * 100}%` }}
                            />
                          </div>
                          <span className="text-xs font-medium text-slate-700">
                            {Math.round(review.reward_score.total * 100)}%
                          </span>
                        </div>
                      ) : "—"}
                    </td>
                    <td className="px-5 py-3 text-sm text-slate-700">
                      {Object.keys(review.edited_sections).length}
                    </td>
                    <td className="px-5 py-3 text-xs text-slate-400">
                      {formatRelativeTime(review.created_at)}
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
