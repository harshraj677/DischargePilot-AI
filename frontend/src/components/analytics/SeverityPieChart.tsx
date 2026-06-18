"use client";

import { Pie, PieChart, Cell, Tooltip, ResponsiveContainer } from "recharts";
import type { SeverityDistribution } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { PieChart as PieChartIcon } from "lucide-react";

const SEVERITY_COLORS: Record<keyof SeverityDistribution, string> = {
  HIGH: "#ea580c",
  MEDIUM: "#ca8a04",
  LOW: "#0284c7",
  INFO: "#2563eb",
};

const CustomTooltipStyle = {
  borderRadius: 8,
  border: "1px solid #e2e8f0",
  boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
  fontSize: 12,
};

interface SeverityPieChartProps {
  distribution: SeverityDistribution;
}

export function SeverityPieChart({ distribution }: SeverityPieChartProps) {
  const data = (Object.keys(distribution) as Array<keyof SeverityDistribution>).map((key) => ({
    name: key,
    value: distribution[key],
    color: SEVERITY_COLORS[key],
  }));
  const total = data.reduce((sum, d) => sum + d.value, 0);

  if (total === 0) {
    return (
      <EmptyState
        icon={<PieChartIcon className="h-6 w-6" />}
        title="No findings yet"
        description="Severity distribution will appear once discharge summaries are generated."
      />
    );
  }

  return (
    <div className="flex items-center">
      <ResponsiveContainer width="50%" height={200}>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3} dataKey="value">
            {data.map((entry) => (
              <Cell key={entry.name} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip contentStyle={CustomTooltipStyle} />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex-1 space-y-3">
        {data.map((item) => (
          <div key={item.name} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 flex-shrink-0 rounded-full" style={{ backgroundColor: item.color }} />
              <span className="text-sm text-slate-600">{item.name}</span>
            </div>
            <div className="text-right">
              <span className="text-sm font-semibold text-slate-900">{item.value}</span>
              <span className="ml-1 text-xs text-slate-400">
                ({total > 0 ? Math.round((item.value / total) * 100) : 0}%)
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
