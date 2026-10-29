"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertDetailsModal } from "@/components/alerts/AlertDetailsModal";
import { AlertsTable } from "@/components/alerts/AlertsTable";
import { TrafficAreaChart } from "@/components/charts/TrafficAreaChart";
import { ExplainCard } from "@/components/common/ExplainCard";
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
  Cpu,
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
      setLastCheckMessage(`Data refreshed at ${formatISTTime(new Date())} IST`);
      setTimeout(() => setLastCheckMessage(null), 3000);
    } catch (err) {
      console.error("Refresh error:", err);
    } finally {
      setIsRefreshing(false);
    }
  };

  const activeRun = simData?.run;
  const isSimRunning = activeRun?.status === "running";

  const handleQuickActivateShield = async () => {
    // Find real target IP from recent alerts or host system status
    const targetIp =
      alertsData?.alerts?.[0]?.target_ip ||
      shieldStatus?.host_ip ||
      "127.0.0.1";

    setIsActivatingShield(true);
    try {
      // Ensure emergency disable is cleared so shield protection is operational
      await api.emergencyDisable(true);
      await api.simulateMitigation({
        target_ip: targetIp,
        action_type: "rate_limit",
        rate_limit_pps: 5000,
        duration_seconds: 60,
        reason: "Operator rapid defense activation from Overview dashboard",
      });
      await Promise.all([refreshShield(), refreshTraffic()]);
      setLastCheckMessage(`Attack Protection activated for ${targetIp}`);
      setTimeout(() => setLastCheckMessage(null), 4000);
    } catch (err) {
      console.error("Shield activation error:", err);
    } finally {
      setIsActivatingShield(false);
    }
  };

  const handleCancelShield = async () => {
    try {
      // Deactivate shield protection without stopping simulated attack
      await api.emergencyDisable(false);

      const mitigation = shieldStatus?.latest_mitigation;
      const actionToCancel = mitigation?.action_id;
      if (actionToCancel) {
        try {
          await api.cancelMitigation(actionToCancel);
        } catch (mitErr) {
          console.debug("Mitigation cancel non-critical error:", mitErr);
        }
      }

      window.dispatchEvent(new CustomEvent("sentrix:shield_update"));
      await Promise.all([refreshShield(), refreshTraffic()]);
      setLastCheckMessage("Attack Protection deactivated (Shield disabled; traffic will flow unmitigated)");
      setTimeout(() => setLastCheckMessage(null), 4000);
    } catch (err) {
      console.error("Shield cancellation error:", err);
    }
  };

  const handleStopAttack = async () => {
    if (activeRun?.run_id) {
      try {
        await api.controlSimulation(activeRun.run_id, "cancel");
        window.dispatchEvent(new CustomEvent("sentrix:shield_update"));
        await Promise.all([refreshSim(), refreshTraffic()]);
        setLastCheckMessage("Simulated DDoS attack stopped explicitly.");
        setTimeout(() => setLastCheckMessage(null), 3000);
      } catch (err) {
        console.error("Stop attack error:", err);
      }
    }
  };

  const simTicks = useMemo(() => simData?.ticks || [], [simData?.ticks]);
  const latestSimTick = simTicks.length > 0 ? simTicks[simTicks.length - 1] : null;

  const isShieldActive = Boolean(shieldStatus?.shield_active);
  const activeMitigation = shieldStatus?.latest_mitigation;
  const remainingShieldSec =
    activeMitigation?.remaining_seconds ?? 0;
  const totalShieldSec = activeMitigation?.duration_seconds ?? 60;
  const shieldProgressPct =
    totalShieldSec > 0
      ? Math.max(5, Math.min(100, Math.round(((totalShieldSec - remainingShieldSec) / totalShieldSec) * 100)))
      : 0;

  // Real-time Traffic calculations
  const liveObservedPps =
    trafficData?.packet_rate && trafficData.packet_rate > 0
      ? Math.round(trafficData.packet_rate)
      : 0;

  // Attack detection triggers
  const isSimAttack = Boolean(isSimRunning && latestSimTick && (latestSimTick.offered_attack_pps || 0) > 0);
  const hasActiveAlert = alertsData?.alerts?.some((a) => a.status === "active") ?? false;
  const isAttackActive = isSimAttack || hasActiveAlert;

  const normalSpeed = isSimRunning && latestSimTick
    ? Math.round(latestSimTick.offered_legit_pps || 0)
    : liveObservedPps;
  const attackSpeed = isSimRunning && latestSimTick
    ? Math.round(latestSimTick.offered_attack_pps || 0)
    : 0;

  const livePps = isSimRunning && latestSimTick
    ? normalSpeed + attackSpeed
    : liveObservedPps;

  const currentAvailability =
    isSimRunning && latestSimTick ? latestSimTick.availability_pct : null;

  const isHealthy =
    currentAvailability !== null ? currentAvailability >= 85 : !trafficError;

  // Chart telemetry points
  const chartPoints = useMemo(() => {
    if (isSimRunning && simTicks && simTicks.length > 0) {
      return simTicks.map((t) => {
        const aPps = Math.round(t.offered_attack_pps || 0);
        const nPps = Math.round(t.offered_legit_pps || 0);
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
            Overview
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Summary of incoming traffic, security alerts, and system protection status.
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
            The backend API is currently unreachable. If running locally, check that the backend server is running on port 8000.
          </span>
        </div>
      )}

      {/* Plain English Welcome & Explanation Card */}
      <ExplainCard
        title="Welcome to SENTRIX — What does this system do?"
        summary="SENTRIX helps you monitor web traffic reaching your applications, identify suspicious traffic spikes, and verify whether traffic is genuine or an intentional attack. A sudden surge in visitors does not always mean an attack—our trained machine learning model inspects 14 traffic patterns before suggesting a defense."
        tips={[
          "Green indicators mean all services are operating normally.",
          "Amber or Red indicators mean unusual traffic has been flagged for your review.",
          "Use the safe Traffic Simulator at any time to test how the system reacts to sudden traffic.",
        ]}
        technicalDetails={
          <div className="space-y-1.5 text-[11px]">
            <p><strong className="text-gray-200">ML Engine:</strong> Random Forest Classifier (100 estimators, trained on CIC-DDoS2019 dataset).</p>
            <p><strong className="text-gray-200">Feature Vector:</strong> 14 normalized NetFlow parameters (packet rates, byte volume, inter-arrival times, header distributions).</p>
            <p><strong className="text-gray-200">Ingestion Path:</strong> AWS CloudFront Real-Time Access Logs → Amazon Kinesis Stream → SENTRIX Consumer → Durable Database Store.</p>
          </div>
        }
      />

      {/* Prominent Protection & Detection Status Banner */}
      <div
        className={`p-6 rounded-2xl border-2 transition-all shadow-2xl ${
          isShieldActive
            ? "bg-linear-to-r from-[rgba(0,255,157,0.2)] via-[#1F2937]/90 to-[#090D16]/95 border-[#00FF9D] shadow-[0_0_35px_rgba(0,255,157,0.3)]"
            : isAttackActive
            ? "bg-linear-to-r from-red-500/25 via-[#1F2937]/90 to-[#090D16]/95 border-[#EF4444] shadow-[0_0_35px_rgba(239,68,68,0.3)]"
            : "bg-linear-to-r from-[rgba(0,255,157,0.15)] via-[#1F2937]/90 to-[#090D16]/95 border-[#00FF9D] shadow-[0_0_30px_rgba(0,255,157,0.2)]"
        }`}
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono uppercase tracking-widest text-gray-400">
                System Security Status:
              </span>
              <span
                className={`w-3 h-3 rounded-full ${
                  isShieldActive
                    ? "bg-[#00FF9D] animate-pulse"
                    : isAttackActive
                    ? "bg-[#EF4444] animate-ping"
                    : "bg-[#00FF9D]"
                }`}
              />
            </div>

            <div className="flex items-center gap-4">
              <div
                className={`text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight font-sans ${
                  isShieldActive
                    ? "text-[#00FF9D]"
                    : isAttackActive
                    ? "text-[#EF4444]"
                    : "text-[#00FF9D]"
                }`}
              >
                {isShieldActive
                  ? "ATTACK PROTECTION ACTIVE"
                  : isAttackActive
                  ? "POTENTIAL ATTACK FLAGGED"
                  : "ALL TRAFFIC LOOKS NORMAL"}
              </div>
            </div>

            <p className="text-sm text-gray-300 max-w-2xl leading-relaxed">
              {isShieldActive
                ? `Active rate limiting is filtering traffic${activeMitigation?.rate_limit_pps ? ` to ${activeMitigation.rate_limit_pps.toLocaleString()} req/s` : ""} on ${activeMitigation?.target_ip || "target service"}. Legitimate traffic remains unaffected.`
                : isAttackActive
                ? `SENTRIX has flagged an unusual traffic pattern for review${isSimAttack ? ` (${attackSpeed.toLocaleString()} test attack requests/sec in current test)` : ""}. Review the event details below to decide on next steps.`
                : "No abnormal spikes or malicious patterns have been detected. The machine learning model is actively inspecting incoming traffic."}
            </p>

            {/* Shield Auto-Expiry Progress Bar */}
            {isShieldActive && (
              <div className="pt-2 max-w-md">
                <div className="flex justify-between items-center text-xs font-mono text-[#00FF9D] mb-1">
                  <span className="flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5 text-[#00FF9D]" />
                    Automatic reset countdown:
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
            <div className="flex flex-wrap items-center gap-2">
              {isShieldActive ? (
                <Button
                  variant="outline"
                  size="md"
                  onClick={handleCancelShield}
                  className="border-rose-500/60 text-rose-300 hover:bg-rose-500/20 font-sans"
                >
                  Deactivate Protection ✕
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="md"
                  onClick={handleQuickActivateShield}
                  loading={isActivatingShield}
                  className="font-sans bg-[#00FF9D] hover:bg-[#00FF9D]/80 text-[#090D16] font-bold shadow-lg"
                >
                  <Shield className="w-4 h-4 mr-1.5" />
                  Activate Protection →
                </Button>
              )}

              {isSimRunning && (
                <Button
                  variant="danger"
                  size="md"
                  onClick={handleStopAttack}
                  className="font-sans bg-rose-600 hover:bg-rose-500 text-white shadow-md text-xs"
                >
                  Stop Attack ⏹
                </Button>
              )}
            </div>

            {isSimRunning && (
              <div className="text-[11px] font-mono text-amber-300">
                Attack Simulation Active: Tick {activeRun?.current_tick}/{activeRun?.total_ticks}
              </div>
            )}

            <Link href="/simulator">
              <Button variant="primary" size="md">
                Run Safe Traffic Test →
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* KPI Cards (Plain English) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. Incoming Traffic Rate */}
        <MetricCard
          title="Incoming Traffic Rate"
          value={livePps}
          unit="requests/sec"
          subtitle={
            isSimRunning && latestSimTick
              ? `Normal: ${normalSpeed.toLocaleString()} · Flagged: ${attackSpeed.toLocaleString()}`
              : "Speed of incoming web requests"
          }
          icon={<Zap className="w-4 h-4 text-[#00FF9D]" />}
        />

        {/* 2. System Health */}
        <MetricCard
          title="System Health"
          value={
            currentAvailability !== null
              ? `${currentAvailability.toFixed(1)}%`
              : trafficLoading
              ? "Checking..."
              : trafficError
              ? "Unavailable"
              : "Working"
          }
          subtitle={
            currentAvailability !== null
              ? isHealthy
                ? "Simulated service within limits"
                : "Simulated service under pressure"
              : trafficError
              ? "Backend API unreachable"
              : "All services operational"
          }
          icon={
            <Server
              className={`w-4 h-4 ${
                trafficError
                  ? "text-[#EF4444]"
                  : isHealthy
                  ? "text-[#10B981]"
                  : "text-[#EF4444]"
              }`}
            />
          }
          badge={
            <Badge variant={trafficError ? "critical" : isHealthy ? "normal" : "warning"}>
              {trafficError ? "Offline" : isHealthy ? "Working" : "Degraded"}
            </Badge>
          }
        />

        {/* 3. Machine Learning Verdict */}
        <MetricCard
          title="Model Assessment"
          value={isAttackActive ? "Unusual Activity" : "Normal Traffic"}
          subtitle="Trained Random Forest model assessment"
          icon={<Cpu className={`w-4 h-4 ${isAttackActive ? "text-[#EF4444]" : "text-[#00FF9D]"}`} />}
          badge={
            <Badge variant={isAttackActive ? "critical" : "normal"}>
              {isAttackActive ? "DDoS Detected" : "Normal"}
            </Badge>
          }
        />

        {/* 4. Protection Guard */}
        <MetricCard
          title="Attack Protection"
          value={
            isShieldActive
              ? `Active (${remainingShieldSec}s)`
              : isAttackActive
              ? "Recommended"
              : "Standby"
          }
          subtitle={
            isShieldActive
              ? activeMitigation?.rate_limit_pps
                ? `Capping traffic at ${activeMitigation.rate_limit_pps.toLocaleString()} req/s`
                : "Active rate limit enforced"
              : "Ready to filter malicious traffic"
          }
          icon={
            <Shield
              className={`w-4 h-4 ${
                isShieldActive ? "text-[#00FF9D] animate-pulse" : isAttackActive ? "text-rose-400" : "text-[#06B6D4]"
              }`}
            />
          }
          badge={
            <Badge variant={isShieldActive ? "matrix" : isAttackActive ? "critical" : "normal"}>
              {isShieldActive ? "Protected" : isAttackActive ? "Needs Action" : "Ready"}
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
              {isSimRunning ? "Live Traffic Test Activity" : "Live Traffic Activity"}
            </CardTitle>
            <CardDescription>
              {isSimRunning
                ? "Showing traffic from your active test scenario in real time."
                : "Real-time traffic volume. Spikes indicate sudden surges in requests."}
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs font-mono">
            {isSimRunning && (
              <>
                <span className="flex items-center gap-1.5 text-[#00FF9D]">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#00FF9D]" />
                  Normal test requests
                </span>
                <span className="flex items-center gap-1.5 text-[#EF4444]">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#EF4444]" />
                  Flagged attack requests
                </span>
              </>
            )}
            <Link href="/traffic" className="text-xs text-[#06B6D4] hover:underline flex items-center gap-1 font-sans">
              View Detailed Traffic Stream →
            </Link>
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
            <CardTitle>Recent Security Incidents</CardTitle>
            <CardDescription>
              Traffic patterns that exceeded safety baselines or were flagged by the machine learning model.
            </CardDescription>
          </div>
          <Link href="/detection">
            <Button variant="ghost" size="sm">
              See All Flagged Events →
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
