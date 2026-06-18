"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TopConflict } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { truncate } from "@/lib/utils";
import { AlertTriangle } from "lucide-react";

const CustomTooltipStyle = {
  borderRadius: 8,
  border: "1px solid #e2e8f0",
  boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
  fontSize: 12,
};

interface TopConflictsChartProps {
  conflicts: TopConflict[];
}

export function TopConflictsChart({ conflicts }: TopConflictsChartProps) {
  if (conflicts.length === 0) {
    return (
      <EmptyState
        icon={<AlertTriangle className="h-6 w-6" />}
        title="No conflicts detected"
        description="Medication and clinical conflicts will appear here once findings are generated."
      />
    );
  }

  const data = conflicts.map((c) => ({ title: truncate(c.title, 28), fullTitle: c.title, count: c.count }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis type="number" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} allowDecimals={false} />
        <YAxis type="category" dataKey="title" width={160} tick={{ fontSize: 11, fill: "#475569" }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={CustomTooltipStyle}
          formatter={(value: number) => [value, "Occurrences"]}
          labelFormatter={(_label, payload) => payload?.[0]?.payload?.fullTitle ?? _label}
        />
        <Bar dataKey="count" fill="#dc2626" radius={[0, 4, 4, 0]} name="Occurrences" />
      </BarChart>
    </ResponsiveContainer>
  );
}
