import { cn } from "@/lib/utils";
import type { FlagSeverity, SafetyStatus, SummaryStatus, AgentRunStatus, DocumentStatus } from "@/lib/types";

type BadgeVariant =
  | "critical"
  | "high"
  | "medium"
  | "low"
  | "info"
  | "success"
  | "warning"
  | "pending"
  | "default"
  | "blue"
  | "purple";

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
  dot?: boolean;
}

const variantStyles: Record<BadgeVariant, string> = {
  critical: "bg-red-100 text-red-700 border border-red-200",
  high: "bg-orange-100 text-orange-700 border border-orange-200",
  medium: "bg-yellow-100 text-yellow-700 border border-yellow-200",
  low: "bg-sky-100 text-sky-700 border border-sky-200",
  info: "bg-blue-100 text-blue-700 border border-blue-200",
  success: "bg-green-100 text-green-700 border border-green-200",
  warning: "bg-amber-100 text-amber-700 border border-amber-200",
  pending: "bg-slate-100 text-slate-600 border border-slate-200",
  default: "bg-slate-100 text-slate-600 border border-slate-200",
  blue: "bg-medical-blue-100 text-medical-blue-700 border border-medical-blue-200",
  purple: "bg-purple-100 text-purple-700 border border-purple-200",
};

const dotStyles: Record<BadgeVariant, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-yellow-500",
  low: "bg-sky-500",
  info: "bg-blue-500",
  success: "bg-green-500",
  warning: "bg-amber-500",
  pending: "bg-slate-400",
  default: "bg-slate-400",
  blue: "bg-medical-blue-500",
  purple: "bg-purple-500",
};

export function Badge({ variant = "default", children, className, dot }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
        variantStyles[variant],
        className
      )}
    >
      {dot && (
        <span className={cn("h-1.5 w-1.5 flex-shrink-0 rounded-full", dotStyles[variant])} />
      )}
      {children}
    </span>
  );
}

// ── Convenience wrappers ───────────────────────────────────────────────────────

export function SeverityBadge({ severity }: { severity: FlagSeverity }) {
  const map: Record<FlagSeverity, BadgeVariant> = {
    CRITICAL: "critical",
    HIGH: "high",
    MEDIUM: "medium",
    LOW: "low",
    INFO: "info",
  };
  return (
    <Badge variant={map[severity]} dot>
      {severity}
    </Badge>
  );
}

export function SafetyStatusBadge({ status }: { status: SafetyStatus }) {
  const map: Record<SafetyStatus, BadgeVariant> = {
    APPROVED: "success",
    REVIEW_REQUIRED: "warning",
    BLOCKED: "critical",
  };
  return <Badge variant={map[status]}>{status.replace("_", " ")}</Badge>;
}

export function SummaryStatusBadge({ status }: { status: SummaryStatus }) {
  const map: Record<SummaryStatus, BadgeVariant> = {
    PENDING_REVIEW: "pending",
    IN_REVIEW: "warning",
    APPROVED: "success",
    ESCALATED: "critical",
    INCOMPLETE: "default",
  };
  const labels: Record<SummaryStatus, string> = {
    PENDING_REVIEW: "Pending Review",
    IN_REVIEW: "In Review",
    APPROVED: "Approved",
    ESCALATED: "Escalated",
    INCOMPLETE: "Incomplete",
  };
  return <Badge variant={map[status]}>{labels[status]}</Badge>;
}

export function AgentStatusBadge({ status }: { status: AgentRunStatus }) {
  const map: Record<AgentRunStatus, BadgeVariant> = {
    PENDING: "pending",
    RUNNING: "blue",
    COMPLETED: "success",
    ESCALATED: "warning",
    FAILED: "critical",
    TIMED_OUT: "high",
  };
  return (
    <Badge variant={map[status]} dot>
      {status}
    </Badge>
  );
}

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  const map: Record<DocumentStatus, BadgeVariant> = {
    UPLOADED: "pending",
    PROCESSING: "blue",
    PROCESSED: "success",
    FAILED: "critical",
    EMPTY: "default",
  };
  return <Badge variant={map[status]}>{status}</Badge>;
}
