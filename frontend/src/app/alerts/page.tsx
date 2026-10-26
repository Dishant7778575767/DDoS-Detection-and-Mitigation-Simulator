"use client";

import { useCallback, useState } from "react";

import { AlertDetailsModal } from "@/components/alerts/AlertDetailsModal";
import { AlertsTable } from "@/components/alerts/AlertsTable";
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
    usePolling(fetchAlerts, 4000);

  const statusType = isDisconnected
    ? "disconnected"
    : isStale
      ? "stale"
      : loading
        ? "loading"
        : "online";

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-cyan-500/15">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-cyan-50 flex items-center gap-3">
            <Bell className="w-6 h-6 text-amber-400" />
            Threat Alerts & Detections
          </h1>
          <p className="text-xs text-sky-200/60 mt-1">
            Real-time attack signatures detected by dual-signal engine (Random Forest + Traffic Rate)
          </p>
        </div>

        <div className="flex items-center gap-4">
          <StatusIndicator status={statusType} />
          {lastUpdated && (
            <span className="text-xs text-sky-300/40 font-mono">
              {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <Button variant="outline" size="sm" onClick={() => void refresh()}>
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <Card>
        <CardContent className="p-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <label className="text-xs text-sky-200/70 font-mono">Severity:</label>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="bg-[#050b14] border border-cyan-500/20 rounded-lg px-3 py-1.5 text-xs text-cyan-200 font-mono focus:border-cyan-400 focus:outline-none"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          <div className="flex items-center gap-3">
            <label className="text-xs text-sky-200/70 font-mono">Target IP:</label>
            <input
              type="text"
              placeholder="e.g. 192.168.1.150"
              value={searchIp}
              onChange={(e) => setSearchIp(e.target.value)}
              className="bg-[#050b14] border border-cyan-500/20 rounded-lg px-3 py-1.5 text-xs text-cyan-200 font-mono placeholder:text-slate-600 focus:border-cyan-400 focus:outline-none"
            />
          </div>
        </CardContent>
      </Card>

      {/* Alerts Table */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Active & Historical Alerts ({data?.total || 0})</CardTitle>
            <CardDescription>
              Each alert indicates whether single-signal or dual-signal criteria were met
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="p-4 mb-4 rounded-xl border border-rose-500/30 bg-rose-950/20 text-rose-300 text-xs font-mono">
              Error loading alerts: {error.message}
            </div>
          )}

          <AlertsTable
            alerts={data?.alerts || []}
            onSelectAlert={(alert) => setSelectedAlert(alert)}
          />
        </CardContent>
      </Card>

      {/* Simulation Modal */}
      <AlertDetailsModal
        alert={selectedAlert}
        onClose={() => setSelectedAlert(null)}
      />
    </div>
  );
}
