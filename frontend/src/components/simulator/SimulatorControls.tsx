"use client";

import { Button } from "@/components/ui/Button";
import {
  Download,
  FastForward,
  Pause,
  Play,
  RotateCcw,
  Square,
} from "@/components/ui/icons";
import type { SimulationRunResponse } from "@/types";

interface SimulatorControlsProps {
  activeRun: SimulationRunResponse;
  isStepping: boolean;
  isExportingCsv: boolean;
  isExportingJson: boolean;
  onControl: (action: "start" | "pause" | "resume" | "step" | "cancel" | "reset") => void;
  onExport: (format: "csv" | "json") => void;
}

export function SimulatorControls({
  activeRun,
  isStepping,
  isExportingCsv,
  isExportingJson,
  onControl,
  onExport,
}: SimulatorControlsProps) {
  const totalTicks = activeRun.total_ticks ?? 60;
  const currentTick = activeRun.current_tick ?? 0;
  const progressPct = Math.min(100, Math.round((currentTick / Math.max(1, totalTicks)) * 100));

  return (
    <div className="space-y-4">
      {/* Top Header & Buttons */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-gray-800 pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="text-sm font-mono text-[#00FF9D] font-bold">{activeRun.run_id}</span>
            <span
              className={`text-[10px] uppercase font-mono px-2.5 py-0.5 rounded-full font-bold border ${
                activeRun.status === "running"
                  ? "bg-red-500/20 text-[#EF4444] border-red-500/40 animate-pulse"
                  : activeRun.status === "completed"
                  ? "bg-emerald-500/15 text-[#00FF9D] border-[#00FF9D]/40"
                  : activeRun.status === "paused"
                  ? "bg-amber-500/20 text-[#F59E0B] border-amber-500/40"
                  : "bg-[#1F2937] text-gray-400 border-gray-700/60"
              }`}
            >
              ● {activeRun.status}
            </span>
          </div>
          <div className="text-xs text-gray-400 font-mono mt-0.5">
            Attack: <strong className="text-gray-100">{activeRun.scenario_type}</strong> · Speed:{" "}
            <strong>{activeRun.speed_multiplier}x</strong> · Seed: {activeRun.seed}
          </div>
        </div>

        {/* Action Buttons Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Start / Resume */}
          {activeRun.status !== "running" &&
            activeRun.status !== "completed" &&
            activeRun.status !== "cancelled" && (
              <Button
                variant="primary"
                size="sm"
                onClick={() => onControl(activeRun.status === "paused" ? "resume" : "start")}
              >
                <Play className="w-3.5 h-3.5" />
                {activeRun.status === "paused" ? "Resume" : "Start Attack"}
              </Button>
            )}

          {/* Pause */}
          {activeRun.status === "running" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onControl("pause")}
            >
              <Pause className="w-3.5 h-3.5" />
              Pause
            </Button>
          )}

          {/* Single Step */}
          {activeRun.status !== "completed" && activeRun.status !== "cancelled" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onControl("step")}
              disabled={isStepping}
            >
              <FastForward className="w-3.5 h-3.5 text-[#00FF9D]" />
              {isStepping ? "Stepping..." : "Step +1s"}
            </Button>
          )}

          {/* Cancel / Stop */}
          {activeRun.status !== "completed" && activeRun.status !== "cancelled" && (
            <Button
              variant="danger"
              size="sm"
              onClick={() => onControl("cancel")}
            >
              <Square className="w-3 h-3" />
              Stop
            </Button>
          )}

          {/* Reset */}
          {(activeRun.status === "completed" ||
            activeRun.status === "cancelled" ||
            activeRun.status === "paused") && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onControl("reset")}
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset
            </Button>
          )}

          {/* Export Buttons */}
          <Button
            variant="outline"
            size="sm"
            loading={isExportingCsv}
            onClick={() => onExport("csv")}
            className="text-xs"
          >
            <Download className="w-3.5 h-3.5 text-[#00FF9D]" />
            CSV
          </Button>
          <Button
            variant="outline"
            size="sm"
            loading={isExportingJson}
            onClick={() => onExport("json")}
            className="text-xs"
          >
            <Download className="w-3.5 h-3.5 text-[#06B6D4]" />
            JSON
          </Button>
        </div>
      </div>

      {/* Virtual Progress Bar */}
      <div className="space-y-1.5 font-mono">
        <div className="flex justify-between text-xs">
          <span className="text-gray-200 font-medium">
            Simulation Progress: {progressPct}%
          </span>
          <span className="text-gray-400">
            Tick {currentTick} / {totalTicks} seconds
          </span>
        </div>
        <div className="w-full bg-[#090D16] h-2.5 rounded-full overflow-hidden border border-gray-700/50">
          <div
            className={`h-full transition-all duration-300 rounded-full ${
              activeRun.status === "running"
                ? "bg-[#EF4444] shadow-[0_0_12px_#EF4444]"
                : "bg-[#00FF9D] shadow-[0_0_12px_#00FF9D]"
            }`}
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

