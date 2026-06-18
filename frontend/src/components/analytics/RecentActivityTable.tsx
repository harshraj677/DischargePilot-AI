import Link from "next/link";
import { ClipboardList } from "lucide-react";
import type { ReviewHistoryEntry } from "@/lib/types";
import { SeverityBadge, ReviewActionBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDateTime, truncate } from "@/lib/utils";

interface RecentActivityTableProps {
  entries: ReviewHistoryEntry[];
}

export function RecentActivityTable({ entries }: RecentActivityTableProps) {
  if (entries.length === 0) {
    return (
      <EmptyState
        icon={<ClipboardList className="h-6 w-6" />}
        title="No review activity yet"
        description="Approved, rejected, and acknowledged findings will show up here."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-400">
            <th className="py-2 pr-4">Timestamp</th>
            <th className="py-2 pr-4">Patient</th>
            <th className="py-2 pr-4">Finding</th>
            <th className="py-2 pr-4">Severity</th>
            <th className="py-2 pr-4">Action</th>
            <th className="py-2 pr-4">Reviewer</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50">
          {entries.map((entry) => (
            <tr key={entry.id} className="text-slate-700">
              <td className="py-2.5 pr-4 whitespace-nowrap text-xs text-slate-400">
                {formatDateTime(entry.timestamp)}
              </td>
              <td className="py-2.5 pr-4">
                {entry.patient_id ? (
                  <Link
                    href={`/patients/${entry.patient_id}/timeline`}
                    className="font-medium text-medical-blue-600 hover:text-medical-blue-700"
                  >
                    {entry.patient_name ?? entry.patient_id}
                  </Link>
                ) : (
                  <span className="text-slate-400">—</span>
                )}
              </td>
              <td className="py-2.5 pr-4 text-slate-600">
                {entry.finding_title ? truncate(entry.finding_title, 40) : "—"}
              </td>
              <td className="py-2.5 pr-4">{entry.severity ? <SeverityBadge severity={entry.severity} /> : "—"}</td>
              <td className="py-2.5 pr-4"><ReviewActionBadge action={entry.action} /></td>
              <td className="py-2.5 pr-4 text-slate-600">{entry.reviewer}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
