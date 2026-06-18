"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TopMissingField } from "@/lib/types";
import { MISSING_FIELD_LABELS } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { ListChecks } from "lucide-react";

const CustomTooltipStyle = {
  borderRadius: 8,
  border: "1px solid #e2e8f0",
  boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
  fontSize: 12,
};

interface TopMissingFieldsChartProps {
  fields: TopMissingField[];
}

export function TopMissingFieldsChart({ fields }: TopMissingFieldsChartProps) {
  const hasData = fields.some((f) => f.count > 0);
  if (!hasData) {
    return (
      <EmptyState
        icon={<ListChecks className="h-6 w-6" />}
        title="No missing fields"
        description="Tracked required fields are fully documented across recent summaries."
      />
    );
  }

  const data = fields.map((f) => ({ field: MISSING_FIELD_LABELS[f.field] ?? f.field, count: f.count }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis type="number" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} allowDecimals={false} />
        <YAxis type="category" dataKey="field" width={130} tick={{ fontSize: 11, fill: "#475569" }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={CustomTooltipStyle} />
        <Bar dataKey="count" fill="#ea580c" radius={[0, 4, 4, 0]} name="Occurrences" />
      </BarChart>
    </ResponsiveContainer>
  );
}
