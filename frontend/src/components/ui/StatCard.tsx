import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: {
    value: number;
    label?: string;
  };
  variant?: "default" | "blue" | "green" | "red" | "amber";
  loading?: boolean;
  className?: string;
}

const variantStyles = {
  default: {
    card: "border-slate-200 bg-white",
    icon: "bg-slate-100 text-slate-600",
    value: "text-slate-900",
  },
  blue: {
    card: "border-medical-blue-100 bg-medical-blue-50",
    icon: "bg-medical-blue-100 text-medical-blue-600",
    value: "text-medical-blue-900",
  },
  green: {
    card: "border-clinical-green-100 bg-clinical-green-50",
    icon: "bg-clinical-green-100 text-clinical-green-600",
    value: "text-clinical-green-900",
  },
  red: {
    card: "border-red-100 bg-red-50",
    icon: "bg-red-100 text-red-600",
    value: "text-red-900",
  },
  amber: {
    card: "border-amber-100 bg-amber-50",
    icon: "bg-amber-100 text-amber-600",
    value: "text-amber-900",
  },
};

export function StatCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  variant = "default",
  loading = false,
  className,
}: StatCardProps) {
  const styles = variantStyles[variant];

  return (
    <div className={cn("rounded-xl border p-5", styles.card, className)}>
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
          {loading ? (
            <div className="mt-2 h-8 w-24 animate-pulse rounded bg-slate-200" />
          ) : (
            <p className={cn("mt-1 text-2xl font-bold tabular-nums", styles.value)}>
              {value}
            </p>
          )}
          {subtitle && !loading && (
            <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>
          )}
          {trend != null && !loading && (
            <div className="mt-2 flex items-center gap-1">
              {trend.value > 0 ? (
                <TrendingUp className="h-3.5 w-3.5 text-clinical-green-600" />
              ) : trend.value < 0 ? (
                <TrendingDown className="h-3.5 w-3.5 text-red-500" />
              ) : (
                <Minus className="h-3.5 w-3.5 text-slate-400" />
              )}
              <span
                className={cn(
                  "text-xs font-medium",
                  trend.value > 0
                    ? "text-clinical-green-600"
                    : trend.value < 0
                    ? "text-red-500"
                    : "text-slate-400"
                )}
              >
                {trend.value > 0 ? "+" : ""}
                {trend.value}%
              </span>
              {trend.label && (
                <span className="text-xs text-slate-400">{trend.label}</span>
              )}
            </div>
          )}
        </div>
        {icon && (
          <div className={cn("flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg", styles.icon)}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
