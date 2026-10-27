"use client";

import { useCallback, useState } from "react";

import { AlertDetailsModal } from "@/components/alerts/AlertDetailsModal";
import { AlertsTable } from "@/components/alerts/AlertsTable";
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
import { AlertTriangle, Bell, RefreshCw, Shield } from "@/components/ui/icons";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { api, type AlertItem } from "@/lib/api";
import { usePolling } from "@/lib/polling";

export default function AlertsPage() {
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [searchIp, setSearchIp] = useState<string>("");
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);

  const fetchAlerts = useCallback(() => {
    return api.getAlerts({
      limit: 50,
      severity: severityFilter === "all" ? undefined : severityFilter,
      target_ip: searchIp.trim() ? searchIp.trim() : undefined,
    });
  }, [severityFilter, searchIp]);

  const { data, loading, error, isStale, isDisconnected, lastUpdated, refresh } =
    usePolling(fetchAlerts, 3000);

  const [isManualRefreshing, setIsManualRefreshing] = useState(false);

  const handleManualRefresh = async () => {
    setIsManualRefreshing(true);
    try {
      await refresh();
    } finally {
      setIsManualRefreshing(false);
    }
  };

  const statusType = isDisconnected
    ? "disconnected"
    : isStale
      ? "stale"
      : loading
        ? "loading"
        : "online";

  const alerts = data?.alerts || [];
  const criticalCount = alerts.filter((a) => a.severity.toLowerCase() === "critical").length;
  const highCount = alerts.filter((a) => a.severity.toLowerCase() === "high" || a.severity.toLowerCase() === "warning").length;
  const mediumCount = alerts.filter((a) => a.severity.toLowerCase() === "medium").length;
  const lowCount = alerts.filter((a) => a.severity.toLowerCase() === "low" || a.severity.toLowerCase() === "info").length;

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-[rgba(75,85,99,0.3)]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-100 flex items-center gap-3 font-mono">
            <Bell className="w-6 h-6 text-[#00FF9D]" />
            Threat Incidents
          </h1>
          <p className="text-xs text-[#9CA3AF] mt-1 font-sans">
            Real-time data packet inspection and AI Random Forest threat classification.
          </p>
        </div>

        <div className="flex items-center gap-4">
          <StatusIndicator status={statusType} />
          {lastUpdated && (
            <span className="text-xs text-[#9CA3AF] font-mono">
              Updated: {lastUpdated.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false })} IST
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleManualRefresh}
            disabled={isManualRefreshing}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isManualRefreshing ? "animate-spin text-[#00FF9D]" : ""}`} />
            {isManualRefreshing ? "Refreshing..." : "Refresh"}
          </Button>
        </div>
      </div>

      {/* Quick Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Threat Events"
          value={data?.total_count ?? alerts.length}
          subtitle="All detected anomalous flows"
          icon={<Bell className="w-4 h-4 text-[#00FF9D]" />}
        />
        <MetricCard
          title="Critical Threats"
          value={criticalCount}
          subtitle="Immediate mitigation recommended"
          icon={<AlertTriangle className="w-4 h-4 text-rose-500" />}
          badge={<Badge variant="critical">{criticalCount > 0 ? "URGENT" : "CLEAR"}</Badge>}
        />
        <MetricCard
          title="High & Warning"
          value={highCount}
          subtitle="Heavy anomalous packet volume"
          icon={<AlertTriangle className="w-4 h-4 text-amber-400" />}
          badge={<Badge variant="warning">{highCount > 0 ? "ELEVATED" : "NORMAL"}</Badge>}
        />
        <MetricCard
          title="Medium & Low"
          value={mediumCount + lowCount}
          subtitle={`Medium: ${mediumCount} · Low: ${lowCount}`}
          icon={<Shield className="w-4 h-4 text-[#06B6D4]" />}
          badge={<Badge variant="matrix">MONITORED</Badge>}
        />
      </div>

      {/* Filter Toolbar */}
      <Card>
        <CardContent className="px-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs text-[#9CA3AF] font-mono">Filter by Severity:</span>
            <div className="flex flex-wrap items-center gap-1.5">
              {[
                { id: "all", label: "All", count: data?.total || alerts.length, color: "text-gray-200" },
                { id: "critical", label: "Critical", count: criticalCount, color: "text-rose-400" },
                { id: "high", label: "High", count: highCount, color: "text-amber-400" },
                { id: "medium", label: "Medium", count: mediumCount, color: "text-cyan-400" },
                { id: "low", label: "Low", count: lowCount, color: "text-emerald-400" },
              ].map((tab) => {
                const isActive = severityFilter === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setSeverityFilter(tab.id)}
                    className={`px-3 py-1 rounded-md text-xs font-mono transition-all flex items-center gap-1.5 border ${
                      isActive
                        ? "bg-[#1F2937] border-[#00FF9D] text-[#00FF9D] shadow-xs"
                        : "bg-[#090D16] border-[rgba(75,85,99,0.4)] text-gray-400 hover:text-gray-200 hover:border-gray-500"
                    }`}
                  >
                    <span>{tab.label}</span>
                    <span className={`text-[10px] px-1.5 py-0.2 rounded-full bg-black/40 ${tab.color}`}>
                      {tab.count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-[#9CA3AF] font-mono">Target IP:</label>
            <input
              suppressHydrationWarning
              autoComplete="off"
              type="text"
              placeholder="e.g. 192.168.1.150"
              value={searchIp}
              onChange={(e) => setSearchIp(e.target.value)}
              className="bg-[#090D16] border border-[rgba(75,85,99,0.4)] rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono placeholder:text-gray-600 focus:border-[#00FF9D] focus:outline-none"
            />
            {(severityFilter !== "all" || searchIp.trim()) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSeverityFilter("all");
                  setSearchIp("");
                }}
              >
                Reset
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Alerts Table */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="font-mono">
              High-Density Security Incident Feed (              {data?.total_count ?? alerts.length})
            </CardTitle>
            <CardDescription>
              Select any incident row to open the interactive mitigation drawer and evaluate safety gate guardrails
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="p-4 mb-4 rounded-xl border border-red-500/40 bg-[rgba(239,68,68,0.15)] text-[#EF4444] text-xs font-mono">
              Error fetching telemetry alerts: {error.message}
            </div>
          )}

          <AlertsTable
            alerts={alerts}
            onSelectAlert={(alert) => setSelectedAlert(alert)}
          />
        </CardContent>
      </Card>

      {/* Interactive Mitigation Drawer */}
      <AlertDetailsModal
        alert={selectedAlert}
        onClose={() => setSelectedAlert(null)}
      />
    </div>
  );
}
