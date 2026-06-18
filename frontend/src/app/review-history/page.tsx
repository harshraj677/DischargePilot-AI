"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ReviewHistoryTable } from "@/components/review/ReviewHistoryTable";
import { reviewHistory as reviewHistoryApi } from "@/lib/api";
import type { ReviewActionType, ReviewHistoryEntry } from "@/lib/types";

const PAGE_SIZE = 20;

export default function ReviewHistoryPage() {
  const [entries, setEntries] = useState<ReviewHistoryEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [severity, setSeverity] = useState("");
  const [action, setAction] = useState<ReviewActionType | "">("");
  const [reviewer, setReviewer] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await reviewHistoryApi.list({
        page,
        page_size: PAGE_SIZE,
        severity: severity || undefined,
        action: action || undefined,
        reviewer: reviewer || undefined,
        date_from: dateFrom ? new Date(dateFrom).toISOString() : undefined,
        date_to: dateTo ? new Date(dateTo).toISOString() : undefined,
      });
      setEntries(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load review history");
    } finally {
      setLoading(false);
    }
  }, [page, severity, action, reviewer, dateFrom, dateTo]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  function resetToFirstPage<T>(setter: (v: T) => void) {
    return (value: T) => {
      setPage(1);
      setter(value);
    };
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <PageHeader title="Review History" subtitle="Track every approve, reject, and acknowledgment decision" />

      {/* Filters */}
      <div className="grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-4 lg:grid-cols-5">
        <select
          value={severity}
          onChange={(e) => resetToFirstPage(setSeverity)(e.target.value)}
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
        >
          <option value="">All severities</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
          <option value="INFO">Info</option>
        </select>

        <select
          value={action}
          onChange={(e) => resetToFirstPage(setAction)(e.target.value as ReviewActionType | "")}
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
        >
          <option value="">All actions</option>
          <option value="APPROVED">Approved</option>
          <option value="REJECTED">Rejected</option>
          <option value="ACKNOWLEDGED">Acknowledged</option>
        </select>

        <input
          type="text"
          placeholder="Reviewer"
          value={reviewer}
          onChange={(e) => resetToFirstPage(setReviewer)(e.target.value)}
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400"
        />

        <input
          type="date"
          value={dateFrom}
          onChange={(e) => resetToFirstPage(setDateFrom)(e.target.value)}
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
        />

        <input
          type="date"
          value={dateTo}
          onChange={(e) => resetToFirstPage(setDateTo)(e.target.value)}
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
        />
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center text-sm text-red-600">
          {error}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-10 animate-pulse rounded bg-slate-100" />
              ))}
            </div>
          ) : (
            <>
              <ReviewHistoryTable entries={entries} />
              {total > 0 && (
                <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
                  <span>
                    Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      className="flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-slate-600 disabled:opacity-40"
                    >
                      <ChevronLeft className="h-3.5 w-3.5" />
                      Prev
                    </button>
                    <span className="text-slate-500">
                      Page {page} of {totalPages}
                    </span>
                    <button
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page >= totalPages}
                      className="flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-slate-600 disabled:opacity-40"
                    >
                      Next
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
