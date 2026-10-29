"use client";

import { useCallback, useState } from "react";
import { AlertDetailsModal } from "@/components/alerts/AlertDetailsModal";
import { AlertsTable } from "@/components/alerts/AlertsTable";
import { MetricCard } from "@/components/common/MetricCard";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { Bell, RefreshCw } from "@/components/ui/icons";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { api, type AlertItem } from "@/lib/api";
import { formatISTTime } from "@/lib/formatters";
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

  const { data, loading, isStale, isDisconnected, lastUpdated, refresh } =
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
  const highCount = alerts.filter(
    (a) => a.severity.toLowerCase() === "high" || a.severity.toLowerCase() === "warning"
  ).length;
  const mediumCount = alerts.filter((a) => a.severity.toLowerCase() === "medium").length;
  const lowCount = alerts.filter(
    (a) => a.severity.toLowerCase() === "low" || a.severity.toLowerCase() === "info"
  ).length;

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-gray-800">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-100 flex items-center gap-3 font-mono">
            <Bell className="w-6 h-6 text-[#00FF9D]" />
            Threat Incidents
          </h1>
          <p className="text-xs text-gray-400 mt-1 font-sans">
            Real-time data packet inspection and AI Random Forest threat classification.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <StatusIndicator status={statusType} />
          {lastUpdated && (
            <span className="text-xs text-gray-400 font-mono">
              Updated: {formatISTTime(lastUpdated)} IST
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
          subtitle="All recorded incident payloads"
          icon={<Bell className="w-4 h-4 text-[#00FF9D]" />}
        />
        <MetricCard
          title="Critical Severity"
          value={criticalCount}
          subtitle="Immediate mitigation required"
          icon={<span className="text-rose-400 font-bold">CRIT</span>}
          className="border-rose-500/30"
        />
        <MetricCard
          title="High / Warning"
          value={highCount}
          subtitle="Elevated packet flood risk"
          icon={<span className="text-amber-400 font-bold">WARN</span>}
          className="border-amber-500/30"
        />
        <MetricCard
          title="Medium / Low"
          value={mediumCount + lowCount}
          subtitle="Anomalies under surveillance"
          icon={<span className="text-[#06B6D4] font-bold">INFO</span>}
        />
      </div>

      {/* Filter Toolbar */}
      <Card>
        <CardHeader className="flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <CardTitle className="font-mono text-sm">Threat Incident Query Filters</CardTitle>
            <CardDescription>Filter incoming security incidents by severity or destination IP</CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
            <div className="w-full sm:w-auto">
              <label htmlFor="search-target-ip" className="sr-only">Search Target IP</label>
              <input
                id="search-target-ip"
                type="text"
                placeholder="Filter by target IP..."
                value={searchIp}
                onChange={(e) => setSearchIp(e.target.value)}
                className="w-full sm:w-48 bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono placeholder:text-gray-500 focus:outline-none focus:border-[#00FF9D]"
              />
            </div>
            <div className="w-full sm:w-auto">
              <label htmlFor="select-severity" className="sr-only">Filter Severity</label>
              <select
                id="select-severity"
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="w-full sm:w-36 bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:outline-none focus:border-[#00FF9D]"
              >
                <option value="all">All Severities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <AlertsTable
            alerts={alerts}
            onSelectAlert={(alert) => setSelectedAlert(alert)}
          />
        </CardContent>
      </Card>

      {/* Investigation Modal */}
      <AlertDetailsModal
        alert={selectedAlert}
        onClose={() => setSelectedAlert(null)}
      />
    </div>
  );
}
