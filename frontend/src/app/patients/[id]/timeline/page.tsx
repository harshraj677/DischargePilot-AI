"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { PatientInfoCard } from "@/components/patients/PatientInfoCard";
import { PatientTimeline } from "@/components/patients/PatientTimeline";
import { timeline as timelineApi } from "@/lib/api";
import type { PatientTimelineResponse } from "@/lib/types";

export default function PatientTimelinePage() {
  const { id: patientId } = useParams<{ id: string }>();
  const [data, setData] = useState<PatientTimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    timelineApi
      .get(patientId)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load timeline"))
      .finally(() => setLoading(false));
  }, [patientId]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-slate-200" />
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="h-64 animate-pulse rounded-xl bg-slate-200 lg:col-span-1" />
          <div className="h-64 animate-pulse rounded-xl bg-slate-200 lg:col-span-2" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center text-sm text-red-600">
        {error ?? "Timeline not found."}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${data.patient.name} — Timeline`}
        subtitle="Full clinical review history for this patient"
        breadcrumbs={[
          { label: "Patients", href: "/patients" },
          { label: data.patient.name, href: `/patients/${patientId}` },
          { label: "Timeline" },
        ]}
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <PatientInfoCard
            patient={data.patient}
            latestSafetyScore={data.latest_safety_score}
            latestCompletenessScore={data.latest_completeness_score}
          />
        </div>
        <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="mb-4 text-sm font-semibold text-slate-900">Timeline</h3>
          <PatientTimeline events={data.events} />
        </div>
      </div>
    </div>
  );
}
