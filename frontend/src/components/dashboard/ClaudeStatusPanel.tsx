"use client";

import { useEffect, useState } from "react";
import { Sparkles, Database, Repeat, ScanText } from "lucide-react";
import { ClaudeStatusBadge } from "@/components/ui/Badge";
import { system as systemApi } from "@/lib/api";
import type { ClaudeStatus } from "@/lib/types";

export function ClaudeStatusPanel() {
  const [status, setStatus] = useState<ClaudeStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    systemApi
      .claudeStatus()
      .then(setStatus)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-medical-blue-600" />
          <h2 className="text-sm font-semibold text-slate-900">Claude Status</h2>
        </div>
        {loading ? (
          <div className="h-5 w-20 animate-pulse rounded-full bg-slate-100" />
        ) : status ? (
          <ClaudeStatusBadge status={status.status} />
        ) : null}
      </div>

      {error ? (
        <p className="text-sm text-red-500">{error}</p>
      ) : loading ? (
        <div className="space-y-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-8 animate-pulse rounded bg-slate-100" />
          ))}
        </div>
      ) : status ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Model</p>
            <p className="mt-1 text-sm font-medium text-slate-900">{status.text_model}</p>
            <p className="text-xs text-slate-400">Vision: {status.vision_model}</p>
          </div>
          <div>
            <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <Repeat className="h-3 w-3" /> Requests
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">{status.requests.total}</p>
            <p className="text-xs text-slate-400">
              text {status.requests.text} · vision {status.requests.vision} · errors {status.requests.errors}
            </p>
          </div>
          <div>
            <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <Database className="h-3 w-3" /> Cache Hits
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">{status.cache.hits}</p>
            <p className="text-xs text-slate-400">
              {status.cache.enabled ? `misses ${status.cache.misses}` : "disabled"}
            </p>
          </div>
          <div>
            <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <ScanText className="h-3 w-3" /> OCR
            </p>
            <p className="mt-1 text-sm font-medium capitalize text-slate-900">{status.ocr.status}</p>
            <p className="text-xs text-slate-400">
              {status.ocr.primary_provider} · {status.ocr.requests} requests
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
