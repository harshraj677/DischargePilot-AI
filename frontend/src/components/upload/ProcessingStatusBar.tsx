"use client";

import { CheckCircle2, Loader2, AlertCircle, Clock } from "lucide-react";
import type { ProcessingStatus } from "@/lib/types";

interface ProcessingStatusBarProps {
  status: ProcessingStatus | null;
  loading: boolean;
}

export function ProcessingStatusBar({ status, loading }: ProcessingStatusBarProps) {
  if (!status && !loading) return null;

  if (loading && !status) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>Checking processing status…</span>
      </div>
    );
  }

  if (!status) return null;

  const { total_documents, processed, processing, failed, uploaded, all_ready } = status;
  const pct = total_documents > 0 ? Math.round((processed / total_documents) * 100) : 0;

  return (
    <div className="space-y-3">
      {/* Progress bar */}
      <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
        <div className="mb-2 flex items-center justify-between text-xs text-slate-600">
          <span className="font-500">Processing Progress</span>
          <span>{processed}/{total_documents} documents ready</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className={[
              "h-full rounded-full transition-all duration-500",
              all_ready ? "bg-green-500" : "bg-blue-500",
            ].join(" ")}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Status tiles */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <StatusTile
          label="Processed"
          count={processed}
          icon={<CheckCircle2 className="h-4 w-4 text-green-500" />}
          active={processed > 0}
          activeColor="text-green-700"
        />
        <StatusTile
          label="Processing"
          count={processing}
          icon={<Loader2 className={`h-4 w-4 text-amber-500 ${processing > 0 ? "animate-spin" : ""}`} />}
          active={processing > 0}
          activeColor="text-amber-700"
        />
        <StatusTile
          label="Queued"
          count={uploaded}
          icon={<Clock className="h-4 w-4 text-slate-400" />}
          active={uploaded > 0}
          activeColor="text-slate-700"
        />
        <StatusTile
          label="Failed"
          count={failed}
          icon={<AlertCircle className="h-4 w-4 text-red-500" />}
          active={failed > 0}
          activeColor="text-red-700"
        />
      </div>

      {/* Ready banner */}
      {all_ready && total_documents > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
          <span>
            All {total_documents} document{total_documents !== 1 ? "s" : ""} processed and ready.
            You can now generate the discharge summary.
          </span>
        </div>
      )}

      {/* Failed warning */}
      {failed > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>
            {failed} document{failed !== 1 ? "s" : ""} failed to process. Use the retry button to re-attempt.
          </span>
        </div>
      )}
    </div>
  );
}

function StatusTile({
  label,
  count,
  icon,
  active,
  activeColor,
}: {
  label: string;
  count: number;
  icon: React.ReactNode;
  active: boolean;
  activeColor: string;
}) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-slate-100 bg-white px-3 py-2.5">
      {icon}
      <div>
        <p className={`text-lg font-700 leading-none ${active ? activeColor : "text-slate-300"}`}>
          {count}
        </p>
        <p className="mt-0.5 text-xs text-slate-400">{label}</p>
      </div>
    </div>
  );
}
