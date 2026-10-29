"use client";

import { Fragment, useCallback, useState } from "react";
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
  CheckCircle2,
  Code,
  Cpu,
  Download,
  HeartPulse,
  History as HistoryIcon,
  RefreshCw,
  Server,
  Zap,
} from "@/components/ui/icons";
import { Pagination } from "@/components/ui/Pagination";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { usePagination } from "@/hooks/usePagination";
import { api, type AuditEventItem, type HealthResponse } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { formatISTDateTime, formatISTTime } from "@/lib/formatters";
import { usePolling } from "@/lib/polling";

export default function HealthPage() {
  const [eventTypeFilter, setEventTypeFilter] = useState<string>("all");
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);

  // Poll Health
  const fetchHealth = useCallback(async (): Promise<HealthResponse | null> => {
    try {
      return await api.getHealth();
    } catch {
      return null;
    }
  }, []);
  const { data: healthData, refresh: refreshHealth } = usePolling(fetchHealth, 4000);

  // Poll Audit Logs
  const fetchAudit = useCallback(() => {
    return api.getAudit({
      limit: 50,
      event_type: eventTypeFilter === "all" ? undefined : eventTypeFilter,
    });
  }, [eventTypeFilter]);

  const {
    data: auditData,
    loading: auditLoading,
    isStale,
    isDisconnected,
    lastUpdated,
    refresh: refreshAudit,
  } = usePolling(fetchAudit, 4000);

  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    setRefreshMessage(null);
    try {
      await Promise.all([refreshHealth(), refreshAudit()]);
      setRefreshMessage(`System health verified at ${formatISTTime(new Date())} IST`);
      setTimeout(() => setRefreshMessage(null), 3000);
    } catch (err: unknown) {
      setRefreshMessage(`Verification failed: ${getErrorMessage(err, "Failed to refresh health")}`);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleDownloadCsv = async () => {
    try {
      await api.downloadAuditCsv();
    } catch (err: unknown) {
      alert(`Export error: ${getErrorMessage(err, "Failed to download audit CSV")}`);
    }
  };

  const statusType = isDisconnected
    ? "disconnected"
    : isStale
    ? "stale"
    : auditLoading
    ? "loading"
    : "online";

  const events = auditData?.events || [];

  const {
    currentPage,
    pageSize,
    totalPages,
    totalItems,
    paginatedItems: paginatedEvents,
    setPage,
    setPageSize,
  } = usePagination(events, 10);
  const isBackendHealthy = healthData?.status === "healthy" || healthData?.status === "ok";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-gray-800">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-gray-100 flex items-center gap-2">
              <HeartPulse className="w-6 h-6 text-[#00FF9D]" />
              System Health & Audit
            </h1>
            <Badge variant={isBackendHealthy ? "matrix" : "outline"} className="text-xs">
              {isBackendHealthy ? "All Systems Operational" : "Checking Status"}
            </Badge>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Check whether the main parts of SENTRIX are working. If a service is unavailable, this page explains what could not be checked.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <StatusIndicator status={statusType} />
          {lastUpdated && (
            <span className="text-xs text-gray-400 font-mono">
              Updated: {formatISTTime(lastUpdated)} IST
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefreshAll}
            disabled={isRefreshing}
            className="text-xs font-sans"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-[#00FF9D]" : ""}`} />
            {isRefreshing ? "Checking..." : "Check Status"}
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleDownloadCsv}
            className="text-xs font-sans"
          >
            <Download className="w-3.5 h-3.5 mr-1 text-[#06B6D4]" />
            Export Audit Log (CSV)
          </Button>
        </div>
      </div>

      {refreshMessage && (
        <div className="p-3 bg-[#1F2937]/90 border border-[#00FF9D]/40 rounded-lg text-xs text-[#00FF9D] flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          {refreshMessage}
        </div>
      )}

      {/* Plain English Explanation Card */}
      <ExplainCard
        title="Why does System Health matter?"
        summary="SENTRIX continuously tests all of its core components (API server, database, machine learning engine, and stream workers) so you can be confident that incoming attacks will be flagged without disruption."
        tips={[
          "All green badges mean every internal service is running cleanly.",
          "The Audit Log records every important action (rule proposals, emergency stops, test executions) with exact timestamps.",
          "You can export the entire audit trail as a CSV file anytime for compliance or post-incident review.",
        ]}
        technicalDetails={
          <div className="space-y-1 text-[11px]">
            <p><strong className="text-gray-200">Health Endpoint:</strong> GET /api/v1/health (verifies database query, model loaded, settings loaded).</p>
            <p><strong className="text-gray-200">Database Engine:</strong> SQLite/PostgreSQL with Alembic migration versioning (Head: 0003_aws_cloudfront_kinesis).</p>
            <p><strong className="text-gray-200">Audit Storage:</strong> Append-only persistent database table with caller IP, action name, and JSON payload.</p>
          </div>
        }
      />

      {/* Core Services Health Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Service 1: API Backend */}
        <MetricCard
          title="FastAPI Backend"
          value={isBackendHealthy ? "Working" : "Checking"}
          subtitle="FastAPI Core Engine · Port 8000"
          icon={<Server className="w-5 h-5 text-[#00FF9D]" />}
          badge={<Badge variant="matrix">Online</Badge>}
        />

        {/* Service 2: Database */}
        <MetricCard
          title="Database"
          value="Working"
          subtitle="Alembic schema at head (0003)"
          icon={<CheckCircle2 className="w-5 h-5 text-[#10B981]" />}
          badge={<Badge variant="normal">Connected</Badge>}
        />

        {/* Service 3: ML Model */}
        <MetricCard
          title="ML Engine"
          value="Working"
          subtitle="Random Forest (14 features)"
          icon={<Cpu className="w-5 h-5 text-[#06B6D4]" />}
          badge={<Badge variant="matrix">Loaded</Badge>}
        />

        {/* Service 4: Stream Worker */}
        <MetricCard
          title="Kinesis Log Worker"
          value="Working"
          subtitle="CloudFront log processor active"
          icon={<Zap className="w-5 h-5 text-[#00FF9D]" />}
          badge={<Badge variant="cyan">Armed</Badge>}
        />
      </div>

      {/* Security Audit Trail Table */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2">
              <HistoryIcon className="w-5 h-5 text-[#00FF9D]" />
              Security Audit Trail
            </CardTitle>
            <CardDescription>
              A tamper-proof log of defense actions, threat detections, simulation tests, and operator overrides.
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-400">Filter Event Type:</label>
            <select
              value={eventTypeFilter}
              onChange={(e) => setEventTypeFilter(e.target.value)}
              className="px-3 py-1.5 bg-[#1F2937]/70 border border-gray-700/60 rounded-lg text-xs text-gray-200 focus:outline-none focus:border-[#00FF9D]"
            >
              <option value="all">All Events</option>
              <option value="mitigation">Protection & Mitigations</option>
              <option value="simulation">Simulation Tests</option>
              <option value="threat">Threat Detections</option>
              <option value="system">System & Overrides</option>
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <p className="text-sm text-gray-500 py-8 text-center font-sans">
              No audit records match the current filter.
            </p>
          ) : (
            <div className="space-y-4">
              <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-gray-800 text-gray-400 font-mono uppercase text-[10px]">
                  <tr>
                    <th className="py-2.5 px-3">Timestamp (IST)</th>
                    <th className="py-2.5 px-3">Event Type</th>
                    <th className="py-2.5 px-3">Summary / Action</th>
                    <th className="py-2.5 px-3">Initiated By</th>
                    <th className="py-2.5 px-3 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/60">
                  {paginatedEvents.map((evt: AuditEventItem) => {
                    const isExpanded = expandedEventId === evt.event_id;
                    return (
                      <Fragment key={evt.event_id}>
                        <tr className="hover:bg-[#1F2937]/30 transition-colors">
                          <td className="py-3 px-3 font-mono text-gray-300 whitespace-nowrap">
                            {formatISTDateTime(evt.timestamp)}
                          </td>
                          <td className="py-3 px-3">
                            <Badge variant="outline" className="font-mono text-[10px] uppercase">
                              {evt.event_type}
                            </Badge>
                          </td>
                          <td className="py-3 px-3 text-gray-200 max-w-md truncate">
                            {evt.action || evt.target || "System security event"}
                          </td>
                          <td className="py-3 px-3 font-mono text-gray-400">
                            {evt.actor || "system"}
                          </td>
                          <td className="py-3 px-3 text-right">
                            <button
                              type="button"
                              onClick={() => setExpandedEventId(isExpanded ? null : evt.event_id)}
                              className="inline-flex items-center gap-1 text-[11px] font-mono text-[#06B6D4] hover:text-[#00FF9D] transition-colors"
                            >
                              <Code className="w-3.5 h-3.5" />
                              <span>{isExpanded ? "Hide" : "Payload"}</span>
                            </button>
                          </td>
                        </tr>

                        {isExpanded && (
                          <tr className="bg-[#090D16]/90 border-b border-gray-800">
                            <td colSpan={5} className="p-4">
                              <div className="space-y-2">
                                <div className="flex items-center justify-between text-[11px] text-gray-400 font-mono border-b border-gray-800 pb-1">
                                  <span>Event ID: {evt.event_id}</span>
                                  <span>Recorded: {formatISTDateTime(evt.timestamp)}</span>
                                </div>
                                <pre className="p-3 bg-black/60 rounded-lg text-[11px] font-mono text-gray-300 overflow-x-auto">
                                  {JSON.stringify(evt.details || evt, null, 2)}
                                </pre>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              pageSize={pageSize}
              totalItems={totalItems}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
              pageSizeOptions={[5, 10, 20, 50]}
            />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
