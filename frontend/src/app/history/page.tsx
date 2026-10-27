"use client";

import { Fragment, useCallback, useState } from "react";

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
  CheckCircle2,
  Code,
  Download,
  History as HistoryIcon,
  RefreshCw,
} from "@/components/ui/icons";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { api, getApiAuthToken, type AuditEventItem } from "@/lib/api";
import { usePolling } from "@/lib/polling";

export default function HistoryPage() {
  const [eventTypeFilter, setEventTypeFilter] = useState<string>("all");
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);

  const fetchAudit = useCallback(() => {
    return api.getAudit({
      limit: 50,
      event_type: eventTypeFilter === "all" ? undefined : eventTypeFilter,
    });
  }, [eventTypeFilter]);

  const { data, loading, error, isStale, isDisconnected, lastUpdated, refresh } =
    usePolling(fetchAudit, 4000);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    setRefreshMessage(null);
    try {
      await refresh();
      const timeStr = new Date().toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour12: false,
      });
      setRefreshMessage(`Audit trail synchronized successfully at ${timeStr} IST`);
      setTimeout(() => setRefreshMessage(null), 3000);
    } catch (err: unknown) {
      const msg = err && typeof err === "object" && "message" in err ? String(err.message) : "Failed to refresh audit log";
      setRefreshMessage(`Sync failed: ${msg}`);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleDownloadCsv = async () => {
    const token = getApiAuthToken();
    const url = api.getAuditCsvUrl();
    try {
      const res = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) throw new Error("Failed to export CSV");
      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `sentrix_audit_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err: unknown) {
      const msg = err && typeof err === "object" && "message" in err ? String(err.message) : "Failed to download audit CSV";
      alert(`Export error: ${msg}`);
    }
  };

  const statusType = isDisconnected
    ? "disconnected"
    : isStale
      ? "stale"
      : loading
        ? "loading"
        : "online";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-[rgba(75,85,99,0.3)]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-100 flex items-center gap-3 font-mono">
            <HistoryIcon className="w-6 h-6 text-[#00FF9D]" />
            Security Audit Trail
          </h1>
          <p className="text-xs text-[#9CA3AF] mt-1 font-sans">
            A secure, tamper-proof timeline of network events, threat detections, simulations, and actions taken.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <StatusIndicator status={statusType} />
          {lastUpdated && (
            <span className="text-xs text-[#9CA3AF] font-mono">
              Updated: {lastUpdated.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false })} IST
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="border-[rgba(75,85,99,0.4)] hover:border-[#00FF9D] hover:text-[#00FF9D] transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-[#00FF9D]" : ""}`} />
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </Button>
          <Button variant="primary" size="sm" onClick={handleDownloadCsv}>
            <Download className="w-3.5 h-3.5" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Sync Message Banner */}
      {refreshMessage && (
        <div className="p-3.5 rounded-xl bg-[#090D16] border border-[#00FF9D]/40 text-[#00FF9D] text-xs font-mono flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-[#00FF9D] shrink-0" />
          <span>{refreshMessage}</span>
        </div>
      )}

      {/* Filter Bar */}
      <Card>
        <CardContent className="px-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <label className="text-xs text-[#9CA3AF] font-mono">Event Type Filter:</label>
            <select
              value={eventTypeFilter}
              onChange={(e) => setEventTypeFilter(e.target.value)}
              className="bg-[#090D16] border border-[rgba(75,85,99,0.4)] rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
            >
              <option value="all">All Events</option>
              <option value="simulation_created">simulation_created (Simulation Created)</option>
              <option value="simulation_started">simulation_started (Simulation Clock Started)</option>
              <option value="simulation_paused">simulation_paused (Simulation Paused)</option>
              <option value="simulation_completed">simulation_completed (Simulation Finished)</option>
              <option value="mitigation_triggered">mitigation_triggered (Defense Rule Triggered)</option>
              <option value="alert_created">alert_created (Threat Alert Created)</option>
              <option value="traffic_ingest">traffic_ingest (Traffic Ingest Flow)</option>
              <option value="detection_evaluated">detection_evaluated (AI Flow Evaluated)</option>
              <option value="threshold_update">threshold_update (Threshold Config Updated)</option>
              <option value="emergency_disable">emergency_disable (Emergency Kill-Switch)</option>
            </select>
          </div>

          {eventTypeFilter !== "all" && (
            <Button variant="ghost" size="sm" onClick={() => setEventTypeFilter("all")}>
              Reset Filter
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Audit Events Table */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="font-mono">Audit Records ({data?.total_count ?? data?.total ?? 0})</CardTitle>
            <CardDescription>
              High-density immutable security ledger. Click Details on any entry to inspect raw telemetry payload.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="p-4 mb-4 rounded-xl border border-red-500/40 bg-[rgba(239,68,68,0.15)] text-[#EF4444] text-xs font-mono">
              Error fetching audit records: {error.message}
            </div>
          )}

          <div className="overflow-x-auto rounded-xl border border-[rgba(75,85,99,0.3)] bg-[#090D16]/80 font-mono text-xs">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[rgba(75,85,99,0.3)] bg-[#1F2937]/50 text-[#9CA3AF] text-[11px] uppercase tracking-wider">
                  <th className="py-3 px-3">Timestamp (UTC)</th>
                  <th className="py-3 px-3">Event ID</th>
                  <th className="py-3 px-3">Event Type</th>
                  <th className="py-3 px-3">Actor / Subsystem</th>
                  <th className="py-3 px-3">Action</th>
                  <th className="py-3 px-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[rgba(75,85,99,0.2)]">
                {data?.events && data.events.length > 0 ? (
                  data.events.map((event: AuditEventItem) => {
                    const isExpanded = expandedEventId === event.event_id;
                    const formattedTime = event.timestamp
                      ? new Date(event.timestamp).toISOString().replace("T", " ").slice(0, 19)
                      : "—";

                    return (
                      <Fragment key={event.event_id}>
                        <tr className="hover:bg-[#1F2937]/40 transition-colors">
                          <td className="py-3 px-3 text-[#9CA3AF] whitespace-nowrap">
                            {formattedTime}
                          </td>
                          <td className="py-3 px-3 text-[#00FF9D] font-bold">
                            {event.event_id.slice(0, 8)}...
                          </td>
                          <td className="py-3 px-3">
                            <Badge
                              variant={
                                event.event_type.includes("mitigation") || event.event_type.includes("disable")
                                  ? "critical"
                                  : event.event_type.includes("alert")
                                  ? "warning"
                                  : event.event_type.includes("simulation")
                                  ? "cyan"
                                  : "normal"
                              }
                              className="text-[10px]"
                            >
                              {event.event_type}
                            </Badge>
                          </td>
                          <td className="py-3 px-3 text-gray-200 font-semibold">
                            {event.actor || "system"}
                          </td>
                          <td className="py-3 px-3 text-[#9CA3AF]">
                            {event.action}
                          </td>
                          <td className="py-3 px-3 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setExpandedEventId(isExpanded ? null : event.event_id)}
                              className="text-xs"
                            >
                              <Code className="w-3.5 h-3.5 text-[#00FF9D]" />
                              {isExpanded ? "Collapse" : "Inspect"}
                            </Button>
                          </td>
                        </tr>

                        {isExpanded && (
                          <tr className="bg-[#090D16]">
                            <td colSpan={6} className="p-4 border-b border-[rgba(75,85,99,0.3)]">
                              <div className="space-y-2 rounded-lg bg-[#1F2937]/40 border border-[rgba(75,85,99,0.4)] p-3">
                                <div className="text-[11px] font-bold text-[#00FF9D] flex items-center justify-between">
                                  <span>Raw Event Telemetry Payload</span>
                                  <span className="text-[#9CA3AF] font-normal">SHA256 Signed</span>
                                </div>
                                <pre className="text-[11px] text-[#9CA3AF] overflow-x-auto max-h-60 p-2 rounded bg-[#090D16] border border-[rgba(75,85,99,0.3)]">
                                  {JSON.stringify(event.details, null, 2)}
                                </pre>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-[#9CA3AF]">
                      No audit events recorded for this criteria.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
