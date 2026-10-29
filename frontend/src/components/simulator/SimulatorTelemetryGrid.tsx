"use client";

import { Activity, AlertTriangle, Server, Shield } from "@/components/ui/icons";
import type { SimulationTickItem } from "@/types";

interface SimulatorTelemetryGridProps {
  latestTick: SimulationTickItem | null;
  liveBlockedPct: number;
  isShieldActive: boolean;
}

export function SimulatorTelemetryGrid({
  latestTick,
  liveBlockedPct,
  isShieldActive,
}: SimulatorTelemetryGridProps) {
  const currentAvail = latestTick?.availability_pct ?? 100.0;
  let availColor = "text-[#10B981]";
  let availBg = "bg-emerald-500/10 border-emerald-500/40";
  let availStatusText = "Server Healthy (All users connected)";

  if (currentAvail < 60) {
    availColor = "text-[#EF4444]";
    availBg = "bg-red-500/15 border-red-500/40";
    availStatusText = "Severe Outage (Server down - dropping requests)";
  } else if (currentAvail < 90) {
    availColor = "text-[#F59E0B]";
    availBg = "bg-amber-500/15 border-amber-500/40";
    availStatusText = "Slow Response (High load - degraded)";
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {/* 1. Server Availability */}
      <div className={`p-3 rounded-xl border ${availBg}`}>
        <div className="flex items-center justify-between text-[11px] font-mono text-gray-400 mb-1">
          <span>Target Health</span>
          <Activity className="w-3.5 h-3.5" />
        </div>
        <div className={`text-xl font-bold font-mono ${availColor}`}>
          {currentAvail.toFixed(1)}%
        </div>
        <div className="text-[10px] text-gray-400 mt-1 truncate" title={availStatusText}>
          {availStatusText}
        </div>
      </div>

      {/* 2. Latency */}
      <div className="bg-[#090D16] border border-gray-700/60 p-3 rounded-xl">
        <div className="flex items-center justify-between text-[11px] font-mono text-gray-400 mb-1">
          <span>P95 Latency</span>
          <Server className="w-3.5 h-3.5 text-[#06B6D4]" />
        </div>
        <div className="text-xl font-bold font-mono text-[#06B6D4]">
          {latestTick?.latency_ms ? `${latestTick.latency_ms.toFixed(1)} ms` : "15.0 ms"}
        </div>
        <div className="text-[10px] text-gray-400 mt-1">
          {latestTick && latestTick.latency_ms > 35 ? "Queue Congested" : "Normal Latency"}
        </div>
      </div>

      {/* 3. Attack Traffic */}
      <div className="bg-[#090D16] border border-gray-700/60 p-3 rounded-xl">
        <div className="flex items-center justify-between text-[11px] font-mono text-gray-400 mb-1">
          <span>Attack Ingress</span>
          <AlertTriangle className="w-3.5 h-3.5 text-[#EF4444]" />
        </div>
        <div className="text-xl font-bold font-mono text-[#EF4444]">
          {latestTick?.offered_attack_pps
            ? `${Math.round(latestTick.offered_attack_pps).toLocaleString()} PPS`
            : "0 PPS"}
        </div>
        <div className="text-[10px] text-[#00FF9D] mt-1 font-mono">
          Dropped: {latestTick ? Math.round(latestTick.dropped_attack_pps).toLocaleString() : 0} PPS ({liveBlockedPct}%)
        </div>
      </div>

      {/* 4. Policy Defense Action */}
      <div className="bg-[#090D16] border border-gray-700/60 p-3 rounded-xl">
        <div className="flex items-center justify-between text-[11px] font-mono text-gray-400 mb-1">
          <span>Defense Shield</span>
          <Shield
            className={`w-3.5 h-3.5 ${isShieldActive ? "text-[#00FF9D] animate-pulse" : "text-[#00FF9D]"}`}
          />
        </div>
        <div className="text-xs font-bold font-mono text-[#00FF9D] uppercase mt-1">
          {isShieldActive
            ? "Rate Limiting Active"
            : latestTick?.policy_action === "alert"
            ? "Alert Triggered"
            : "Monitoring Normal"}
        </div>
        <div className="text-[10px] text-gray-400 mt-1 font-mono">
          Active Rules: {latestTick?.active_mitigations_count ?? (isShieldActive ? 1 : 0)}
        </div>
      </div>
    </div>
  );
}

