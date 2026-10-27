"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SimulationTickItem } from "@/types";

interface SimulationLiveChartProps {
  ticks: SimulationTickItem[];
}

export function SimulationLiveChart({ ticks }: SimulationLiveChartProps) {
  if (!ticks || ticks.length === 0) {
    return (
      <div className="h-64 w-full flex flex-col items-center justify-center border border-dashed border-[rgba(75,85,99,0.4)] rounded-xl bg-[rgba(9,13,22,0.6)] text-[#9CA3AF] text-xs font-mono">
        <span className="text-[#9CA3AF]">No simulation telemetry frames recorded yet.</span>
        <span className="text-[11px] text-[#00FF9D]/70 mt-1">
          Execute &quot;Start Attack&quot; or &quot;Step +1s&quot; to begin stream replay.
        </span>
      </div>
    );
  }

  // Take the most recent 60 ticks for clean real-time rendering
  const displayTicks = ticks.slice(-60).map((t) => ({
    time: `t+${t.tick}s`,
    tick: t.tick,
    "Normal Traffic": Math.round(t.offered_legit_pps),
    "Attack Traffic": Math.round(t.offered_attack_pps),
    "Attack Blocked": Math.round(t.dropped_attack_pps),
    "Availability %": Math.round(t.availability_pct),
    "Latency (ms)": Math.round(t.latency_ms),
    action: t.policy_action,
  }));

  return (
    <div className="h-72 w-full font-mono">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={displayTicks} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
          <defs>
            <linearGradient id="attackGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#EF4444" stopOpacity={0.45} />
              <stop offset="95%" stopColor="#EF4444" stopOpacity={0.0} />
            </linearGradient>
            <linearGradient id="normalGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#00FF9D" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#00FF9D" stopOpacity={0.0} />
            </linearGradient>
            <linearGradient id="mitigatedGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#06B6D4" stopOpacity={0.35} />
              <stop offset="95%" stopColor="#06B6D4" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(75, 85, 99, 0.2)" />
          <XAxis dataKey="time" stroke="#9CA3AF" tick={{ fontSize: 10 }} />
          <YAxis stroke="#9CA3AF" tick={{ fontSize: 10 }} />
          <Tooltip
            content={({ active, payload, label }) => {
              if (active && payload && payload.length) {
                const item = payload[0]?.payload;
                return (
                  <div className="bg-[rgba(31,41,55,0.95)] border border-[rgba(75,85,99,0.4)] backdrop-blur-xl rounded-lg p-3 text-xs shadow-2xl space-y-1.5 font-mono">
                    <div className="font-bold text-[#00FF9D] border-b border-[rgba(75,85,99,0.3)] pb-1 flex items-center justify-between gap-4">
                      <span>FRAME: {label}</span>
                      <span className="text-[10px] text-[#06B6D4]">eBPF Telemetry</span>
                    </div>
                    <div className="flex justify-between gap-4 text-[#EF4444]">
                      <span>Offered Ingress Attack:</span>
                      <strong>{item["Attack Traffic"].toLocaleString()} PPS</strong>
                    </div>
                    <div className="flex justify-between gap-4 text-[#00FF9D]">
                      <span>Legitimate Workload:</span>
                      <strong>{item["Normal Traffic"].toLocaleString()} PPS</strong>
                    </div>
                    <div className="flex justify-between gap-4 text-[#06B6D4]">
                      <span>eBPF XDP Dropped:</span>
                      <strong>{item["Attack Blocked"].toLocaleString()} PPS</strong>
                    </div>
                    <div className="flex justify-between gap-4 text-[#F59E0B]">
                      <span>Target Availability:</span>
                      <strong>{item["Availability %"]}%</strong>
                    </div>
                    <div className="flex justify-between gap-4 text-[#9CA3AF] border-t border-[rgba(75,85,99,0.3)] pt-1 text-[11px]">
                      <span>Policy Decision Gate:</span>
                      <strong className="text-[#00FF9D] uppercase tracking-wider">{item.action}</strong>
                    </div>
                  </div>
                );
              }
              return null;
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }}
            formatter={(val) => <span className="text-[#9CA3AF]">{val}</span>}
          />
          <Area
            type="monotone"
            dataKey="Attack Traffic"
            stroke="#EF4444"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#attackGradient)"
            name="Attack Ingress (PPS)"
          />
          <Area
            type="monotone"
            dataKey="Normal Traffic"
            stroke="#00FF9D"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#normalGradient)"
            name="Benign Traffic (PPS)"
          />
          <Area
            type="monotone"
            dataKey="Attack Blocked"
            stroke="#06B6D4"
            strokeWidth={1.5}
            strokeDasharray="4 4"
            fillOpacity={1}
            fill="url(#mitigatedGradient)"
            name="Mitigated Dropped (PPS)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
