"use client";

import { RadialBar, RadialBarChart, ResponsiveContainer, Legend } from "recharts";

interface ApprovalGaugeProps {
  approvalRate: number;
  rejectionRate: number;
  acknowledgmentRate: number;
}

export function ApprovalGauge({ approvalRate, rejectionRate, acknowledgmentRate }: ApprovalGaugeProps) {
  const data = [
    { name: "Approved", value: Math.round(approvalRate * 100), fill: "#059669" },
    { name: "Rejected", value: Math.round(rejectionRate * 100), fill: "#dc2626" },
    { name: "Acknowledged", value: Math.round(acknowledgmentRate * 100), fill: "#7c3aed" },
  ];

  const allZero = data.every((d) => d.value === 0);

  return (
    <div>
      <ResponsiveContainer width="100%" height={200}>
        <RadialBarChart
          data={data}
          innerRadius="30%"
          outerRadius="100%"
          startAngle={180}
          endAngle={-180}
          barCategoryGap="20%"
        >
          <RadialBar background dataKey="value" cornerRadius={6} />
          <Legend
            iconSize={10}
            iconType="circle"
            layout="horizontal"
            verticalAlign="bottom"
            wrapperStyle={{ fontSize: 12 }}
            formatter={(value: string) => value}
          />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="-mt-4 grid grid-cols-3 gap-2 text-center">
        {data.map((item) => (
          <div key={item.name}>
            <p className="text-lg font-bold tabular-nums" style={{ color: item.fill }}>
              {allZero ? "—" : `${item.value}%`}
            </p>
            <p className="text-xs text-slate-400">{item.name}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
