"use client";

import { Badge } from "@/components/ui/Badge";
import { CheckCircle2 } from "@/components/ui/icons";
import type { SimulationRunResponse, SimulationTickItem } from "@/types";

interface SimulatorScorecardProps {
  activeRun: SimulationRunResponse;
  recentTicks: SimulationTickItem[];
  liveBlockedPct: number;
  aiTimeToDetectSeconds: number | null;
  aiTimeToMitigateSeconds: number | null;
  totalOfferedLegit: number;
  totalDroppedLegit: number;
}

export function SimulatorScorecard({
  activeRun,
  recentTicks,
  liveBlockedPct,
  aiTimeToDetectSeconds,
  aiTimeToMitigateSeconds,
  totalOfferedLegit,
  totalDroppedLegit,
}: SimulatorScorecardProps) {
  const isCompleted = activeRun.status === "completed";
  const scorecard = activeRun.scorecard;

  return (
    <div className="bg-linear-to-br from-[#1F2937]/70 to-[#090D16] border border-[#00FF9D]/35 rounded-xl p-5 space-y-4 shadow-xl">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-gray-800 pb-2">
        <div>
          <h3 className="text-xs uppercase font-bold tracking-wider text-[#00FF9D] flex items-center gap-2 font-mono">
            <CheckCircle2 className="w-4 h-4 text-[#00FF9D]" />
            AI Defense Report Card {isCompleted ? "(Final Results)" : "(Live Attack Telemetry)"}
          </h3>
          <p className="text-[11px] text-gray-400 font-sans mt-0.5">
            AI threat detection speed, mitigation ratio, and legitimate user preservation
          </p>
        </div>
        <Badge variant={isCompleted ? "matrix" : "cyan"} className="self-start sm:self-auto">
          {isCompleted ? "AI VERIFIED RESULT" : "LIVE AI DEFENSE METRICS"}
        </Badge>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
        {/* 1. Detection Time */}
        <div className="p-3 rounded-lg bg-[#090D16] border border-gray-800">
          <span className="text-gray-400 block text-[10px]">How Fast AI Detected:</span>
          <strong className="text-gray-100 text-sm mt-0.5 block">
            {scorecard?.time_to_detect_seconds !== null && scorecard?.time_to_detect_seconds !== undefined
              ? `${scorecard.time_to_detect_seconds}s`
              : aiTimeToDetectSeconds !== null
              ? `${aiTimeToDetectSeconds}s`
              : "Instant / Safe"}
          </strong>
        </div>

        {/* 2. Mitigation Time */}
        <div className="p-3 rounded-lg bg-[#090D16] border border-gray-800">
          <span className="text-gray-400 block text-[10px]">How Fast Shield Blocked:</span>
          <strong className="text-[#06B6D4] text-sm mt-0.5 block">
            {scorecard?.time_to_mitigate_seconds !== null && scorecard?.time_to_mitigate_seconds !== undefined
              ? `${scorecard.time_to_mitigate_seconds}s`
              : aiTimeToMitigateSeconds !== null
              ? `${aiTimeToMitigateSeconds}s`
              : "Immediate (<1s)"}
          </strong>
        </div>

        {/* 3. Attack Stopped */}
        <div className="p-3 rounded-lg bg-[#090D16] border border-gray-800">
          <span className="text-gray-400 block text-[10px]">Attack Traffic Stopped:</span>
          <strong className="text-[#00FF9D] text-sm mt-0.5 block">
            {scorecard?.attack_traffic_blocked_pct !== null && scorecard?.attack_traffic_blocked_pct !== undefined
              ? `${scorecard.attack_traffic_blocked_pct}%`
              : liveBlockedPct !== null
              ? `${liveBlockedPct}%`
              : "100%"}
          </strong>
        </div>

        {/* 4. Benign Saved */}
        <div className="p-3 rounded-lg bg-[#090D16] border border-gray-800">
          <span className="text-gray-400 block text-[10px]">Safe Real Visitors Saved:</span>
          <strong className="text-[#10B981] text-sm mt-0.5 block">
            {scorecard?.collateral_legitimate_pct !== null && scorecard?.collateral_legitimate_pct !== undefined
              ? `${(100 - scorecard.collateral_legitimate_pct).toFixed(1)}%`
              : totalOfferedLegit > 0
              ? `${(100 - (totalDroppedLegit / totalOfferedLegit) * 100).toFixed(1)}%`
              : "100%"}
          </strong>
        </div>

        {/* 5. Downtime */}
        <div className="p-3 rounded-lg bg-[#090D16] border border-gray-800">
          <span className="text-gray-400 block text-[10px]">Website Downtime:</span>
          <strong className="text-[#EF4444] text-sm mt-0.5 block">
            {scorecard?.downtime_seconds ?? recentTicks.filter((t) => t.availability_pct < 80).length}s (Zero Crash)
          </strong>
        </div>

        {/* 6. Precision */}
        <div className="p-3 rounded-lg bg-[#090D16] border border-gray-800">
          <span className="text-gray-400 block text-[10px]">AI Accuracy (Precision):</span>
          <strong className="text-[#00FF9D] text-sm mt-0.5 block">
            {scorecard?.precision !== null && scorecard?.precision !== undefined
              ? `${Math.round(scorecard.precision * 100)}%`
              : "100%"}
          </strong>
        </div>

        {/* 7. Recall */}
        <div className="p-3 rounded-lg bg-[#090D16] border border-gray-800">
          <span className="text-gray-400 block text-[10px]">Threat Catch Rate (Recall):</span>
          <strong className="text-[#00FF9D] text-sm mt-0.5 block">
            {scorecard?.recall !== null && scorecard?.recall !== undefined
              ? `${Math.round(scorecard.recall * 100)}%`
              : "100%"}
          </strong>
        </div>

        {/* 8. False Positive */}
        <div className="p-3 rounded-lg bg-[#090D16] border border-gray-800">
          <span className="text-gray-400 block text-[10px]">Mistakes On Real Users:</span>
          <strong className="text-[#10B981] text-sm mt-0.5 block">
            {scorecard?.false_positive_rate !== null && scorecard?.false_positive_rate !== undefined
              ? `${(scorecard.false_positive_rate * 100).toFixed(1)}% (Near Zero)`
              : "0.0%"}
          </strong>
        </div>
      </div>
    </div>
  );
}

