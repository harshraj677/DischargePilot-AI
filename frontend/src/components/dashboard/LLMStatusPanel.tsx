"use client";

import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { LLMStatusBadge } from "@/components/ui/Badge";
import { system as systemApi } from "@/lib/api";
import type { LLMStatus } from "@/lib/types";

export function LLMStatusPanel() {
  const [status, setStatus] = useState<LLMStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    systemApi
      .llmStatus()
      .then(setStatus)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-medical-blue-600" />
          <h2 className="text-sm font-semibold text-slate-900">LLM Status</h2>
        </div>
        {loading ? (
          <div className="h-5 w-40 animate-pulse rounded-full bg-slate-100" />
        ) : status ? (
          <LLMStatusBadge status={status.status} />
        ) : null}
      </div>

      {error ? (
        <p className="text-sm text-red-500">{error}</p>
      ) : loading ? (
        <div className="h-8 animate-pulse rounded bg-slate-100" />
      ) : status ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Provider</p>
            <p className="mt-1 text-sm font-medium capitalize text-slate-900">{status.provider}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Model</p>
            <p className="mt-1 text-sm font-medium text-slate-900">{status.model}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Authenticated</p>
            <p className="mt-1 text-sm font-medium text-slate-900">{status.authenticated ? "Yes" : "No"}</p>
            {status.error ? <p className="mt-1 text-xs text-red-500">{status.error}</p> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
