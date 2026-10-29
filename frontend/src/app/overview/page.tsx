"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertDetailsModal } from "@/components/alerts/AlertDetailsModal";
import { AlertsTable } from "@/components/alerts/AlertsTable";
import { TrafficAreaChart } from "@/components/charts/TrafficAreaChart";
import { MetricCard } from "@/components/common/MetricCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import {
  Activity,
  AlertTriangle,
  RefreshCw,
  Server,
  Shield,
  Zap,
} from "@/components/ui/icons";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import {
  api,
  type AlertItem,
  type SimulationRunResponse,
  type SimulationTickItem,
  type TrafficSummaryResponse,
} from "@/lib/api";
import { formatISTTime } from "@/lib/formatters";
import { usePolling } from "@/lib/polling";

interface LatestSimData {
  run: SimulationRunResponse;
  ticks: SimulationTickItem[];
}

export default function OverviewPage() {
  const fetchTraffic = useCallback(() => api.getTrafficSummary(), []);
  const fetchAlerts = useCallback(() => api.getAlerts({ limit: 5 }), []);

  const fetchLatestSimulation = useCallback(async (): Promise<LatestSimData | null> => {
    try {
      const list = await api.listSimulations({ limit: 1 });
      if (list.runs && list.runs.length > 0) {
        const topRun = list.runs[0];
        const [runDetails, ticksRes] = await Promise.all([
          api.getSimulation(topRun.run_id),
          api.getSimulationTicks(topRun.run_id, { limit: 40 }),
        ]);
        return {
          run: runDetails,
          ticks: ticksRes.ticks || [],
        };
      }
    } catch (err: unknown) {
      if (process.env.NODE_ENV === "development") {
        console.warn(
          "Overview: latest simulation stream offline or pending:",
          err instanceof Error ? err.message : err
        );
      }
    }
    return null;
  }, []);

  const {
    data: trafficData,
    loading: trafficLoading,
    error: trafficError,
    isStale,
    isDisconnected,
    lastUpdated,
    refresh: refreshTraffic,
  } = usePolling<TrafficSummaryResponse>(fetchTraffic, 3000);

  const { data: alertsData, refresh: refreshAlerts } = usePolling(
    fetchAlerts,
    4000
  );

  const {
    data: simData,
    refresh: refreshSim,
  } = usePolling<LatestSimData | null>(fetchLatestSimulation, 2500);

  const fetchShieldStatus = useCallback(() => api.getMitigationStatus(), []);
  const {
    data: shieldStatus,
    refresh: refreshShield,
  } = usePolling(fetchShieldStatus, 2500);

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isActivatingShield, setIsActivatingShield] = useState(false);
  const [lastCheckMessage, setLastCheckMessage] = useState<string | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);

  useEffect(() => {
    const handleShieldUpdate = () => {
      void refreshShield();
      void refreshSim();
    };
    window.addEventListener("sentrix:shield_update", handleShieldUpdate);
    return () => window.removeEventListener("sentrix:shield_update", handleShieldUpdate);
  }, [refreshShield, refreshSim]);

  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([
        refreshTraffic(),
        refreshAlerts(),
        refreshSim(),
        refreshShield(),
      ]);
      setLastCheckMessage(`Telemetry fresh at ${formatISTTime(new Date())} IST`);
      setTimeout(() => setLastCheckMessage(null), 3000);
    } catch (err) {
      console.error("Refresh error:", err);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleQuickActivateShield = async () => {
    setIsActivatingShield(true);
    try {
      await api.simulateMitigation({
        target_ip: "192.168.1.100",
        action_type: "rate_limit",
        rate_limit_pps: 5000,
        duration_seconds: 60,
        reason: "Operator rapid defense activation from Overview dashboard",
      });
      await Promise.all([refreshShield(), refreshTraffic()]);
      setLastCheckMessage("Defense Shield activated (5,000 PPS rate limit)");
      setTimeout(() => setLastCheckMessage(null), 4000);
    } catch (err) {
      console.error("Shield activation error:", err);
    } finally {
      setIsActivatingShield(false);
    }
  };

  const activeRun = simData?.run;
  const isSimRunning = activeRun?.status === "running";

  const handleCancelShield = async () => {
    const mitigation = shieldStatus?.latest_mitigation;
    try {
      if (mitigation?.source === "simulation_run" && mitigation.run_id) {
        try {
          await api.controlSimulation(mitigation.run_id, "cancel");
        } catch (simErr) {
          console.debug("Simulation cancel non-critical error:", simErr);
        }
      } else if (activeRun && activeRun.status === "running") {
        try {
          await api.controlSimulation(activeRun.run_id, "cancel");
        } catch (simErr) {
          console.debug("Active run cancel non-critical error:", simErr);
        }
      }

      const actionToCancel = mitigation?.action_id;
      if (actionToCancel) {
        try {
          await api.cancelMitigation(actionToCancel);
        } catch (mitErr) {
          console.debug("Mitigation cancel non-critical error:", mitErr);
        }
      }

      window.dispatchEvent(new CustomEvent("sentrix:shield_update"));
      await Promise.all([refreshShield(), refreshSim()]);
      setLastCheckMessage("Defense Shield cancelled");
      setTimeout(() => setLastCheckMessage(null), 3000);
    } catch (err) {
      console.error("Shield cancellation error:", err);
    }
  };

  const simTicks = useMemo(() => simData?.ticks || [], [simData?.ticks]);
  const latestSimTick = simTicks.length > 0 ? simTicks[simTicks.length - 1] : null;

  const isShieldActive = Boolean(shieldStatus?.shield_active);
  const activeMitigation = shieldStatus?.latest_mitigation;
  const remainingShieldSec = activeMitigation?.remaining_seconds ?? 0;
  const totalShieldSec = activeMitigation?.duration_seconds ?? 60;
  const shieldProgressPct = totalShieldSec > 0
    ? Math.max(5, Math.min(100, Math.round(((totalShieldSec - remainingShieldSec) / totalShieldSec) * 100)))
    : 0;

  // Real-time Traffic calculations
  const liveObservedPps =
    trafficData?.packet_rate && trafficData.packet_rate > 0
      ? Math.round(trafficData.packet_rate)
      : 0;

  // Attack detection triggers
  const isSimAttack = Boolean(isSimRunning && latestSimTick && latestSimTick.offered_attack_pps > 0);
  const hasActiveAlert = alertsData?.alerts?.some((a) => a.status === "active") ?? false;
  const isAttackActive = isSimAttack || hasActiveAlert;

  const normalSpeed = isSimRunning && latestSimTick
    ? Math.round(latestSimTick.offered_legit_pps)
    : liveObservedPps;
  const attackSpeed = isSimRunning && latestSimTick
    ? Math.round(latestSimTick.offered_attack_pps)
    : 0;

  const livePps = isSimRunning && latestSimTick
    ? normalSpeed + attackSpeed
    : liveObservedPps;

  const currentAvailability =
    isSimRunning && latestSimTick ? latestSimTick.availability_pct : null;

  const isHealthy =
    currentAvailability !== null && currentAvailability >= 85;

  // Chart telemetry points
  const chartPoints = useMemo(() => {
    if (isSimRunning && simTicks && simTicks.length > 0) {
      return simTicks.map((t) => {
        const aPps = Math.round(t.offered_attack_pps);
        const nPps = Math.round(t.offered_legit_pps);
        const totalPps = aPps + nPps;
        return {
          time: formatISTTime(t.timestamp),
          pps: totalPps,
          attack_pps: aPps,
          normal_pps: nPps,
          syn_pps: aPps,
          bps: totalPps * 128 * 8,
        };
      });
    }

    return trafficData?.time_series ?? [];
  }, [isSimRunning, simTicks, trafficData?.time_series]);

  const statusType = isDisconnected
    ? "disconnected"
    : isStale
      ? "stale"
      : trafficLoading
        ? "loading"
        : "online";

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-gray-800">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-100 flex items-center gap-3">
            <Activity className="w-7 h-7 text-[#00FF9D]" />
            Traffic & Detection Overview
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Flow telemetry and synthetic simulation results. This dashboard does not monitor live network interfaces.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <StatusIndicator status={statusType} />
          {lastCheckMessage && (
            <span className="text-[11px] font-mono text-[#00FF9D] bg-[rgba(0,255,157,0.12)] border border-[#00FF9D]/40 px-2.5 py-1 rounded-md animate-pulse">
              ✓ {lastCheckMessage}
            </span>
          )}
          {lastUpdated && !lastCheckMessage && (
            <span className="text-xs text-gray-400 font-mono">
              Last checked: {formatISTTime(lastUpdated)} IST
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefreshAll}
            disabled={isRefreshing}
            title="Refresh dashboard data"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-[#00FF9D]" : ""}`} />
            {isRefreshing ? "Checking..." : "Check Now"}
          </Button>
        </div>
      </div>

      {/* Disconnection Warning */}
      {trafficError && (
        <div className="p-4 rounded-xl border border-red-500/40 bg-red-500/15 text-[#EF4444] flex items-center gap-3 text-sm font-mono">
          <AlertTriangle className="w-5 h-5 text-[#EF4444] shrink-0" />
          <span>
            Backend is offline. Please run: <code className="text-white bg-black/40 px-2 py-0.5 rounded">uvicorn backend.app.main:app --port 8000</code> in terminal.
          </span>
        </div>
      )}

      {/* Prominent AI Classifier Banner */}
      <div className={`p-6 rounded-2xl border-2 transition-all shadow-2xl ${
        isShieldActive
          ? "bg-linear-to-r from-[rgba(0,255,157,0.2)] via-[#1F2937]/90 to-[#090D16]/95 border-[#00FF9D] shadow-[0_0_35px_rgba(0,255,157,0.3)]"
          : isAttackActive
          ? "bg-linear-to-r from-red-500/25 via-[#1F2937]/90 to-[#090D16]/95 border-[#EF4444] shadow-[0_0_35px_rgba(239,68,68,0.3)]"
          : "bg-linear-to-r from-[rgba(0,255,157,0.15)] via-[#1F2937]/90 to-[#090D16]/95 border-[#00FF9D] shadow-[0_0_30px_rgba(0,255,157,0.2)]"
      }`}>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono uppercase tracking-widest text-gray-400">
                Current Detection State:
              </span>
              <span className={`w-3 h-3 rounded-full ${isShieldActive ? "bg-[#00FF9D] animate-pulse" : isAttackActive ? "bg-[#EF4444] animate-ping" : "bg-[#00FF9D]"}`} />
            </div>

            <div className="flex items-center gap-4">
              <div className={`text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight font-mono ${
                isShieldActive ? "text-[#00FF9D]" : isAttackActive ? "text-[#EF4444]" : "text-[#00FF9D]"
              }`}>
                {isShieldActive
                  ? "DEFENSE SHIELD ACTIVE (RATE-LIMITED)"
                  : isAttackActive
                  ? "THREAT SIGNAL PRESENT"
                  : "NO ACTIVE THREAT ALERT"}
              </div>
            </div>

            <p className="text-sm text-gray-300 max-w-2xl leading-relaxed">
              {isShieldActive
                ? `Defense Shield is actively rate-limiting malicious flows to ${activeMitigation?.rate_limit_pps?.toLocaleString() || "5,000"} PPS on ${activeMitigation?.target_ip || "target node"}. Collateral damage is near 0%.`
                : isAttackActive
                ? `SENTRIX has an active threat alert${isSimAttack ? ` and the current simulation offers ${attackSpeed.toLocaleString()} attack PPS` : ""}. Review the alert or run a simulation to inspect its impact.`
                : "No active threat alert is currently recorded. Incoming live network interfaces are not monitored by this simulator."}
            </p>

            {/* Shield Auto-Expiry Progress Bar */}
            {isShieldActive && (
              <div className="pt-2 max-w-md">
                <div className="flex justify-between items-center text-xs font-mono text-[#00FF9D] mb-1">
                  <span className="flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5 text-[#00FF9D]" />
                    Auto-reset countdown:
                  </span>
                  <span className="font-bold">{remainingShieldSec}s remaining</span>
                </div>
                <div className="w-full bg-[#1F2937] rounded-full h-2.5 overflow-hidden border border-[#00FF9D]/30">
                  <div
                    className="bg-linear-to-r from-[#00FF9D] to-[#06B6D4] h-2.5 transition-all duration-1000"
                    style={{ width: `${Math.max(5, Math.min(100, 100 - shieldProgressPct))}%` }}
                  />
                </div>
              </div>
            )}
          </div>

          <div className="flex flex-col sm:flex-row md:flex-col items-start md:items-end gap-3 shrink-0">
            {isShieldActive ? (
              <Button
                variant="outline"
                size="md"
                onClick={handleCancelShield}
                className="border-rose-500/60 text-rose-300 hover:bg-rose-500/20 font-mono"
              >
                Disable Shield ✕
              </Button>
            ) : isAttackActive ? (
              <Button
                variant="danger"
                size="md"
                onClick={handleQuickActivateShield}
                loading={isActivatingShield}
                className="font-mono bg-rose-600 hover:bg-rose-500 text-white shadow-lg animate-pulse"
              >
                <Shield className="w-4 h-4" />
                Activate Defense Shield →
              </Button>
            ) : (
              <div className="px-4 py-2 rounded-xl bg-[#090D16] border border-gray-700/60 text-right">
                <div className="text-[11px] text-gray-400 uppercase font-mono">Mitigation Mode</div>
                <div className="text-lg font-bold text-[#00FF9D] font-mono">Simulation only</div>
              </div>
            )}
            <Link href="/simulator">
              <Button variant="primary" size="md">
                Launch Attack Test →
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. Total Speed */}
        <MetricCard
          title="Observed Packet Rate"
          value={livePps}
          unit="packets/sec"
          subtitle={isSimRunning && latestSimTick
            ? `Legitimate: ${normalSpeed.toLocaleString()} · Attack: ${attackSpeed.toLocaleString()}`
            : "Aggregate rate from submitted flow records"}
          icon={<Zap className="w-4 h-4 text-[#00FF9D]" />}
        />

        {/* 2. Website Health */}
        <MetricCard
          title="Website Health"
          value={currentAvailability === null ? "N/A" : `${currentAvailability.toFixed(1)}%`}
          subtitle={currentAvailability === null ? "Available for simulation runs only" : isHealthy ? "Virtual victim within service limits" : "Virtual victim under resource pressure"}
          icon={<Server className={`w-4 h-4 ${currentAvailability === null ? "text-[#06B6D4]" : isHealthy ? "text-[#10B981]" : "text-[#EF4444]"}`} />}
          badge={
            <Badge variant={currentAvailability === null ? "cyan" : isHealthy ? "normal" : "critical"}>
              {currentAvailability === null ? "Simulation only" : isHealthy ? "Healthy" : "Degraded"}
            </Badge>
          }
        />

        {/* 3. AI Verdict */}
        <MetricCard
          title="AI Classification"
          value={isAttackActive ? "Threat alert" : "No active alert"}
          subtitle="Based on persisted alert records; not live packet inspection"
          icon={<Activity className={`w-4 h-4 ${isAttackActive ? "text-[#EF4444]" : "text-[#00FF9D]"}`} />}
          badge={
            <Badge variant={isAttackActive ? "critical" : "normal"}>
              {isAttackActive ? "DDoS" : "Benign"}
            </Badge>
          }
        />

        {/* 4. Protection Guard */}
        <MetricCard
          title="Defense Shield"
          value={
            isShieldActive
              ? `Shield Active (${remainingShieldSec}s)`
              : isAttackActive
              ? "Attack - Shield Off"
              : "Standby"
          }
          subtitle={
            isShieldActive
              ? `Limiting to ${activeMitigation?.rate_limit_pps?.toLocaleString() || "5,000"} PPS`
              : "Virtual mitigation actions only"
          }
          icon={<Shield className={`w-4 h-4 ${isShieldActive ? "text-[#00FF9D] animate-pulse" : isAttackActive ? "text-rose-400" : "text-[#06B6D4]"}`} />}
          badge={
            <Badge variant={isShieldActive ? "matrix" : isAttackActive ? "critical" : "normal"}>
              {isShieldActive ? "SHIELDING" : isAttackActive ? "EXPOSED" : "READY"}
            </Badge>
          }
        />
      </div>

      {/* Main Realtime Chart */}
      <Card>
        <CardHeader className="flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-[#00FF9D]" />
              {isSimRunning ? "Synthetic Simulation Traffic" : "Traffic Time Series"}
            </CardTitle>
            <CardDescription>
              {isSimRunning
                ? "Per-tick synthetic scenario data from the active run."
                : "No historical series is provided by the current traffic summary API."}
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs font-mono">
            {isSimRunning && (
              <>
                <span className="flex items-center gap-1.5 text-[#00FF9D]">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#00FF9D]" />
                  Legitimate synthetic traffic
                </span>
                <span className="flex items-center gap-1.5 text-[#EF4444]">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#EF4444]" />
                  Synthetic attack traffic
                </span>
              </>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <TrafficAreaChart data={chartPoints} />
        </CardContent>
      </Card>

      {/* Recent Alerts Feed Table */}
      <Card>
        <CardHeader className="flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <CardTitle>Recent Attack Warnings & Incidents</CardTitle>
            <CardDescription>
              Every time the AI detects an attack, it creates an incident record with the proof
            </CardDescription>
          </div>
          <Link href="/alerts">
            <Button variant="ghost" size="sm">
              See All Incidents →
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          <AlertsTable
            alerts={alertsData?.alerts || []}
            onSelectAlert={(alert) => setSelectedAlert(alert)}
          />
        </CardContent>
      </Card>

      {/* Interactive Threat Modal */}
      <AlertDetailsModal
        alert={selectedAlert}
        onClose={() => setSelectedAlert(null)}
      />
    </div>
  );
}
