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
  if (data.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center rounded-lg border border-dashed border-[rgba(75,85,99,0.3)] text-center text-xs text-[#9CA3AF]">
        Start a simulation to view synthetic traffic over time.
      </div>
    );
  }

  return (
    <div className="h-72 w-full font-mono">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="normalGreenGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#00FF9D" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#00FF9D" stopOpacity={0.0} />
            </linearGradient>
            <linearGradient id="attackRedGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#EF4444" stopOpacity={0.45} />
              <stop offset="95%" stopColor="#EF4444" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(75, 85, 99, 0.2)" />
          <XAxis dataKey="time" stroke="#9CA3AF" tick={{ fontSize: 10 }} />
          <YAxis stroke="#9CA3AF" tick={{ fontSize: 10 }} />
          <Tooltip
            content={({ active, payload, label }) => {
              if (active && payload && payload.length) {
                const item = payload[0]?.payload;
                const normal = item.normal_pps ?? item.pps ?? 0;
                const attack = item.attack_pps ?? item.syn_pps ?? 0;
                const total = normal + attack;
                const isAttack = attack > 0;
                return (
                  <div className="bg-[rgba(31,41,55,0.95)] border border-[rgba(75,85,99,0.4)] backdrop-blur-xl rounded-lg p-3 text-xs shadow-2xl space-y-1.5 font-mono">
                    <div className="font-bold text-gray-200 border-b border-[rgba(75,85,99,0.3)] pb-1 flex items-center justify-between gap-4">
                      <span>TIME: {label}</span>
                      <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${
                        isAttack
                          ? "bg-[rgba(239,68,68,0.2)] text-[#EF4444] border-red-500/40"
                          : "bg-[rgba(0,255,157,0.15)] text-[#00FF9D] border-[#00FF9D]/40"
                      }`}>
                        {isAttack ? "⚠️ DDoS Attack Detected" : "✅ 100% Benign"}
                      </span>
                    </div>
                    <div className="flex justify-between gap-4 text-[#00FF9D]">
                      <span>Normal Visitors:</span>
                      <strong>{Number(normal).toLocaleString()} PPS</strong>
                    </div>
                    <div className="flex justify-between gap-4 text-[#EF4444]">
                      <span>Attack Traffic:</span>
                      <strong>{Number(attack).toLocaleString()} PPS</strong>
                    </div>
                    <div className="flex justify-between gap-4 text-gray-100 border-t border-[rgba(75,85,99,0.3)] pt-1 text-[11px]">
                      <span>Total Flow Volume:</span>
                      <strong>{Number(total).toLocaleString()} PPS</strong>
                    </div>
                  </div>
                );
              }
              return null;
            }}
          />
          {/* Normal Traffic Area in Matrix Neon Green */}
          <Area
            type="monotone"
            dataKey="normal_pps"
            stroke="#00FF9D"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#normalGreenGradient)"
            name="Normal Visitors (Benign PPS)"
          />
          {/* Attack Traffic Area in Bright Alert Red */}
          <Area
            type="monotone"
            dataKey="attack_pps"
            stroke="#EF4444"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#attackRedGradient)"
            name="Attack Flood (DDoS PPS)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
