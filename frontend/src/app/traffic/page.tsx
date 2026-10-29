"use client";

import { useCallback, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  RotateCcw,
  Server,
  Zap,
} from "@/components/ui/icons";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { ExplainCard } from "@/components/common/ExplainCard";
import { MetricCard } from "@/components/common/MetricCard";
import { Pagination } from "@/components/ui/Pagination";
import { usePagination } from "@/hooks/usePagination";
import { api, type LiveTelemetrySummary } from "@/lib/api";
import { usePolling } from "@/lib/polling";

export default function TrafficPage() {
  const [windowSec, setWindowSec] = useState<number>(10);
  const [isResetting, setIsResetting] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchTelemetry = useCallback(
    () => api.getLiveTelemetry(windowSec),
    [windowSec]
  );

  const { data: telemetry, refresh } = usePolling<LiveTelemetrySummary>(
    fetchTelemetry,
    2000
  );

  const handleReset = async () => {
    setIsResetting(true);
    try {
      await api.resetTelemetry();
      setActionMessage("Live traffic measurement window has been reset.");
      await refresh();
      setTimeout(() => setActionMessage(null), 3500);
    } catch {
      setActionMessage("Failed to reset traffic measurement window.");
    } finally {
      setIsResetting(false);
    }
  };

  const totalRequests = telemetry?.total_requests ?? 0;
  const hasData = totalRequests > 0;
  const rps = telemetry?.requests_per_second ?? 0;
  const kbps = Math.round(((telemetry?.bytes_per_second ?? 0) / 1024) * 10) / 10;
  const errorRate = telemetry?.status_codes?.error_rate_pct ?? 0;
  const entropyRatio = telemetry?.client_metrics?.entropy_ratio ?? 0;
  const uniqueClients = telemetry?.client_metrics?.unique_clients ?? 0;

  const {
    currentPage: urisPage,
    pageSize: urisPageSize,
    totalPages: urisTotalPages,
    totalItems: urisTotalItems,
    paginatedItems: paginatedUris,
    setPage: setUrisPage,
    setPageSize: setUrisPageSize,
  } = usePagination(telemetry?.top_uris || [], 5);

  const {
    currentPage: clientsPage,
    pageSize: clientsPageSize,
    totalPages: clientsTotalPages,
    totalItems: clientsTotalItems,
    paginatedItems: paginatedClients,
    setPage: setClientsPage,
    setPageSize: setClientsPageSize,
  } = usePagination(telemetry?.top_clients || [], 6);

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-gray-800">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
              <Server className="w-6 h-6 text-[#00FF9D]" />
              Live Traffic
            </h1>
            <Badge variant="cyan" className="font-sans text-xs">
              Live Stream
            </Badge>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            See how much traffic is reaching your system and how it changes over time. Unusual increases may need investigation, but a traffic increase does not always mean an attack.
          </p>
        </div>

        {/* Window Selector & Actions */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center bg-[#1F2937]/70 border border-gray-700/60 rounded-lg p-1 text-xs">
            <span className="px-2 text-gray-400">Measurement Window:</span>
            {[5, 10, 30, 60].map((sec) => (
              <button
                key={sec}
                type="button"
                onClick={() => setWindowSec(sec)}
                className={`px-2.5 py-1 rounded transition-colors ${
                  windowSec === sec
                    ? "bg-[#00FF9D]/20 text-[#00FF9D] font-bold"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                {sec}s
              </button>
            ))}
          </div>

          <Button
            size="sm"
            variant="danger"
            onClick={handleReset}
            disabled={isResetting}
            className="text-xs font-sans"
          >
            <RotateCcw className="w-3.5 h-3.5 mr-1" />
            Clear Current Window
          </Button>
        </div>
      </div>

      {actionMessage && (
        <div className="p-3 bg-[#1F2937]/90 border border-[#00FF9D]/40 rounded-lg text-xs text-[#00FF9D] flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          {actionMessage}
        </div>
      )}

      {/* Plain English Explanation Card */}
      <ExplainCard
        title="Understanding Live Traffic Numbers"
        summary="This page monitors how many people or programs are visiting your application in real time. We look at four main signs to detect problems:"
        tips={[
          "Requests Per Second: The current speed of incoming visits.",
          "Data Flow Rate: The volume of information transferred per second.",
          "Error Percentage: How many requests encountered an issue (normal is below 5%).",
          "Visitor Variety: When many different IP addresses visit, it is usually legitimate people. When all requests come from one single source, it may be a flood.",
        ]}
        technicalDetails={
          <div className="space-y-1 text-[11px]">
            <p><strong className="text-gray-200">Sliding Window:</strong> In-memory deque pruned to last {windowSec} seconds using precise event timestamps.</p>
            <p><strong className="text-gray-200">Shannon Entropy Formula:</strong> H(X) = -sum(p(x) * log2(p(x))). Entropy ratio normalized against log2(N).</p>
            <p><strong className="text-gray-200">Latency Method:</strong> Derived from CloudFront time-to-first-byte duration percentiles via numpy.</p>
          </div>
        }
      />

      {/* Primary KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Requests Per Second"
          value={hasData ? rps : 0}
          unit="req/sec"
          subtitle={hasData ? `Calculated over the last ${windowSec} seconds` : `No requests in last ${windowSec}s`}
          icon={<Activity className="w-5 h-5 text-[#00FF9D]" />}
          badge={
            <Badge variant={!hasData ? "outline" : rps > 500 ? "critical" : rps > 100 ? "warning" : "matrix"}>
              {!hasData ? "Idle" : rps > 500 ? "High Surge" : rps > 100 ? "Elevated" : "Normal"}
            </Badge>
          }
        />
        <MetricCard
          title="Data Flow Rate"
          value={hasData ? `${kbps}` : "0"}
          unit="KB/sec"
          subtitle={hasData ? `${telemetry?.bytes_per_second?.toLocaleString() ?? 0} bytes/sec` : "0 bytes transferred"}
          icon={<Server className="w-5 h-5 text-[#06B6D4]" />}
        />
        <MetricCard
          title="Failed Requests"
          value={hasData ? `${errorRate}` : "0"}
          unit="%"
          subtitle={
            hasData
              ? `${(telemetry?.status_codes?.c_4xx ?? 0) + (telemetry?.status_codes?.c_5xx ?? 0)} failed out of ${totalRequests}`
              : "No failed requests"
          }
          icon={<AlertTriangle className="w-5 h-5 text-amber-400" />}
          badge={
            <Badge variant={!hasData ? "outline" : errorRate > 25 ? "critical" : errorRate > 10 ? "warning" : "normal"}>
              {!hasData ? "Normal" : errorRate > 25 ? "Needs Attention" : "Healthy"}
            </Badge>
          }
        />
        <MetricCard
          title="Visitor Variety"
          value={
            !hasData
              ? "Waiting for Data"
              : entropyRatio >= 0.7
              ? "High Variety"
              : entropyRatio >= 0.35
              ? "Moderate"
              : "Low Variety"
          }
          subtitle={
            hasData
              ? `${uniqueClients} unique client addresses (${entropyRatio} variety score)`
              : "No active clients"
          }
          icon={<Zap className="w-5 h-5 text-[#00FF9D]" />}
          badge={
            <Badge variant={!hasData ? "outline" : entropyRatio < 0.35 && totalRequests > 15 ? "critical" : "cyan"}>
              {!hasData ? "Standby" : entropyRatio < 0.35 && totalRequests > 15 ? "Single Source" : "Healthy Mix"}
            </Badge>
          }
        />
      </div>

      {/* Response Times Grid */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Response Times (How fast pages load)</CardTitle>
            <CardDescription>
              Response time in milliseconds (ms). 100ms is one-tenth of a second.
            </CardDescription>
          </div>
          <Badge variant="outline">Speed Analysis</Badge>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 text-center">
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-[11px] text-gray-400 block">Fastest (Min)</span>
              <span className="text-lg font-bold font-mono text-gray-200">
                {hasData ? `${telemetry?.latencies?.min_ms ?? 0}ms` : "—"}
              </span>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-[11px] text-gray-400 block">Typical Visitor (Median)</span>
              <span className="text-lg font-bold font-mono text-[#06B6D4]">
                {hasData ? `${telemetry?.latencies?.p50_ms ?? 0}ms` : "—"}
              </span>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-[11px] text-gray-400 block">Average</span>
              <span className="text-lg font-bold font-mono text-gray-200">
                {hasData ? `${telemetry?.latencies?.avg_ms ?? 0}ms` : "—"}
              </span>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-[11px] text-gray-400 block">Slower 10% (P90)</span>
              <span className="text-lg font-bold font-mono text-gray-200">
                {hasData ? `${telemetry?.latencies?.p90_ms ?? 0}ms` : "—"}
              </span>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-[11px] text-gray-400 block">Slower 5% (P95)</span>
              <span
                className={`text-lg font-bold font-mono ${
                  hasData && (telemetry?.latencies?.p95_ms ?? 0) > 1500 ? "text-[#FF0055]" : "text-[#00FF9D]"
                }`}
              >
                {hasData ? `${telemetry?.latencies?.p95_ms ?? 0}ms` : "—"}
              </span>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-[11px] text-gray-400 block">Slowest 1% (P99)</span>
              <span className="text-lg font-bold font-mono text-amber-400">
                {hasData ? `${telemetry?.latencies?.p99_ms ?? 0}ms` : "—"}
              </span>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-[11px] text-gray-400 block">Slowest Single (Max)</span>
              <span className="text-lg font-bold font-mono text-gray-300">
                {hasData ? `${telemetry?.latencies?.max_ms ?? 0}ms` : "—"}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Status Codes & Top URIs Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Status Codes Distribution */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Request Outcomes (HTTP Status)</CardTitle>
              <CardDescription>How the web server answered incoming visitors</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {!hasData ? (
              <p className="text-sm text-gray-500 py-6 text-center">
                Waiting for incoming traffic. No web requests recorded in the current {windowSec}s window.
              </p>
            ) : (
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-[#00FF9D] font-medium">Successful (2xx): {telemetry?.status_codes?.c_2xx ?? 0}</span>
                    <span className="text-gray-400 font-mono">{telemetry?.status_codes?.pct_2xx ?? 0}%</span>
                  </div>
                  <div className="h-2 w-full bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[#00FF9D]"
                      style={{ width: `${Math.min(100, telemetry?.status_codes?.pct_2xx ?? 0)}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-[#06B6D4] font-medium">Redirected (3xx): {telemetry?.status_codes?.c_3xx ?? 0}</span>
                    <span className="text-gray-400 font-mono">{telemetry?.status_codes?.pct_3xx ?? 0}%</span>
                  </div>
                  <div className="h-2 w-full bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[#06B6D4]"
                      style={{ width: `${Math.min(100, telemetry?.status_codes?.pct_3xx ?? 0)}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-amber-400 font-medium">Client Errors (4xx Not Found / Unauthorized): {telemetry?.status_codes?.c_4xx ?? 0}</span>
                    <span className="text-gray-400 font-mono">{telemetry?.status_codes?.pct_4xx ?? 0}%</span>
                  </div>
                  <div className="h-2 w-full bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-amber-400"
                      style={{ width: `${Math.min(100, telemetry?.status_codes?.pct_4xx ?? 0)}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-[#FF0055] font-medium">Server Errors (5xx System Failures): {telemetry?.status_codes?.c_5xx ?? 0}</span>
                    <span className="text-gray-400 font-mono">{telemetry?.status_codes?.pct_5xx ?? 0}%</span>
                  </div>
                  <div className="h-2 w-full bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[#FF0055]"
                      style={{ width: `${Math.min(100, telemetry?.status_codes?.pct_5xx ?? 0)}%` }}
                    />
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Endpoints Table */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Most Visited Pages & Endpoints</CardTitle>
              <CardDescription>Which pages are receiving the highest number of requests</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {(!telemetry?.top_uris || telemetry.top_uris.length === 0) ? (
              <p className="text-sm text-gray-500 py-6 text-center">
                No active endpoints visited in current window.
              </p>
            ) : (
              <div className="space-y-3">
                <div className="divide-y divide-gray-800/60 text-xs">
                  {paginatedUris.map((uriItem) => (
                    <div key={uriItem.uri} className="py-2.5 flex items-center justify-between font-mono">
                      <span className="text-gray-200 truncate max-w-[280px]">
                        {uriItem.uri}
                      </span>
                      <div className="flex items-center gap-3">
                        <span className="text-gray-400">{uriItem.count} requests</span>
                        <Badge variant="outline" className="text-[10px]">
                          {uriItem.pct}%
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
                <Pagination
                  currentPage={urisPage}
                  totalPages={urisTotalPages}
                  pageSize={urisPageSize}
                  totalItems={urisTotalItems}
                  onPageChange={setUrisPage}
                  onPageSizeChange={setUrisPageSize}
                  pageSizeOptions={[5, 10, 20]}
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Client Sources Table */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Top Visitor Sources</CardTitle>
              <CardDescription>Client addresses sending the most requests right now</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {(!telemetry?.top_clients || telemetry.top_clients.length === 0) ? (
              <p className="text-sm text-gray-500 py-6 text-center">
                No visitor activity in the current measurement window.
              </p>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
                  {paginatedClients.map((clientItem) => (
                    <div
                      key={clientItem.client_ip}
                      className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg flex items-center justify-between font-mono"
                    >
                      <span className="text-[#06B6D4] font-semibold truncate max-w-[180px]">
                        {clientItem.client_ip}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-gray-400">{clientItem.count} req</span>
                        <Badge variant="outline" className="text-[10px]">
                          {clientItem.pct}%
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
                <Pagination
                  currentPage={clientsPage}
                  totalPages={clientsTotalPages}
                  pageSize={clientsPageSize}
                  totalItems={clientsTotalItems}
                  onPageChange={setClientsPage}
                  onPageSizeChange={setClientsPageSize}
                  pageSizeOptions={[6, 12, 24]}
                />
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
