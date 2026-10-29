"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SimulationLiveChart } from "@/components/charts/SimulationLiveChart";
import { ExplainCard } from "@/components/common/ExplainCard";
import { SimulatorConfigForm } from "@/components/simulator/SimulatorConfigForm";
import { SimulatorControls } from "@/components/simulator/SimulatorControls";
import { SimulatorHistoryTable } from "@/components/simulator/SimulatorHistoryTable";
import { SimulatorScorecard } from "@/components/simulator/SimulatorScorecard";
import { SimulatorTelemetryGrid } from "@/components/simulator/SimulatorTelemetryGrid";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Info,
  Zap,
} from "@/components/ui/icons";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import type {
  ScenarioType,
  SimulationRunResponse,
  SimulationRunSummary,
  SimulationTickItem,
} from "@/types";

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
  const isSteppingTickerRef = useRef<boolean>(false);

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
      setErrorMsg(getErrorMessage(err, "Failed to load test run details"));
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
          setErrorMsg(getErrorMessage(err, "Unable to load initial test runs from backend."));
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
    const isRunning = activeRun?.status === "running";
    const runId = activeRun?.run_id;
    const speed = activeRun?.speed_multiplier ?? 1.0;

    if (!isRunning || !runId) {
      if (tickerRef.current) clearInterval(tickerRef.current);
      return;
    }

    const tickIntervalMs =
      speed >= 100.0 ? 50 : speed >= 10.0 ? 200 : 1000;

    tickerRef.current = setInterval(async () => {
      if (isSteppingTickerRef.current) return;
      isSteppingTickerRef.current = true;
      try {
        // Backend persistent worker continuously advances running simulations.
        // Frontend subscribes to latest authoritative tick updates without owning clock.
        await loadRunDetail(runId);
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("sentrix:shield_update"));
        }
        if (activeRun?.status === "completed" || activeRun?.status === "cancelled") {
          await refreshPastRuns();
          setStatusMessage("Test run completed successfully! Performance scorecard ready.");
        }
      } catch (err: unknown) {
        if (process.env.NODE_ENV === "development") {
          console.warn("Simulation clock poll notice:", err instanceof Error ? err.message : err);
        }
      } finally {
        isSteppingTickerRef.current = false;
      }
    }, tickIntervalMs);

    return () => {
      if (tickerRef.current) clearInterval(tickerRef.current);
    };
  }, [activeRun?.status, activeRun?.run_id, activeRun?.speed_multiplier, loadRunDetail, refreshPastRuns]);

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
      setStatusMessage(`New test run initialized: ${newRun.run_id}. Click "Start Attack" to begin testing!`);
    } catch (err: unknown) {
      setErrorMsg(getErrorMessage(err, "Failed to create test run"));
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
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("sentrix:shield_update"));
      }

      if (action === "start") setStatusMessage("Traffic test started. Observing defense engine reaction...");
      else if (action === "pause") setStatusMessage("Traffic test paused.");
      else if (action === "resume") setStatusMessage("Traffic test resumed.");
      else if (action === "step") setStatusMessage(`Advanced test clock by +1 second.`);
      else if (action === "cancel") setStatusMessage("Traffic test stopped.");
      else if (action === "reset") {
        setRecentTicks([]);
        setLatestTick(null);
        setStatusMessage("Traffic test reset to beginning. Ready to run again!");
      }
    } catch (err: unknown) {
      setErrorMsg(getErrorMessage(err, `Action ${action} failed`));
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
      setStatusMessage(`Exported test data as ${format.toUpperCase()}`);
    } catch (err: unknown) {
      setErrorMsg(getErrorMessage(err, `Failed to export ${format}`));
    } finally {
      if (format === "csv") setIsExportingCsv(false);
      else setIsExportingJson(false);
    }
  };

  // Derived metrics
  const attackStartTick = recentTicks.find((t) => (t.offered_attack_pps || 0) > 0)?.tick;
  const firstDetectedTick = recentTicks.find(
    (t) =>
      (t.offered_attack_pps || 0) > 0 &&
      (t.prediction === "suspicious" ||
        t.policy_action === "alert" ||
        t.policy_action === "request_mitigation")
  )?.tick;
  const firstMitigatedTick = recentTicks.find(
    (t) =>
      (t.offered_attack_pps || 0) > 0 &&
      ((t.dropped_attack_pps || 0) > 0 || (t.active_mitigations_count || 0) > 0)
  )?.tick;

  const totalOfferedAttack = recentTicks.reduce((acc, t) => acc + (t.offered_attack_pps || 0), 0);
  const totalDroppedAttack = recentTicks.reduce((acc, t) => acc + (t.dropped_attack_pps || 0), 0);
  const totalOfferedLegit = recentTicks.reduce((acc, t) => acc + (t.offered_legit_pps || 0), 0);
  const totalDroppedLegit = recentTicks.reduce((acc, t) => acc + (t.dropped_legit_pps || 0), 0);

  const liveBlockedPct =
    totalOfferedAttack > 0
      ? Math.min(100, Math.round((totalDroppedAttack / totalOfferedAttack) * 100))
      : latestTick && (latestTick.offered_attack_pps || 0) > 0
      ? Math.min(
          100,
          Math.round(((latestTick.dropped_attack_pps || 0) / latestTick.offered_attack_pps) * 100)
        )
      : 0;

  const aiTimeToDetectSeconds =
    activeRun?.scorecard?.time_to_detect_seconds !== null &&
    activeRun?.scorecard?.time_to_detect_seconds !== undefined
      ? activeRun.scorecard.time_to_detect_seconds
      : attackStartTick !== undefined && firstDetectedTick !== undefined
      ? Math.max(0, firstDetectedTick - attackStartTick)
      : null;

  const aiTimeToMitigateSeconds =
    activeRun?.scorecard?.time_to_mitigate_seconds !== null &&
    activeRun?.scorecard?.time_to_mitigate_seconds !== undefined
      ? activeRun.scorecard.time_to_mitigate_seconds
      : attackStartTick !== undefined && firstMitigatedTick !== undefined
      ? Math.max(0, firstMitigatedTick - attackStartTick)
      : null;

  const isShieldActive =
    latestTick?.policy_action === "request_mitigation" ||
    latestTick?.policy_action === "simulate_mitigation" ||
    latestTick?.policy_action === "rate_limit" ||
    (latestTick?.active_mitigations_count ?? 0) > 0;

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-gray-800">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
              <Zap className="w-6 h-6 text-[#00FF9D]" />
              Traffic Simulator
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-sans font-bold bg-[#00FF9D]/15 text-[#00FF9D] border border-[#00FF9D]/40">
              Test Mode Only — 100% Safe Sandbox
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Generate test traffic to see how SENTRIX processes it. Use test mode to explore how detection works without affecting a real service.
          </p>
        </div>
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="bg-red-500/15 border border-red-500/40 text-[#EF4444] p-3.5 rounded-xl text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-[#EF4444] shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}
      {statusMessage && (
        <div className="bg-[rgba(0,255,157,0.12)] border border-[#00FF9D]/40 text-[#00FF9D] p-3 rounded-xl text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-[#00FF9D] shrink-0" />
          <span>{statusMessage}</span>
        </div>
      )}

      {/* Plain English Explanation Card */}
      <ExplainCard
        title="What is the Traffic Simulator?"
        summary="The Traffic Simulator lets you see how your defense system reacts to different types of traffic before an actual attack occurs. No real servers, real networks, or real customers are touched."
        tips={[
          "Choose a scenario: e.g. SYN Flood (rapid connection attempts) or Flash Crowd (sudden rush of real visitors).",
          "Click 'Start Attack' to watch the virtual clock tick second-by-second.",
          "Check the Scorecard to see how fast SENTRIX detected the attack and whether legitimate traffic was protected.",
        ]}
        technicalDetails={
          <div className="space-y-1 text-[11px]">
            <p><strong className="text-gray-200">Simulation Engine:</strong> Discrete-event queuing model with finite server capacity, token bucket mitigation, and EWMA latency modeling.</p>
            <p><strong className="text-gray-200">Reproducibility:</strong> Runs are seed-deterministic (same seed produces identical tick-by-tick results).</p>
            <p><strong className="text-gray-200">Export:</strong> Per-tick metrics exportable to standard CSV and JSON for audit records.</p>
          </div>
        }
      />

      {/* Main Grid: Left Setup Column & Right Active Controls / Live Dashboard */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start h-fit">
        {/* Left Column: Setup Form */}
        <SimulatorConfigForm
          scenarioType={scenarioType}
          setScenarioType={setScenarioType}
          seed={seed}
          setSeed={setSeed}
          durationSeconds={durationSeconds}
          setDurationSeconds={setDurationSeconds}
          attackPeakPps={attackPeakPps}
          setAttackPeakPps={setAttackPeakPps}
          speedMultiplier={speedMultiplier}
          setSpeedMultiplier={setSpeedMultiplier}
          bandwidthMbps={bandwidthMbps}
          setBandwidthMbps={setBandwidthMbps}
          cpuCapacityPps={cpuCapacityPps}
          setCpuCapacityPps={setCpuCapacityPps}
          maxConnections={maxConnections}
          setMaxConnections={setMaxConnections}
          maxLatencyMs={maxLatencyMs}
          setMaxLatencyMs={setMaxLatencyMs}
          loading={loading}
          onCreateRun={handleCreateRun}
        />

        {/* Right 2 Columns: Active Controls, Live Metrics & Live Chart */}
        <div className="lg:col-span-2 space-y-5 h-fit">
          {activeRun ? (
            <div className="bg-[#111827]/70 backdrop-blur-xl border border-gray-700/60 rounded-xl p-5 shadow-xl space-y-5">
              <SimulatorControls
                activeRun={activeRun}
                isStepping={isStepping}
                isExportingCsv={isExportingCsv}
                isExportingJson={isExportingJson}
                onControl={handleControl}
                onExport={handleExport}
              />

              <SimulatorTelemetryGrid
                latestTick={latestTick}
                liveBlockedPct={liveBlockedPct}
                isShieldActive={isShieldActive}
              />

              {/* Dynamic Live Attack & Defense Chart */}
              <div className="bg-[#090D16] border border-gray-700/60 rounded-xl p-4 space-y-2">
                <div className="flex items-center justify-between border-b border-gray-800 pb-2">
                  <h3 className="text-xs font-bold text-gray-100 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-[#00FF9D]" />
                    Real-time Test Traffic Graph
                  </h3>
                  <span className="text-[11px] font-mono text-[#00FF9D]">
                    {recentTicks.length} seconds recorded
                  </span>
                </div>
                <SimulationLiveChart ticks={recentTicks} />
              </div>

              {/* Ground Truth Scorecard */}
              {(activeRun.scorecard || recentTicks.length >= 3) && (
                <SimulatorScorecard
                  activeRun={activeRun}
                  recentTicks={recentTicks}
                  liveBlockedPct={liveBlockedPct}
                  aiTimeToDetectSeconds={aiTimeToDetectSeconds}
                  aiTimeToMitigateSeconds={aiTimeToMitigateSeconds}
                  totalOfferedLegit={totalOfferedLegit}
                  totalDroppedLegit={totalDroppedLegit}
                />
              )}
            </div>
          ) : (
            <div className="bg-[#111827]/70 backdrop-blur-xl border border-gray-700/60 rounded-xl p-12 text-center text-gray-400 text-sm space-y-2">
              <Info className="w-8 h-8 text-[#00FF9D] mx-auto opacity-70" />
              <div>No test session loaded.</div>
              <p className="text-xs text-gray-400">
                Choose a test scenario on the left and click &quot;Initialize Simulation Run&quot; to begin.
              </p>
            </div>
          )}

          {/* Past Simulation Runs Table */}
          <SimulatorHistoryTable
            pastRuns={pastRuns}
            activeRunId={activeRun?.run_id}
            onRefresh={refreshPastRuns}
            onLoadRun={loadRunDetail}
          />
        </div>
      </div>
    </div>
  );
}
