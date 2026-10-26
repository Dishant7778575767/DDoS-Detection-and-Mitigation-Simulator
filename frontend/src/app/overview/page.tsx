"use client";

import Link from "next/link";
import { useCallback, useMemo } from "react";

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
import { api, type TrafficSummaryResponse } from "@/lib/api";
import { usePolling } from "@/lib/polling";

export default function OverviewPage() {
  const fetchTraffic = useCallback(() => api.getTrafficSummary(), []);
  const fetchAlerts = useCallback(() => api.getAlerts({ limit: 5 }), []);

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

  const handleRefreshAll = () => {
    void refreshTraffic();
    void refreshAlerts();
  };

  const chartPoints = useMemo(() => {
    if (trafficData?.time_series && trafficData.time_series.length > 0) {
      return trafficData.time_series;
    }
    const currentPps = trafficData?.avg_fwd_pps || 4200;
    const currentSyn = trafficData?.avg_syn_pps || 380;
    const baseTime = lastUpdated ? lastUpdated.getTime() : 1730000000000;
    return Array.from({ length: 12 }).map((_, i) => {
      const t = new Date(baseTime - (11 - i) * 5000);
      const jitter = Math.sin(i / 2) * 450;
      return {
        time: t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
        pps: Math.max(100, Math.round(currentPps + jitter)),
        syn_pps: Math.max(20, Math.round(currentSyn + jitter * 0.15)),
        bps: Math.round((currentPps + jitter) * 128 * 8),
      };
    });
  }, [trafficData, lastUpdated]);

  const statusType = isDisconnected
    ? "disconnected"
    : isStale
      ? "stale"
      : trafficLoading
        ? "loading"
        : "online";

  return (
    <div className="space-y-6">
      {/* Top Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-cyan-500/15">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-cyan-50 flex items-center gap-3">
            <Activity className="w-6 h-6 text-cyan-400" />
            SOC Telemetry Overview
          </h1>
          <p className="text-xs text-sky-200/60 mt-1">
            Real-time ingress traffic analysis, ML inference, and dual-signal threat telemetry
          </p>
        </div>

        <div className="flex items-center gap-4">
          <StatusIndicator status={statusType} />
          {lastUpdated && (
            <span className="text-xs text-sky-300/40 font-mono">
              Updated: {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefreshAll}
            title="Refresh live data"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Disconnection Warning Banner */}
      {trafficError && (
        <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-950/20 text-rose-300 flex items-center gap-3 text-sm">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
          <span>
            Unable to connect to SENTRIX backend API. Ensure the backend server is running on port 8000.
          </span>
        </div>
      )}

      {/* Top 4 KPI Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Ingress Traffic Rate"
          value={trafficData?.avg_fwd_pps || 0}
          unit="pps"
          subtitle={`${trafficData?.recent_flows_10s || 0} flows in last 10s window`}
          icon={<Zap className="w-4 h-4" />}
        />

        <MetricCard
          title="Total Observations"
          value={trafficData?.total_flows || 0}
          subtitle="Active window: 10s / 30s rolling"
          icon={<Server className="w-4 h-4 text-sky-400" />}
        />

        <MetricCard
          title="ML Threat Signal"
          value="Random Forest"
          subtitle="Approved schema: 1.0.0 · Cutoff: 0.75"
          icon={<Activity className="w-4 h-4 text-amber-400" />}
          badge={<Badge variant="normal">rf-1.0.0</Badge>}
        />

        <MetricCard
          title="Mitigation Status"
          value="Simulation"
          subtitle="Host networking safe & unaltered"
          icon={<Shield className="w-4 h-4 text-emerald-400" />}
          badge={<Badge variant="simulation">Safe</Badge>}
        />
      </div>

      {/* Main Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Live Flow Telemetry</CardTitle>
              <CardDescription>
                Packet arrival rates (Packets/s) and SYN flood indicators over time
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 text-xs text-cyan-300 font-mono">
                <span className="w-2.5 h-2.5 rounded-full bg-cyan-400" />
                Fwd PPS
              </span>
              <span className="flex items-center gap-1.5 text-xs text-sky-400 font-mono">
                <span className="w-2.5 h-2.5 rounded-full bg-sky-500" />
                SYN PPS
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <TrafficAreaChart data={chartPoints} />
          </CardContent>
        </Card>

        {/* Target Breakdown & Policy Matrix */}
        <Card>
          <CardHeader>
            <CardTitle>Target IP Breakdown</CardTitle>
            <CardDescription>Flow volume by destination IP</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {trafficData?.target_breakdown &&
              Object.keys(trafficData.target_breakdown).length > 0 ? (
                Object.entries(trafficData.target_breakdown).map(([ip, count]) => (
                  <div key={ip} className="space-y-1">
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-cyan-200">{ip}</span>
                      <span className="text-sky-300/70">{count} flows</span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className="h-full bg-cyan-400 rounded-full"
                        style={{
                          width: `${Math.min(100, Math.max(10, (count / (trafficData.total_flows || 1)) * 100))}%`,
                        }}
                      />
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-10 text-xs text-sky-200/40">
                  No targeted flows recorded yet
                </div>
              )}

              <div className="mt-6 pt-4 border-t border-cyan-500/10">
                <div className="text-xs font-medium text-sky-200/80 mb-2">
                  Dual-Signal Hybrid Policy
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                  <div className="p-2 rounded bg-slate-900/60 border border-slate-800">
                    <span className="text-emerald-400 font-bold">Neither:</span> Monitor
                  </div>
                  <div className="p-2 rounded bg-amber-950/20 border border-amber-900/30">
                    <span className="text-amber-400 font-bold">1 Signal:</span> Alert
                  </div>
                  <div className="p-2 col-span-2 rounded bg-rose-950/20 border border-rose-900/30">
                    <span className="text-rose-400 font-bold">Both Signals:</span> Request
                    Mitigation
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Alerts Feed Table */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Recent Threat Detections</CardTitle>
            <CardDescription>
              Latest alerts evaluated by Random Forest and traffic threshold rules
            </CardDescription>
          </div>
          <Link href="/alerts">
            <Button variant="ghost" size="sm">
              View All Alerts →
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          <AlertsTable alerts={alertsData?.alerts || []} />
        </CardContent>
      </Card>
    </div>
  );
}
