import { StatCard } from "@/components/ui/StatCard";

interface AnalyticsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  variant?: "default" | "blue" | "green" | "red" | "amber";
  loading?: boolean;
}

/** Thin analytics-dashboard wrapper over StatCard — keeps KPI cards visually consistent with the rest of the app. */
export function AnalyticsCard({ title, value, subtitle, icon, variant = "default", loading }: AnalyticsCardProps) {
  return <StatCard title={title} value={value} subtitle={subtitle} icon={icon} variant={variant} loading={loading} />;
}
