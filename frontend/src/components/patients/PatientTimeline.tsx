import {
  UserPlus,
  FileText,
  ScrollText,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Eye,
} from "lucide-react";
import type { TimelineEvent, TimelineEventType } from "@/lib/types";
import { SeverityBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

const EVENT_STYLES: Record<TimelineEventType, { dot: string; icon: React.ReactNode }> = {
  patient_created: { dot: "bg-slate-400", icon: <UserPlus className="h-3.5 w-3.5" /> },
  document_uploaded: { dot: "bg-medical-blue-500", icon: <FileText className="h-3.5 w-3.5" /> },
  summary_generated: { dot: "bg-clinical-green-500", icon: <ScrollText className="h-3.5 w-3.5" /> },
  finding_created: { dot: "bg-amber-500", icon: <AlertTriangle className="h-3.5 w-3.5" /> },
  finding_approved: { dot: "bg-clinical-green-500", icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
  finding_rejected: { dot: "bg-red-500", icon: <XCircle className="h-3.5 w-3.5" /> },
  finding_acknowledged: { dot: "bg-purple-500", icon: <Eye className="h-3.5 w-3.5" /> },
};

interface PatientTimelineProps {
  events: TimelineEvent[];
}

export function PatientTimeline({ events }: PatientTimelineProps) {
  if (events.length === 0) {
    return (
      <EmptyState
        icon={<FileText className="h-6 w-6" />}
        title="No timeline events yet"
        description="Events appear as documents are uploaded and summaries are generated."
      />
    );
  }

  return (
    <ol className="relative space-y-6 border-l border-slate-200 pl-6">
      {events.map((event, i) => {
        const style = EVENT_STYLES[event.type];
        return (
          <li key={i} className="relative">
            <span
              className={cn(
                "absolute -left-[31px] flex h-6 w-6 items-center justify-center rounded-full text-white",
                style.dot
              )}
            >
              {style.icon}
            </span>
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold text-slate-900">{event.title}</p>
              {event.severity && <SeverityBadge severity={event.severity} />}
            </div>
            {event.description && (
              <p className="mt-0.5 text-sm text-slate-500">{event.description}</p>
            )}
            <p className="mt-1 text-xs text-slate-400">{formatDateTime(event.timestamp)}</p>
          </li>
        );
      })}
    </ol>
  );
}
