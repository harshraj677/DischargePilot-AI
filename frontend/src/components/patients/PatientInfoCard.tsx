import { Calendar, Hash, User, ShieldCheck, Gauge } from "lucide-react";
import type { PatientTimelineInfo } from "@/lib/types";
import { formatDate, formatScore } from "@/lib/utils";

interface PatientInfoCardProps {
  patient: PatientTimelineInfo;
  latestSafetyScore: number | null;
  latestCompletenessScore: number | null;
}

export function PatientInfoCard({ patient, latestSafetyScore, latestCompletenessScore }: PatientInfoCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-medical-blue-100 text-lg font-bold text-medical-blue-600">
          {patient.name.charAt(0).toUpperCase()}
        </div>
        <h2 className="font-semibold text-slate-900">{patient.name}</h2>
      </div>

      <div className="space-y-2.5 text-sm">
        {patient.mrn && <InfoRow icon={<Hash className="h-3.5 w-3.5" />} label="MRN" value={patient.mrn} mono />}
        {patient.dob && <InfoRow icon={<Calendar className="h-3.5 w-3.5" />} label="DOB" value={formatDate(patient.dob)} />}
        {patient.gender && <InfoRow icon={<User className="h-3.5 w-3.5" />} label="Gender" value={patient.gender} />}
        <InfoRow icon={<Calendar className="h-3.5 w-3.5" />} label="Created" value={formatDate(patient.created_at)} />
        <InfoRow
          icon={<ShieldCheck className="h-3.5 w-3.5" />}
          label="Safety"
          value={formatScore(latestSafetyScore)}
        />
        <InfoRow
          icon={<Gauge className="h-3.5 w-3.5" />}
          label="Completeness"
          value={formatScore(latestCompletenessScore)}
        />
      </div>
    </div>
  );
}

function InfoRow({ icon, label, value, mono = false }: { icon: React.ReactNode; label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start gap-2">
      <span className="mt-0.5 flex-shrink-0 text-slate-400">{icon}</span>
      <span className="w-24 flex-shrink-0 text-xs text-slate-400">{label}</span>
      <span className={`text-slate-700 ${mono ? "font-mono text-xs" : ""}`}>{value}</span>
    </div>
  );
}
