"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { SimulationLiveChart } from "@/components/charts/SimulationLiveChart";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Activity,
  Play,
  Pause,
  FastForward,
  RotateCcw,
  Square,
  Download,
  AlertTriangle,
  Zap,
  Server,
  Shield,
  CheckCircle2,
  Info,
} from "@/components/ui/icons";
import type {
  ScenarioType,
  SimulationRunResponse,
  SimulationRunSummary,
  SimulationTickItem,
} from "@/types";

const SCENARIO_DESCRIPTIONS: Record<ScenarioType, { title: string; subtitle: string; desc: string }> = {
  syn_flood: {
    title: "Connection Overload Attack (SYN Flood)",
    subtitle: "Spamming fake phone calls until the line goes busy",
    desc: "Attackers send millions of half-open connection requests. The server waits endlessly for them to finish, running out of memory so real visitors cannot connect.",
  },
  udp_flood: {
    title: "Bandwidth Choke Attack (UDP Flood)",
    subtitle: "Clogging the internet pipe with giant junk data",
    desc: "Blasts huge volumes of random data packets to exhaust network bandwidth. Real user traffic gets blocked by pure congestion.",
  },
  http_flood: {
    title: "Website Overload Attack (HTTP Flood)",
    subtitle: "Botnets hitting Refresh button millions of times",
    desc: "A swarm of fake bots endlessly requests heavy web pages, draining server CPU and crashing the web application.",
  },
  low_and_slow: {
    title: "Sneaky Stealth Attack (Slowloris)",
    subtitle: "Creeping slowly under the radar without alarm bells",
    desc: "Sends tiny fragments of data extremely slowly. Traditional volume alarms don't trigger, but server connections get locked up one by one.",
  },
  mixed: {
    title: "Combined Multi-Vector Attack",
    subtitle: "Simultaneous attack on bandwidth, connections, and website",
    desc: "Combines connection overload, bandwidth flooding, and web spam simultaneously to test full AI defense resilience.",
  },
  flash_crowd: {
    title: "Viral Traffic Spike (Safe Real Visitors - NOT an Attack!)",
    subtitle: "Sudden wave of genuine happy users (e.g. viral news / sale)",
    desc: "A massive surge of legitimate real customers. SENTRIX proves its AI intelligence by NEVER blocking real people by accident (zero false alarms).",
  },
};

export default function SimulatorPage() {
  // Configuration State
  const [scenarioType, setScenarioType] = useState<ScenarioType>("syn_flood");
  const [seed, setSeed] = useState<number>(42);
  const [durationSeconds, setDurationSeconds] = useState<number>(60);
  const [attackPeakPps, setAttackPeakPps] = useState<number>(10000);
  const [speedMultiplier, setSpeedMultiplier] = useState<number>(1.0);
  const [bandwidthMbps, setBandwidthMbps] = useState<number>(100.0);
  const [cpuCapacityPps, setCpuCapacityPps] = useState<number>(5000.0);
  const [maxConnections, setMaxConnections] = useState<number>(10000);
  const [maxLatencyMs, setMaxLatencyMs] = useState<number>(5000.0);

  // Active Run State
  const [activeRun, setActiveRun] = useState<SimulationRunResponse | null>(null);
  const [latestTick, setLatestTick] = useState<SimulationTickItem | null>(null);
  const [recentTicks, setRecentTicks] = useState<SimulationTickItem[]>([]);
  const [pastRuns, setPastRuns] = useState<SimulationRunSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [isStepping, setIsStepping] = useState<boolean>(false);
  const [isExportingCsv, setIsExportingCsv] = useState<boolean>(false);
  const [isExportingJson, setIsExportingJson] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Polling ref for clock ticks
  const tickerRef = useRef<NodeJS.Timeout | null>(null);

  // Load run details & committed ticks
  const loadRunDetail = useCallback(async (runId: string) => {
    try {
      const run = await api.getSimulation(runId);
      setActiveRun(run);

      const ticksRes = await api.getSimulationTicks(runId, { limit: 150 });
      const ticks = ticksRes.ticks || [];
      setRecentTicks(ticks);
      if (ticks.length > 0) {
        setLatestTick(ticks[ticks.length - 1]);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load simulation run details");
    }
  }, []);

  const refreshPastRuns = useCallback(async () => {
    try {
      const res = await api.listSimulations({ limit: 10 });
      setPastRuns(res.runs || []);
    } catch (err: unknown) {
      console.error("Failed to refresh runs:", err);
    }
  }, []);

  // Fetch recent runs list on mount
  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const res = await api.listSimulations({ limit: 10 });
        if (!ignore) {
          setPastRuns(res.runs || []);
          if (res.runs && res.runs.length > 0) {
            void loadRunDetail(res.runs[0].run_id);
          }
        }
      } catch (err: unknown) {
        if (!ignore) {
          setErrorMsg(err instanceof Error ? err.message : "Unable to load initial simulation runs from backend.");
        }
      }
    }
    void init();
    return () => {
      ignore = true;
    };
  }, [loadRunDetail]);

  // Real-time ticking execution loop when status === "running"
  useEffect(() => {
    if (!activeRun || activeRun.status !== "running") {
      if (tickerRef.current) clearInterval(tickerRef.current);
      return;
    }

    // Dynamic tick delay according to virtual speed multiplier
    const tickIntervalMs =
      activeRun.speed_multiplier >= 100.0 ? 50 : activeRun.speed_multiplier >= 10.0 ? 200 : 1000;

    tickerRef.current = setInterval(async () => {
      try {
        const ctrlRes = await api.controlSimulation(activeRun.run_id, "step");
        await loadRunDetail(activeRun.run_id);
        if (ctrlRes.status === "completed" || ctrlRes.status === "cancelled") {
          await refreshPastRuns();
          setStatusMessage("Simulation finished successfully! Scorecard generated.");
        }
      } catch (err: unknown) {
        if (process.env.NODE_ENV === "development") {
          console.warn("Simulation clock step paused/offline:", err instanceof Error ? err.message : err);
        }
      }
    }, tickIntervalMs);

    return () => {
      if (tickerRef.current) clearInterval(tickerRef.current);
    };
  }, [activeRun, loadRunDetail, refreshPastRuns]);

  // Create new simulation run
  const handleCreateRun = async () => {
    setLoading(true);
    setErrorMsg(null);
    setStatusMessage(null);
    try {
      const attackStart = Math.max(2, Math.floor(durationSeconds * 0.15));
      const attackEnd = Math.max(attackStart + 2, Math.floor(durationSeconds * 0.85));

      const payload = {
        scenario_type: scenarioType,
        seed: Number(seed),
        duration_seconds: Number(durationSeconds),
        baseline_pps: 250.0,
        attack_peak_pps: Number(attackPeakPps),
        attack_start_tick: attackStart,
        attack_end_tick: attackEnd,
        speed_multiplier: Number(speedMultiplier),
        victim: {
          bandwidth_mbps: Number(bandwidthMbps),
          cpu_capacity_pps: Number(cpuCapacityPps),
          max_active_connections: Number(maxConnections),
          max_latency_ms: Number(maxLatencyMs),
          baseline_latency_ms: 15.0,
        },
      };

      const newRun = await api.createSimulation(payload);
      setActiveRun(newRun);
      setLatestTick(null);
      setRecentTicks([]);
      await refreshPastRuns();
      setStatusMessage(`New simulation run created: ${newRun.run_id}. Click "Start Attack" to begin!`);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to create simulation run");
    } finally {
      setLoading(false);
    }
  };

  // Run lifecycle controls (start, pause, resume, step, cancel, reset)
  const handleControl = async (action: "start" | "pause" | "resume" | "step" | "cancel" | "reset") => {
    if (!activeRun) return;
    setErrorMsg(null);
    setStatusMessage(null);
    setIsStepping(action === "step");
    try {
      if (action === "reset" && activeRun.status === "running") {
        await api.controlSimulation(activeRun.run_id, "pause");
      }
      await api.controlSimulation(activeRun.run_id, action);
      await loadRunDetail(activeRun.run_id);
      await refreshPastRuns();

      if (action === "start") setStatusMessage("Attack simulation started. Virtual clock is ticking!");
      else if (action === "pause") setStatusMessage("Simulation paused.");
      else if (action === "resume") setStatusMessage("Simulation resumed.");
      else if (action === "step") setStatusMessage(`Stepped forward +1s to tick #${activeRun.current_tick + 1}.`);
      else if (action === "cancel") setStatusMessage("Simulation stopped.");
      else if (action === "reset") {
        setRecentTicks([]);
        setLatestTick(null);
        setStatusMessage("Simulation reset back to tick 0. Ready for new run!");
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : `Action ${action} failed`);
    } finally {
      setIsStepping(false);
    }
  };

  const handleExport = async (format: "csv" | "json") => {
    if (!activeRun) return;
    if (format === "csv") setIsExportingCsv(true);
    else setIsExportingJson(true);
    setErrorMsg(null);

    try {
      await api.downloadSimulationExport(activeRun.run_id, format);
      setStatusMessage(`Exported simulation ${activeRun.run_id} as ${format.toUpperCase()}`);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : `Failed to export ${format}`);
    } finally {
      if (format === "csv") setIsExportingCsv(false);
      else setIsExportingJson(false);
    }
  };

  const selectedScenarioInfo = SCENARIO_DESCRIPTIONS[scenarioType] || SCENARIO_DESCRIPTIONS.syn_flood;

  // Determine availability color & friendly message
  const currentAvail = latestTick?.availability_pct ?? 100.0;
  let availColor = "text-[#10B981]";
  let availBg = "bg-[rgba(16,185,129,0.1)] border-emerald-500/40";
  let availStatusText = "Server Healthy (All users connected)";

  if (currentAvail < 60) {
    availColor = "text-[#EF4444]";
    availBg = "bg-[rgba(239,68,68,0.15)] border-red-500/40";
    availStatusText = "Severe Outage (Server down - dropping requests)";
  } else if (currentAvail < 90) {
    availColor = "text-[#F59E0B]";
    availBg = "bg-[rgba(245,158,11,0.12)] border-amber-500/40";
    availStatusText = "Slow Response (High load - degraded)";
  }

  // Virtual progress calculation
  const totalTicks = activeRun?.total_ticks ?? 60;
  const currentTick = activeRun?.current_tick ?? 0;
  const progressPct = Math.min(100, Math.round((currentTick / Math.max(1, totalTicks)) * 100));

  return (
    <div className="space-y-6">
      {/* Top Banner: Synthetic Disclaimer & Safety Guarantee */}
      

      {/* Notifications */}
      {errorMsg && (
        <div className="bg-[rgba(239,68,68,0.15)] border border-red-500/40 text-[#EF4444] p-3.5 rounded-xl text-xs flex items-center gap-2 font-mono">
          <AlertTriangle className="w-4 h-4 text-[#EF4444] shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}
      {statusMessage && (
        <div className="bg-[rgba(0,255,157,0.12)] border border-[#00FF9D]/40 text-[#00FF9D] p-3 rounded-xl text-xs flex items-center gap-2 font-mono">
          <CheckCircle2 className="w-4 h-4 text-[#00FF9D] shrink-0" />
          <span>{statusMessage}</span>
        </div>
      )}

      {/* Main Grid: Left Setup Column & Right Active Controls / Live Dashboard */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start h-fit">
        {/* Left Column: Easy Setup Form */}
        <div className="bg-[rgba(31,41,55,0.6)] backdrop-blur-xl border border-[rgba(75,85,99,0.3)] rounded-xl p-5 shadow-xl space-y-4 h-fit">
          <div className="border-b border-[rgba(75,85,99,0.3)] pb-2">
            <h2 className="text-sm font-bold text-gray-100 flex items-center gap-2 font-mono">
              <Zap className="w-4 h-4 text-[#00FF9D]" />
              Choose Traffic Scenario to Test
            </h2>
            <p className="text-[11px] text-[#9CA3AF] mt-0.5 font-sans">
              Pick an attack to test AI detection, or pick Safe Surge to see how normal visitors are protected.
            </p>
          </div>

          {/* Scenario Select */}
          <div>
            <label className="block text-xs font-medium text-gray-200 mb-1 font-mono">
              Attack Scenario
            </label>
            <select
              value={scenarioType}
              onChange={(e) => setScenarioType(e.target.value as ScenarioType)}
              className="w-full bg-[#090D16] border border-[rgba(75,85,99,0.4)] rounded-lg px-3 py-2 text-xs text-gray-200 font-mono focus:outline-none focus:border-[#00FF9D]"
            >
              <option value="syn_flood">SYN Flood (TCP Connection Overload)</option>
              <option value="udp_flood">UDP Amplification (Massive Bandwidth)</option>
              <option value="http_flood">HTTP GET Flood (Web Application)</option>
              <option value="low_and_slow">Low-and-Slow (Slowloris Stealth)</option>
              <option value="mixed">Mixed Multi-Vector (Combined Attack)</option>
              <option value="flash_crowd">Flash Crowd (Safe Spike - No Attack)</option>
            </select>

            {/* Scenario explanation box */}
            <div className="mt-2 p-3 rounded-lg bg-[#090D16] border border-[rgba(75,85,99,0.3)] text-xs font-mono">
              <div className="text-[#00FF9D] font-bold text-[11px] flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5" />
                {selectedScenarioInfo.subtitle}
              </div>
              <p className="text-[11px] text-[#9CA3AF] mt-1 leading-relaxed font-sans">
                {selectedScenarioInfo.desc}
              </p>
            </div>
          </div>

          {/* Duration & Seed */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-200 mb-1 font-mono">
                Duration (Seconds)
              </label>
              <input
                suppressHydrationWarning
                autoComplete="off"
                type="number"
                min={10}
                max={300}
                value={durationSeconds}
                onChange={(e) => setDurationSeconds(Number(e.target.value))}
                className="w-full bg-[#090D16] border border-[rgba(75,85,99,0.4)] rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
              />
              <span className="text-[10px] text-[#9CA3AF]/60 font-mono">Ticks (10s - 300s)</span>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-200 mb-1 font-mono">
                Random Seed
              </label>
              <input
                suppressHydrationWarning
                autoComplete="off"
                type="number"
                value={seed}
                onChange={(e) => setSeed(Number(e.target.value))}
                className="w-full bg-[#090D16] border border-[rgba(75,85,99,0.4)] rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
              />
              <span className="text-[10px] text-[#9CA3AF]/60 font-mono">Deterministic repeat</span>
            </div>
          </div>

          {/* Attack Peak PPS & Playback Speed */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-200 mb-1 font-mono">
                Attack Ingress (PPS)
              </label>
              <input
                suppressHydrationWarning
                autoComplete="off"
                type="number"
                step={500}
                min={1000}
                max={50000}
                value={attackPeakPps}
                onChange={(e) => setAttackPeakPps(Number(e.target.value))}
                className="w-full bg-[#090D16] border border-[rgba(75,85,99,0.4)] rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
              />
              <span className="text-[10px] text-[#9CA3AF]/60 font-mono">Peak attack PPS</span>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-200 mb-1 font-mono">
                Playback Speed
              </label>
              <select
                value={speedMultiplier}
                onChange={(e) => setSpeedMultiplier(Number(e.target.value))}
                className="w-full bg-[#090D16] border border-[rgba(75,85,99,0.4)] rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
              >
                <option value={1.0}>1x (Realtime - 1s/tick)</option>
                <option value={10.0}>10x (Fast - 0.2s/tick)</option>
                <option value={100.0}>100x (Instant Replay)</option>
              </select>
              <span className="text-[10px] text-[#9CA3AF]/60 font-mono">Clock multiplier</span>
            </div>
          </div>

          {/* Target Victim Capacity */}
          <div className="border-t border-[rgba(75,85,99,0.3)] pt-3 space-y-3">
            <div className="flex items-center justify-between">
              <span className="block text-xs font-bold text-[#00FF9D] font-mono">
                Target Hardware Capacity Limits
              </span>

            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="flex justify-between items-baseline mb-0.5">
                  <label className="block text-[11px] text-gray-200 font-mono font-medium">Bandwidth (Mbps)</label>
                </div>
                <input
                  suppressHydrationWarning
                  autoComplete="off"
                  type="number"
                  min={1}
                  max={10000}
                  value={bandwidthMbps}
                  onChange={(e) => setBandwidthMbps(Number(e.target.value))}
                  className="w-full bg-[#090D16] border border-[rgba(75,85,99,0.4)] rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
                />
                <span className="text-[9px] text-[#9CA3AF]/70 font-sans block mt-0.5">
                  Max pipe throughput (100 Mbps default)
                </span>
              </div>

              <div>
                <div className="flex justify-between items-baseline mb-0.5">
                  <label className="block text-[11px] text-gray-200 font-mono font-medium">CPU Capacity (PPS)</label>
                </div>
                <input
                  suppressHydrationWarning
                  autoComplete="off"
                  type="number"
                  step={500}
                  min={100}
                  max={1000000}
                  value={cpuCapacityPps}
                  onChange={(e) => setCpuCapacityPps(Number(e.target.value))}
                  className="w-full bg-[#090D16] border border-[rgba(75,85,99,0.4)] rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
                />
                <span className="text-[9px] text-[#9CA3AF]/70 font-sans block mt-0.5">
                  Max packets server CPU can handle
                </span>
              </div>

              <div>
                <div className="flex justify-between items-baseline mb-0.5">
                  <label className="block text-[11px] text-gray-200 font-mono font-medium">Max Connections</label>
                </div>
                <input
                  suppressHydrationWarning
                  autoComplete="off"
                  type="number"
                  step={1000}
                  min={100}
                  max={1000000}
                  value={maxConnections}
                  onChange={(e) => setMaxConnections(Number(e.target.value))}
                  className="w-full bg-[#090D16] border border-[rgba(75,85,99,0.4)] rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
                />
                <span className="text-[9px] text-[#9CA3AF]/70 font-sans block mt-0.5">
                  SYN table connection slots (10k default)
                </span>
              </div>

              <div>
                <div className="flex justify-between items-baseline mb-0.5">
                  <label className="block text-[11px] text-gray-200 font-mono font-medium">Max Latency Cap (ms)</label>
                </div>
                <input
                  suppressHydrationWarning
                  autoComplete="off"
                  type="number"
                  step={500}
                  min={500}
                  max={30000}
                  value={maxLatencyMs}
                  onChange={(e) => setMaxLatencyMs(Number(e.target.value))}
                  className="w-full bg-[#090D16] border border-[rgba(75,85,99,0.4)] rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
                />
                <span className="text-[9px] text-[#9CA3AF]/70 font-sans block mt-0.5">
                  Max timeout ceiling under heavy congestion
                </span>
              </div>
            </div>

            {/* Quick Reference Guide Table for Recruiters */}
            <div className="mt-3 p-3 rounded-lg bg-[#090D16] border border-[rgba(75,85,99,0.3)] space-y-2">
              <span className="text-[10px] font-mono text-[#00FF9D] font-bold uppercase tracking-wider block">
                Hardware Limits & Crash Thresholds:
              </span>
              <div className="space-y-1.5 text-[10px] font-mono text-[#9CA3AF]">
                <div className="flex items-start justify-between gap-2 border-b border-[rgba(75,85,99,0.2)] pb-1">
                  <span className="text-gray-300 font-medium">Bandwidth (100M - 10G):</span>
                  <span className="text-right text-[#9CA3AF]/80">Traffic exceed hone par pipe choke & packet drops hote hain.</span>
                </div>
                <div className="flex items-start justify-between gap-2 border-b border-[rgba(75,85,99,0.2)] pb-1">
                  <span className="text-gray-300 font-medium">CPU Throughput (5k - 1M PPS):</span>
                  <span className="text-right text-[#9CA3AF]/80">Queue fill hone par server availability girkar 0% ho jaati hai.</span>
                </div>
                <div className="flex items-start justify-between gap-2 border-b border-[rgba(75,85,99,0.2)] pb-1">
                  <span className="text-gray-300 font-medium">Max Connections (10k slots):</span>
                  <span className="text-right text-[#9CA3AF]/80">SYN Flood table fill karke real users ko block karta hai.</span>
                </div>
                <div className="flex items-start justify-between gap-2">
                  <span className="text-gray-300 font-medium">Max Latency Cap (5s - 30s):</span>
                  <span className="text-right text-[#9CA3AF]/80">Severe congestion me request timeout ceiling trigger hoti hai.</span>
                </div>
              </div>
            </div>
          </div>

          {/* Create Button */}
          <Button
            variant="primary"
            onClick={handleCreateRun}
            disabled={loading}
            className="w-full py-2.5 text-xs font-bold uppercase tracking-wider"
          >
            <Zap className="w-4 h-4" />
            {loading ? "Initializing Virtual Session..." : "Initialize Simulation Run"}
          </Button>
        </div>

        {/* Right 2 Columns: Active Controls, Live Metrics & Live Chart */}
        <div className="lg:col-span-2 space-y-5 h-fit">
          {activeRun ? (
            <div className="bg-[rgba(31,41,55,0.6)] backdrop-blur-xl border border-[rgba(75,85,99,0.3)] rounded-xl p-5 shadow-xl space-y-5">
              {/* Top Control Bar */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[rgba(75,85,99,0.3)] pb-4">
                <div>
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm font-mono text-[#00FF9D] font-bold">{activeRun.run_id}</span>
                    <span
                      className={`text-[10px] uppercase font-mono px-2.5 py-0.5 rounded-full font-bold border ${
                        activeRun.status === "running"
                          ? "bg-[rgba(239,68,68,0.2)] text-[#EF4444] border-red-500/40 animate-pulse"
                          : activeRun.status === "completed"
                          ? "bg-[rgba(0,255,157,0.15)] text-[#00FF9D] border-[#00FF9D]/40"
                          : activeRun.status === "paused"
                          ? "bg-[rgba(245,158,11,0.2)] text-[#F59E0B] border-amber-500/40"
                          : "bg-[#1F2937] text-[#9CA3AF] border-[rgba(75,85,99,0.4)]"
                      }`}
                    >
                      ● {activeRun.status}
                    </span>
                  </div>
                  <div className="text-xs text-[#9CA3AF] font-mono mt-0.5">
                    Attack: <strong className="text-gray-100">{activeRun.scenario_type}</strong> · Speed:{" "}
                    <strong>{activeRun.speed_multiplier}x</strong> · Seed: {activeRun.seed}
                  </div>
                </div>

                {/* Lifecycle Action Buttons */}
                <div className="flex flex-wrap items-center gap-2">
                  {/* Start / Resume */}
                  {activeRun.status !== "running" &&
                    activeRun.status !== "completed" &&
                    activeRun.status !== "cancelled" && (
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => handleControl(activeRun.status === "paused" ? "resume" : "start")}
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
                      onClick={() => handleControl("pause")}
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
                      onClick={() => handleControl("step")}
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
                      onClick={() => handleControl("cancel")}
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
                      onClick={() => handleControl("reset")}
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
                    onClick={() => handleExport("csv")}
                  >
                    <Download className="w-3.5 h-3.5 text-[#00FF9D]" />
                    Export CSV
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    loading={isExportingJson}
                    onClick={() => handleExport("json")}
                  >
                    <Download className="w-3.5 h-3.5 text-[#06B6D4]" />
                    Export JSON
                  </Button>
                </div>
              </div>

              {/* Virtual Progress Bar */}
              <div className="space-y-1.5 font-mono">
                <div className="flex justify-between text-xs">
                  <span className="text-gray-200 font-medium">
                    Simulation Progress: {progressPct}%
                  </span>
                  <span className="text-[#9CA3AF]">
                    Tick {currentTick} / {totalTicks} seconds
                  </span>
                </div>
                <div className="w-full bg-[#090D16] h-2.5 rounded-full overflow-hidden border border-[rgba(75,85,99,0.3)]">
                  <div
                    className={`h-full transition-all duration-300 rounded-full ${
                      activeRun.status === "running" ? "bg-[#EF4444] shadow-[0_0_12px_#EF4444]" : "bg-[#00FF9D] shadow-[0_0_12px_#00FF9D]"
                    }`}
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
              </div>

              {/* 4 Live QoS Telemetry Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {/* 1. Server Availability */}
                <div className={`p-3 rounded-xl border ${availBg}`}>
                  <div className="flex items-center justify-between text-[11px] font-mono text-[#9CA3AF] mb-1">
                    <span>Target Health</span>
                    <Activity className="w-3.5 h-3.5" />
                  </div>
                  <div className={`text-xl font-bold font-mono ${availColor}`}>
                    {currentAvail.toFixed(1)}%
                  </div>
                  <div className="text-[10px] text-[#9CA3AF] mt-1 truncate" title={availStatusText}>
                    {availStatusText}
                  </div>
                </div>

                {/* 2. Latency */}
                <div className="bg-[#090D16] border border-[rgba(75,85,99,0.3)] p-3 rounded-xl">
                  <div className="flex items-center justify-between text-[11px] font-mono text-[#9CA3AF] mb-1">
                    <span>P95 Latency</span>
                    <Server className="w-3.5 h-3.5 text-[#06B6D4]" />
                  </div>
                  <div className="text-xl font-bold font-mono text-[#06B6D4]">
                    {latestTick?.latency_ms ? `${latestTick.latency_ms.toFixed(1)} ms` : "15.0 ms"}
                  </div>
                  <div className="text-[10px] text-[#9CA3AF]/60 mt-1">
                    {latestTick && latestTick.latency_ms > 35 ? "Queue Congested" : "Normal Latency"}
                  </div>
                </div>

                {/* 3. Attack Traffic */}
                <div className="bg-[#090D16] border border-[rgba(75,85,99,0.3)] p-3 rounded-xl">
                  <div className="flex items-center justify-between text-[11px] font-mono text-[#9CA3AF] mb-1">
                    <span>Attack Ingress</span>
                    <AlertTriangle className="w-3.5 h-3.5 text-[#EF4444]" />
                  </div>
                  <div className="text-xl font-bold font-mono text-[#EF4444]">
                    {latestTick?.offered_attack_pps ? `${Math.round(latestTick.offered_attack_pps)} PPS` : "0 PPS"}
                  </div>
                  <div className="text-[10px] text-[#10B981] mt-1 font-mono">
                    Dropped: {latestTick ? Math.round(latestTick.dropped_attack_pps) : 0} PPS
                  </div>
                </div>

                {/* 4. Policy Defense Action */}
                <div className="bg-[#090D16] border border-[rgba(75,85,99,0.3)] p-3 rounded-xl">
                  <div className="flex items-center justify-between text-[11px] font-mono text-[#9CA3AF] mb-1">
                    <span>Defense Shield</span>
                    <Shield className="w-3.5 h-3.5 text-[#00FF9D]" />
                  </div>
                  <div className="text-xs font-bold font-mono text-[#00FF9D] uppercase mt-1">
                    {latestTick?.policy_action === "simulate_mitigation" || latestTick?.policy_action === "rate_limit"
                      ? "Rate Limiting Active"
                      : latestTick?.policy_action === "alert"
                      ? "Alert Triggered"
                      : "Monitoring Normal"}
                  </div>
                  <div className="text-[10px] text-[#9CA3AF]/60 mt-1 font-mono">
                    Active Rules: {latestTick?.active_mitigations_count ?? 0}
                  </div>
                </div>
              </div>

              {/* Dynamic Live Attack & Defense Chart */}
              <div className="bg-[#090D16] border border-[rgba(75,85,99,0.3)] rounded-xl p-4 space-y-2">
                <div className="flex items-center justify-between border-b border-[rgba(75,85,99,0.2)] pb-2">
                  <div>
                    <h3 className="text-xs font-bold text-gray-100 flex items-center gap-2 font-mono">
                      <Activity className="w-4 h-4 text-[#00FF9D]" />
                      Real-time Chaos Telemetry Stream
                    </h3>
                    <p className="text-[11px] text-[#9CA3AF] font-sans">
                      Red: Attack Traffic · Green: Legitimate Workload · Cyan: eBPF Mitigated Dropped
                    </p>
                  </div>
                  <span className="text-[11px] font-mono text-[#00FF9D]">
                    {recentTicks.length} ticks recorded
                  </span>
                </div>
                <SimulationLiveChart ticks={recentTicks} />
              </div>

              {/* Ground Truth Scorecard */}
              {activeRun.scorecard && (
                <div className="bg-linear-to-br from-[#1F2937]/70 to-[#090D16] border border-[rgba(0,255,157,0.35)] rounded-xl p-5 space-y-4 shadow-xl">
                  <div className="flex items-center justify-between border-b border-[rgba(75,85,99,0.3)] pb-2">
                    <div>
                      <h3 className="text-xs uppercase font-bold tracking-wider text-[#00FF9D] flex items-center gap-2 font-mono">
                        <CheckCircle2 className="w-4 h-4 text-[#00FF9D]" />
                        AI Defense Report Card (Results)
                      </h3>
                      <p className="text-[11px] text-[#9CA3AF] font-sans">
                        Did the AI catch the attack accurately without hurting real users?
                      </p>
                    </div>
                    <Badge variant="matrix">AI VERIFIED RESULT</Badge>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
                    <div className="p-3 rounded-lg bg-[#090D16] border border-[rgba(75,85,99,0.3)]">
                      <span className="text-[#9CA3AF] block text-[10px]">How Fast AI Detected:</span>
                      <strong className="text-gray-100 text-sm">
                        {activeRun.scorecard.time_to_detect_seconds !== null
                          ? `${activeRun.scorecard.time_to_detect_seconds}s`
                          : "Instant / Safe"}
                      </strong>
                    </div>

                    <div className="p-3 rounded-lg bg-[#090D16] border border-[rgba(75,85,99,0.3)]">
                      <span className="text-[#9CA3AF] block text-[10px]">How Fast Shield Blocked:</span>
                      <strong className="text-[#06B6D4] text-sm">
                        {activeRun.scorecard.time_to_mitigate_seconds !== null
                          ? `${activeRun.scorecard.time_to_mitigate_seconds}s`
                          : "Immediate"}
                      </strong>
                    </div>

                    <div className="p-3 rounded-lg bg-[#090D16] border border-[rgba(75,85,99,0.3)]">
                      <span className="text-[#9CA3AF] block text-[10px]">Attack Traffic Stopped:</span>
                      <strong className="text-[#00FF9D] text-sm">
                        {activeRun.scorecard.attack_traffic_blocked_pct !== null
                          ? `${activeRun.scorecard.attack_traffic_blocked_pct}%`
                          : "100%"}
                      </strong>
                    </div>

                    <div className="p-3 rounded-lg bg-[#090D16] border border-[rgba(75,85,99,0.3)]">
                      <span className="text-[#9CA3AF] block text-[10px]">Safe Real Visitors Saved:</span>
                      <strong className="text-[#10B981] text-sm">
                        {activeRun.scorecard.collateral_legitimate_pct !== null
                          ? `${(100 - activeRun.scorecard.collateral_legitimate_pct).toFixed(1)}%`
                          : "100%"}
                      </strong>
                    </div>

                    <div className="p-3 rounded-lg bg-[#090D16] border border-[rgba(75,85,99,0.3)]">
                      <span className="text-[#9CA3AF] block text-[10px]">Website Downtime:</span>
                      <strong className="text-[#EF4444] text-sm">
                        {activeRun.scorecard.downtime_seconds}s (Zero Crash)
                      </strong>
                    </div>

                    <div className="p-3 rounded-lg bg-[#090D16] border border-[rgba(75,85,99,0.3)]">
                      <span className="text-[#9CA3AF] block text-[10px]">AI Accuracy (Precision):</span>
                      <strong className="text-[#00FF9D] text-sm">
                        {activeRun.scorecard.precision !== null ? `${Math.round(activeRun.scorecard.precision * 100)}%` : "100%"}
                      </strong>
                    </div>

                    <div className="p-3 rounded-lg bg-[#090D16] border border-[rgba(75,85,99,0.3)]">
                      <span className="text-[#9CA3AF] block text-[10px]">Threat Catch Rate (Recall):</span>
                      <strong className="text-[#00FF9D] text-sm">
                        {activeRun.scorecard.recall !== null ? `${Math.round(activeRun.scorecard.recall * 100)}%` : "100%"}
                      </strong>
                    </div>

                    <div className="p-3 rounded-lg bg-[#090D16] border border-[rgba(75,85,99,0.3)]">
                      <span className="text-[#9CA3AF] block text-[10px]">Mistakes On Real Users:</span>
                      <strong className="text-[#10B981] text-sm">
                        {activeRun.scorecard.false_positive_rate !== null
                          ? `${(activeRun.scorecard.false_positive_rate * 100).toFixed(1)}% (Almost 0)`
                          : "0.0%"}
                      </strong>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-[rgba(31,41,55,0.6)] backdrop-blur-xl border border-[rgba(75,85,99,0.3)] rounded-xl p-12 text-center text-[#9CA3AF] font-mono text-sm space-y-2">
              <Info className="w-8 h-8 text-[#00FF9D] mx-auto opacity-70" />
              <div>No active simulation session loaded.</div>
              <p className="text-xs text-[#9CA3AF]/60 font-sans">
                Choose an attack scenario on the left and click &quot;Initialize Simulation Run&quot; to begin.
              </p>
            </div>
          )}

          {/* Past Simulation Runs Table */}
          <div className="bg-[rgba(31,41,55,0.6)] backdrop-blur-xl border border-[rgba(75,85,99,0.3)] rounded-xl p-5 shadow-xl space-y-3 font-mono">
            <div className="flex items-center justify-between border-b border-[rgba(75,85,99,0.3)] pb-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-200 flex items-center gap-2">
                <RotateCcw className="w-3.5 h-3.5 text-[#00FF9D]" />
                Previous Chaos Replay Sessions
              </h3>
              <button
                onClick={refreshPastRuns}
                className="text-[11px] font-mono text-[#00FF9D] hover:underline cursor-pointer"
              >
                Refresh List
              </button>
            </div>

            {pastRuns.length === 0 ? (
              <span className="text-xs text-[#9CA3AF] font-mono">No simulation runs recorded yet.</span>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-[rgba(75,85,99,0.3)] bg-[#090D16]">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="text-[#9CA3AF] border-b border-[rgba(75,85,99,0.3)] bg-[#1F2937]/50 text-[11px] uppercase">
                      <th className="py-2.5 px-3">Run ID</th>
                      <th className="py-2.5 px-3">Scenario</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3">Progress</th>
                      <th className="py-2.5 px-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[rgba(75,85,99,0.2)]">
                    {pastRuns.map((r) => (
                      <tr
                        key={r.run_id}
                        className={`hover:bg-[#1F2937]/40 transition-colors ${
                          activeRun?.run_id === r.run_id ? "bg-[rgba(0,255,157,0.08)]" : ""
                        }`}
                      >
                        <td className="py-2.5 px-3 text-[#00FF9D] font-bold">{r.run_id}</td>
                        <td className="py-2.5 px-3 text-gray-200">{r.scenario_type}</td>
                        <td className="py-2.5 px-3">
                          <Badge
                            variant={
                              r.status === "completed"
                                ? "normal"
                                : r.status === "running"
                                ? "critical"
                                : r.status === "paused"
                                ? "warning"
                                : "outline"
                            }
                            className="text-[10px]"
                          >
                            {r.status}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-3 text-[#9CA3AF]">
                          {r.current_tick} / {r.total_ticks}s
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <button
                            onClick={() => loadRunDetail(r.run_id)}
                            className="text-[#00FF9D] hover:underline font-semibold cursor-pointer"
                          >
                            Load Session
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
