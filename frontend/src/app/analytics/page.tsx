"use client";

import { useEffect, useState } from "react";
import {
  Users,
  FileText,
  ScrollText,
  ListChecks,
  ShieldCheck,
  Gauge,
  AlertOctagon,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { AnalyticsCard } from "@/components/analytics/AnalyticsCard";
import { SeverityPieChart } from "@/components/analytics/SeverityPieChart";
import { TopMissingFieldsChart } from "@/components/analytics/TopMissingFieldsChart";
import { TopConflictsChart } from "@/components/analytics/TopConflictsChart";
import { ApprovalGauge } from "@/components/analytics/ApprovalGauge";
import { RecentActivityTable } from "@/components/analytics/RecentActivityTable";
import { SkeletonCard, SkeletonChart } from "@/components/ui/Skeleton";
import { analytics as analyticsApi, reviewHistory as reviewHistoryApi } from "@/lib/api";
import { formatScore } from "@/lib/utils";
import type { DashboardMetrics, ReviewHistoryEntry } from "@/lib/types";

export default function AnalyticsPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [recentActivity, setRecentActivity] = useState<ReviewHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      analyticsApi.dashboard(),
      reviewHistoryApi.list({ page: 1, page_size: 10 }),
    ])
      .then(([dashboard, history]) => {
        if (cancelled) return;
        setMetrics(dashboard);
        setRecentActivity(history.items);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load analytics");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader title="Analytics Dashboard" subtitle="Platform performance and clinical quality metrics" />
        <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center text-sm text-red-600">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Analytics Dashboard" subtitle="Platform performance and clinical quality metrics" />

      {/* Overview Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-5">
        {loading || !metrics ? (
          Array.from({ length: 9 }).map((_, i) => <SkeletonCard key={i} />)
        ) : (
          <>
            <AnalyticsCard title="Total Patients" value={metrics.total_patients} icon={<Users className="h-5 w-5" />} variant="blue" />
            <AnalyticsCard title="Total Documents" value={metrics.total_documents} icon={<FileText className="h-5 w-5" />} />
            <AnalyticsCard title="Total Summaries" value={metrics.total_summaries} icon={<ScrollText className="h-5 w-5" />} />
            <AnalyticsCard title="Total Findings" value={metrics.total_findings} icon={<ListChecks className="h-5 w-5" />} />
            <AnalyticsCard
              title="High Risk Findings"
              value={metrics.high_risk_findings}
              icon={<AlertOctagon className="h-5 w-5" />}
              variant={metrics.high_risk_findings > 0 ? "red" : "default"}
            />
            <AnalyticsCard
              title="Avg Safety Score"
              value={formatScore(metrics.average_safety_score)}
              icon={<ShieldCheck className="h-5 w-5" />}
              variant="green"
            />
            <AnalyticsCard
              title="Avg Completeness"
              value={formatScore(metrics.average_completeness_score)}
              icon={<Gauge className="h-5 w-5" />}
              variant="green"
            />
            <AnalyticsCard
              title="Approval Rate"
              value={formatScore(metrics.approval_rate)}
              icon={<ThumbsUp className="h-5 w-5" />}
            />
            <AnalyticsCard
              title="Rejection Rate"
              value={formatScore(metrics.rejection_rate)}
              icon={<ThumbsDown className="h-5 w-5" />}
              variant={metrics.rejection_rate > 0 ? "amber" : "default"}
            />
          </>
        )}
      </div>

      {/* Charts Row 1 */}
      <div className="grid gap-6 lg:grid-cols-2">
        {loading || !metrics ? (
          <>
            <SkeletonChart />
            <SkeletonChart />
          </>
        ) : (
          <>
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="mb-1 text-sm font-semibold text-slate-900">Severity Distribution</h2>
              <p className="mb-4 text-xs text-slate-400">Findings broken down by severity level</p>
              <SeverityPieChart distribution={metrics.severity_distribution} />
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="mb-1 text-sm font-semibold text-slate-900">Approval Outcomes</h2>
              <p className="mb-4 text-xs text-slate-400">Share of findings approved, rejected, or acknowledged</p>
              <ApprovalGauge
                approvalRate={metrics.approval_rate}
                rejectionRate={metrics.rejection_rate}
                acknowledgmentRate={metrics.acknowledgment_rate}
              />
            </div>
          </>
        )}
      </div>

      {/* Charts Row 2 */}
      <div className="grid gap-6 lg:grid-cols-2">
        {loading || !metrics ? (
          <>
            <SkeletonChart />
            <SkeletonChart />
          </>
        ) : (
          <>
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="mb-1 text-sm font-semibold text-slate-900">Top Missing Fields</h2>
              <p className="mb-4 text-xs text-slate-400">Most frequently undocumented required fields</p>
              <TopMissingFieldsChart fields={metrics.top_missing_fields} />
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="mb-1 text-sm font-semibold text-slate-900">Top Conflicts</h2>
              <p className="mb-4 text-xs text-slate-400">Most common conflict findings across patients</p>
              <TopConflictsChart conflicts={metrics.top_conflicts} />
            </div>
          </>
        )}
      </div>

      {/* Recent Activity */}
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="mb-1 text-sm font-semibold text-slate-900">Recent Activity</h2>
        <p className="mb-4 text-xs text-slate-400">Latest clinician decisions on safety findings</p>
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-10 animate-pulse rounded bg-slate-100" />
            ))}
          </div>
        ) : (
          <RecentActivityTable entries={recentActivity} />
        )}
      </div>
    </div>
  );
}
