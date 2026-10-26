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

  const fetchAudit = useCallback(() => {
    return api.getAudit({
      limit: 50,
      event_type: eventTypeFilter === "all" ? undefined : eventTypeFilter,
    });
  }, [eventTypeFilter]);

  const { data, loading, error, isStale, isDisconnected, lastUpdated, refresh } =
    usePolling(fetchAudit, 5000);

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
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-cyan-500/15">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-cyan-50 flex items-center gap-3">
            <HistoryIcon className="w-6 h-6 text-sky-400" />
            Immutable Audit Trail & History
          </h1>
          <p className="text-xs text-sky-200/60 mt-1">
            Complete cryptographic audit log recording detections, threshold updates, and mitigation events
          </p>
        </div>

        <div className="flex items-center gap-3">
          <StatusIndicator status={statusType} />
          {lastUpdated && (
            <span className="text-xs text-sky-300/40 font-mono">
              {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <Button variant="outline" size="sm" onClick={() => refresh()}>
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>
          <Button variant="primary" size="sm" onClick={handleDownloadCsv}>
            <Download className="w-3.5 h-3.5" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      <Card>
        <CardContent className="p-4 flex items-center gap-4">
          <label className="text-xs text-sky-200/70 font-mono">Filter Event Type:</label>
          <select
            value={eventTypeFilter}
            onChange={(e) => setEventTypeFilter(e.target.value)}
            className="bg-[#050b14] border border-cyan-500/20 rounded-lg px-3 py-1.5 text-xs text-cyan-200 font-mono focus:border-cyan-400 focus:outline-none"
          >
            <option value="all">All Events</option>
            <option value="traffic_ingest">traffic_ingest</option>
            <option value="detection_evaluated">detection_evaluated</option>
            <option value="alert_created">alert_created</option>
            <option value="mitigation_simulated">mitigation_simulated</option>
            <option value="mitigation_cancelled">mitigation_cancelled</option>
            <option value="emergency_disable">emergency_disable</option>
            <option value="threshold_update">threshold_update</option>
          </select>
        </CardContent>
      </Card>

      {/* Audit Events Table */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Audit Records ({data?.total_count ?? data?.total ?? 0})</CardTitle>
            <CardDescription>
              Chronological ledger of security and configuration changes
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="p-4 mb-4 rounded-xl border border-rose-500/30 bg-rose-950/20 text-rose-300 text-xs">
              Error fetching audit records: {error.message}
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-cyan-500/15 text-sky-300/60 uppercase tracking-wider">
                  <th className="pb-3 px-3">Timestamp (UTC)</th>
                  <th className="pb-3 px-3">Event ID</th>
                  <th className="pb-3 px-3">Event Type</th>
                  <th className="pb-3 px-3">Actor</th>
                  <th className="pb-3 px-3">Target</th>
                  <th className="pb-3 px-3">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cyan-500/10">
                {data?.events && data.events.length > 0 ? (
                  data.events.map((event: AuditEventItem) => (
                    <Fragment key={event.event_id}>
                      <tr
                        className="hover:bg-cyan-500/5 transition-colors cursor-pointer"
                        onClick={() =>
                          setExpandedEventId(
                            expandedEventId === event.event_id ? null : event.event_id
                          )
                        }
                      >
                        <td className="py-3 px-3 text-sky-200/70">
                          {event.timestamp
                            ? new Date(event.timestamp)
                                .toISOString()
                                .replace("T", " ")
                                .slice(0, 19)
                            : "—"}
                        </td>
                        <td className="py-3 px-3 text-sky-400 font-bold">
                          {event.event_id.slice(0, 8)}...
                        </td>
                        <td className="py-3 px-3">
                          <Badge
                            variant={
                              event.event_type.includes("mitigation") ||
                              event.event_type.includes("disable")
                                ? "critical"
                                : event.event_type.includes("alert")
                                  ? "warning"
                                  : "info"
                            }
                          >
                            {event.event_type}
                          </Badge>
                        </td>
                        <td className="py-3 px-3 text-cyan-200">{event.actor}</td>
                        <td className="py-3 px-3 text-slate-300">
                          {event.target || "—"}
                        </td>
                        <td className="py-3 px-3 text-sky-300">
                          <span className="text-[11px] underline">
                            {expandedEventId === event.event_id ? "Hide JSON" : "View JSON"}
                          </span>
                        </td>
                      </tr>
                      {expandedEventId === event.event_id && (
                        <tr key={`${event.event_id}-details`} className="bg-slate-950/70">
                          <td colSpan={6} className="p-4">
                            <pre className="p-3 rounded-lg bg-black/60 border border-cyan-500/20 text-cyan-300 text-[11px] overflow-x-auto">
                              {JSON.stringify(event.details, null, 2)}
                            </pre>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-sky-200/40">
                      No audit events recorded.
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
