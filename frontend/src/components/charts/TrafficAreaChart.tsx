"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TrafficSeriesPoint } from "@/types";

interface TrafficAreaChartProps {
  data: TrafficSeriesPoint[];
}

export function TrafficAreaChart({ data }: TrafficAreaChartProps) {
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="ppsGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#00e5ff" stopOpacity={0.35} />
              <stop offset="95%" stopColor="#00e5ff" stopOpacity={0.0} />
            </linearGradient>
            <linearGradient id="synGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(56, 189, 248, 0.1)" />
          <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 11 }} />
          <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0a1628",
              borderColor: "rgba(0, 229, 255, 0.3)",
              borderRadius: "0.5rem",
              fontSize: "12px",
              color: "#f0f6fc",
            }}
          />
          <Area
            type="monotone"
            dataKey="pps"
            stroke="#00e5ff"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#ppsGradient)"
            name="Forward PPS"
          />
          <Area
            type="monotone"
            dataKey="syn_pps"
            stroke="#38bdf8"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#synGradient)"
            name="SYN PPS"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

