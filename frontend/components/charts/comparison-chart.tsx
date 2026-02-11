"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface ComparisonChartProps {
  data: {
    name: string;
    [key: string]: string | number;
  }[];
  dataKeys: { key: string; color: string; name: string }[];
  xAxisKey?: string;
}

export function ComparisonChart({
  data,
  dataKeys,
  xAxisKey = "name",
}: ComparisonChartProps) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart
        data={data}
        margin={{
          top: 5,
          right: 30,
          left: 20,
          bottom: 5,
        }}
      >
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey={xAxisKey} />
        <YAxis />
        <Tooltip />
        <Legend />
        {dataKeys.map((dk) => (
          <Bar key={dk.key} dataKey={dk.key} fill={dk.color} name={dk.name} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
