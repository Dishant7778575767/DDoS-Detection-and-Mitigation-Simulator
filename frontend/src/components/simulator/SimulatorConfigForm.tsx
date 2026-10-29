"use client";

import { Button } from "@/components/ui/Button";
import { Info, Zap } from "@/components/ui/icons";
import type { ScenarioType } from "@/types";
import { SCENARIO_DESCRIPTIONS } from "./constants";

interface SimulatorConfigFormProps {
  scenarioType: ScenarioType;
  setScenarioType: (val: ScenarioType) => void;
  seed: number;
  setSeed: (val: number) => void;
  durationSeconds: number;
  setDurationSeconds: (val: number) => void;
  attackPeakPps: number;
  setAttackPeakPps: (val: number) => void;
  speedMultiplier: number;
  setSpeedMultiplier: (val: number) => void;
  bandwidthMbps: number;
  setBandwidthMbps: (val: number) => void;
  cpuCapacityPps: number;
  setCpuCapacityPps: (val: number) => void;
  maxConnections: number;
  setMaxConnections: (val: number) => void;
  maxLatencyMs: number;
  setMaxLatencyMs: (val: number) => void;
  loading: boolean;
  onCreateRun: () => void;
}

export function SimulatorConfigForm({
  scenarioType,
  setScenarioType,
  seed,
  setSeed,
  durationSeconds,
  setDurationSeconds,
  attackPeakPps,
  setAttackPeakPps,
  speedMultiplier,
  setSpeedMultiplier,
  bandwidthMbps,
  setBandwidthMbps,
  cpuCapacityPps,
  setCpuCapacityPps,
  maxConnections,
  setMaxConnections,
  maxLatencyMs,
  setMaxLatencyMs,
  loading,
  onCreateRun,
}: SimulatorConfigFormProps) {
  const selectedScenarioInfo =
    SCENARIO_DESCRIPTIONS[scenarioType] || SCENARIO_DESCRIPTIONS.syn_flood;

  return (
    <div className="bg-[#111827]/70 backdrop-blur-xl border border-gray-700/60 rounded-xl p-5 shadow-xl space-y-4 h-fit">
      <div className="border-b border-gray-800 pb-2">
        <h2 className="text-sm font-bold text-gray-100 flex items-center gap-2 font-mono">
          <Zap className="w-4 h-4 text-[#00FF9D]" />
          Choose Traffic Scenario to Test
        </h2>
        <p className="text-[11px] text-gray-400 mt-0.5 font-sans leading-relaxed">
          Pick an attack to test AI detection, or pick Safe Surge to verify zero false positives on benign users.
        </p>
      </div>

      {/* Scenario Select */}
      <div>
        <label htmlFor="sim-scenario-select" className="block text-xs font-medium text-gray-200 mb-1 font-mono">
          Attack Scenario
        </label>
        <select
          id="sim-scenario-select"
          value={scenarioType}
          onChange={(e) => setScenarioType(e.target.value as ScenarioType)}
          className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-2 text-xs text-gray-200 font-mono focus:outline-none focus:border-[#00FF9D]"
        >
          <option value="syn_flood">SYN Flood (TCP Connection Overload)</option>
          <option value="udp_flood">UDP Amplification (Massive Bandwidth)</option>
          <option value="http_flood">HTTP GET Flood (Web Application)</option>
          <option value="low_and_slow">Low-and-Slow (Slowloris Stealth)</option>
          <option value="mixed">Mixed Multi-Vector (Combined Attack)</option>
          <option value="flash_crowd">Flash Crowd (Safe Spike - No Attack)</option>
        </select>

        {/* Scenario description box */}
        <div className="mt-2 p-3 rounded-lg bg-[#090D16] border border-gray-700/50 text-xs font-mono">
          <div className="text-[#00FF9D] font-bold text-[11px] flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5" />
            {selectedScenarioInfo.subtitle}
          </div>
          <p className="text-[11px] text-gray-400 mt-1 leading-relaxed font-sans">
            {selectedScenarioInfo.desc}
          </p>
        </div>
      </div>

      {/* Duration & Seed */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label htmlFor="sim-duration-input" className="block text-xs font-medium text-gray-200 mb-1 font-mono">
            Duration (Seconds)
          </label>
          <input
            id="sim-duration-input"
            type="number"
            min={10}
            max={300}
            value={durationSeconds}
            onChange={(e) => setDurationSeconds(Number(e.target.value))}
            className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
          />
          <span className="text-[10px] text-gray-400 font-mono">Ticks (10s - 300s)</span>
        </div>
        <div>
          <label htmlFor="sim-seed-input" className="block text-xs font-medium text-gray-200 mb-1 font-mono">
            Random Seed
          </label>
          <input
            id="sim-seed-input"
            type="number"
            value={seed}
            onChange={(e) => setSeed(Number(e.target.value))}
            className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
          />
          <span className="text-[10px] text-gray-400 font-mono">Deterministic replay</span>
        </div>
      </div>

      {/* Attack Peak PPS & Playback Speed */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label htmlFor="sim-pps-input" className="block text-xs font-medium text-gray-200 mb-1 font-mono">
            Attack Ingress (PPS)
          </label>
          <input
            id="sim-pps-input"
            type="number"
            step={500}
            min={1000}
            max={50000}
            value={attackPeakPps}
            onChange={(e) => setAttackPeakPps(Number(e.target.value))}
            className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
          />
          <span className="text-[10px] text-gray-400 font-mono">Peak attack PPS</span>
        </div>
        <div>
          <label htmlFor="sim-speed-select" className="block text-xs font-medium text-gray-200 mb-1 font-mono">
            Playback Speed
          </label>
          <select
            id="sim-speed-select"
            value={speedMultiplier}
            onChange={(e) => setSpeedMultiplier(Number(e.target.value))}
            className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
          >
            <option value={1.0}>1x (Realtime - 1s/tick)</option>
            <option value={10.0}>10x (Fast - 0.2s/tick)</option>
            <option value={100.0}>100x (Instant Replay)</option>
          </select>
          <span className="text-[10px] text-gray-400 font-mono">Clock multiplier</span>
        </div>
      </div>

      {/* Target Victim Capacity */}
      <div className="border-t border-gray-800 pt-3 space-y-3">
        <span className="block text-xs font-bold text-[#00FF9D] font-mono">
          Target Hardware Capacity Limits
        </span>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label htmlFor="sim-bandwidth-input" className="block text-[11px] text-gray-300 font-mono font-medium mb-0.5">
              Bandwidth (Mbps)
            </label>
            <input
              id="sim-bandwidth-input"
              type="number"
              min={1}
              max={10000}
              value={bandwidthMbps}
              onChange={(e) => setBandwidthMbps(Number(e.target.value))}
              className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
            />
            <span className="text-[9px] text-gray-400 font-sans block mt-0.5">
              Max pipe throughput (100 Mbps default)
            </span>
          </div>

          <div>
            <label htmlFor="sim-cpu-input" className="block text-[11px] text-gray-300 font-mono font-medium mb-0.5">
              CPU Capacity (PPS)
            </label>
            <input
              id="sim-cpu-input"
              type="number"
              step={500}
              min={100}
              max={1000000}
              value={cpuCapacityPps}
              onChange={(e) => setCpuCapacityPps(Number(e.target.value))}
              className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
            />
            <span className="text-[9px] text-gray-400 font-sans block mt-0.5">
              Max packets server CPU can process
            </span>
          </div>

          <div>
            <label htmlFor="sim-conn-input" className="block text-[11px] text-gray-300 font-mono font-medium mb-0.5">
              Max Connections
            </label>
            <input
              id="sim-conn-input"
              type="number"
              step={1000}
              min={100}
              max={1000000}
              value={maxConnections}
              onChange={(e) => setMaxConnections(Number(e.target.value))}
              className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
            />
            <span className="text-[9px] text-gray-400 font-sans block mt-0.5">
              SYN connection slots (10k default)
            </span>
          </div>

          <div>
            <label htmlFor="sim-latency-input" className="block text-[11px] text-gray-300 font-mono font-medium mb-0.5">
              Max Latency Cap (ms)
            </label>
            <input
              id="sim-latency-input"
              type="number"
              step={500}
              min={500}
              max={30000}
              value={maxLatencyMs}
              onChange={(e) => setMaxLatencyMs(Number(e.target.value))}
              className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
            />
            <span className="text-[9px] text-gray-400 font-sans block mt-0.5">
              Timeout ceiling under congestion
            </span>
          </div>
        </div>

        {/* Quick Reference Guide Table */}
        <div className="mt-3 p-3 rounded-lg bg-[#090D16] border border-gray-700/50 space-y-2">
          <span className="text-[10px] font-mono text-[#00FF9D] font-bold uppercase tracking-wider block">
            Hardware Limits & Crash Thresholds:
          </span>
          <div className="space-y-1.5 text-[10px] font-mono text-gray-400">
            <div className="flex items-start justify-between gap-2 border-b border-gray-800 pb-1">
              <span className="text-gray-300 font-medium">Bandwidth (100M - 10G):</span>
              <span className="text-right text-gray-400">Pipe saturation causes packet loss.</span>
            </div>
            <div className="flex items-start justify-between gap-2 border-b border-gray-800 pb-1">
              <span className="text-gray-300 font-medium">CPU (5k - 1M PPS):</span>
              <span className="text-right text-gray-400">Overload drops availability to 0%.</span>
            </div>
            <div className="flex items-start justify-between gap-2 border-b border-gray-800 pb-1">
              <span className="text-gray-300 font-medium">Max Connections (10k):</span>
              <span className="text-right text-gray-400">SYN table exhaustion locks out users.</span>
            </div>
            <div className="flex items-start justify-between gap-2">
              <span className="text-gray-300 font-medium">Max Latency Cap:</span>
              <span className="text-right text-gray-400">Triggers request timeout ceiling.</span>
            </div>
          </div>
        </div>
      </div>

      {/* Create Button */}
      <Button
        variant="primary"
        onClick={onCreateRun}
        disabled={loading}
        className="w-full py-2.5 text-xs font-bold uppercase tracking-wider"
      >
        <Zap className="w-4 h-4" />
        {loading ? "Initializing Virtual Session..." : "Initialize Simulation Run"}
      </Button>
    </div>
  );
}

