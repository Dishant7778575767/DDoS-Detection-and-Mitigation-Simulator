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
import { MetricCard } from "@/components/common/MetricCard";
import { api, type LiveTelemetrySummary } from "@/lib/api";
import { usePolling } from "@/lib/polling";

export default function TelemetryPage() {
  const [windowSec, setWindowSec] = useState<number>(10);
  const [isResetting, setIsResetting] = useState(false);
  const [isInjecting, setIsInjecting] = useState(false);
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
      setActionMessage("Telemetry sliding-window buffer reset successfully.");
      await refresh();
      setTimeout(() => setActionMessage(null), 3500);
    } catch {
      setActionMessage("Failed to reset buffer.");
    } finally {
      setIsResetting(false);
    }
  };

  const handleInjectSample = async () => {
    setIsInjecting(true);
    try {
      const now = new Date().toISOString();
      const sampleLogs = [
        `198.51.100.22 - - [${now}] "GET /api/v1/products HTTP/1.1" 200 1450 "-" "Mozilla/5.0" 0.015`,
        `198.51.100.23 - - [${now}] "GET /api/v1/cart HTTP/1.1" 200 420 "-" "Mozilla/5.0" 0.022`,
        `198.51.100.24 - - [${now}] "POST /api/v1/checkout HTTP/1.1" 200 890 "-" "Mozilla/5.0" 0.045`,
        `198.51.100.99 - - [${now}] "POST /api/v1/auth/login HTTP/1.1" 401 120 "-" "curl/7.68" 0.005`,
        `198.51.100.99 - - [${now}] "POST /api/v1/auth/login HTTP/1.1" 401 120 "-" "curl/7.68" 0.005`,
        `198.51.100.30 - - [${now}] "GET /api/v1/search?q=ddos HTTP/1.1" 200 2340 "-" "Mozilla/5.0" 0.035`,
      ];
      await api.ingestTelemetry({ raw_logs: sampleLogs, anonymize_ips: true });
      setActionMessage("Injected 6 sample L7 HTTP requests into ingestion pipeline.");
      await refresh();
      setTimeout(() => setActionMessage(null), 3500);
    } catch {
      setActionMessage("Failed to inject sample telemetry.");
    } finally {
      setIsInjecting(false);
    }
  };

  const rps = telemetry?.requests_per_second ?? 0;
  const kbps = Math.round(((telemetry?.bytes_per_second ?? 0) / 1024) * 10) / 10;
  const errorRate = telemetry?.status_codes?.error_rate_pct ?? 0;
  const entropyRatio = telemetry?.client_metrics?.entropy_ratio ?? 0;
  const uniqueClients = telemetry?.client_metrics?.unique_clients ?? 0;
  const totalRequests = telemetry?.total_requests ?? 0;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold font-mono text-gray-100 flex items-center gap-2">
              <Server className="w-6 h-6 text-[#00FF9D]" />
              Live Telemetry Stream
            </h1>
            <Badge variant="cyan" className="font-mono text-xs">
              Milestone 1 Active
            </Badge>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Real-time HTTP ingress monitoring, statistical latency percentiles, and Shannon Entropy analytics.
          </p>
        </div>

        {/* Window Selector & Actions */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center bg-[#1F2937]/70 border border-gray-700/60 rounded-lg p-1 text-xs font-mono">
            <span className="px-2 text-gray-400">Window:</span>
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
            variant="outline"
            onClick={handleInjectSample}
            disabled={isInjecting}
            className="text-xs"
          >
            <Zap className="w-3.5 h-3.5 mr-1 text-[#06B6D4]" />
            Inject Sample
          </Button>

          <Button
            size="sm"
            variant="danger"
            onClick={handleReset}
            disabled={isResetting}
            className="text-xs"
          >
            <RotateCcw className="w-3.5 h-3.5 mr-1" />
            Reset Window
          </Button>
        </div>
      </div>

      {actionMessage && (
        <div className="p-3 bg-[#1F2937]/90 border border-[#00FF9D]/40 rounded-lg text-xs font-mono text-[#00FF9D] flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          {actionMessage}
        </div>
      )}

      {/* Primary KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Requests / Second"
          value={rps}
          unit="RPS"
          subtitle={`Over ${windowSec}s sliding window`}
          icon={<Activity className="w-5 h-5 text-[#00FF9D]" />}
          badge={
            <Badge variant={rps > 500 ? "critical" : rps > 100 ? "warning" : "matrix"}>
              {rps > 500 ? "Spike" : "Normal"}
            </Badge>
          }
        />
        <MetricCard
          title="Throughput"
          value={`${kbps}`}
          unit="KB/s"
          subtitle={`${telemetry?.bytes_per_second?.toLocaleString() ?? 0} Bps`}
          icon={<Server className="w-5 h-5 text-[#06B6D4]" />}
        />
        <MetricCard
          title="Error Rate"
          value={`${errorRate}`}
          unit="%"
          subtitle={`${(telemetry?.status_codes?.c_4xx ?? 0) + (telemetry?.status_codes?.c_5xx ?? 0)} failed / ${totalRequests}`}
          icon={<AlertTriangle className="w-5 h-5 text-amber-400" />}
          badge={
            <Badge variant={errorRate > 25 ? "critical" : errorRate > 10 ? "warning" : "normal"}>
              {errorRate > 25 ? "Critical" : "Healthy"}
            </Badge>
          }
        />
        <MetricCard
          title="Shannon Entropy"
          value={`${entropyRatio}`}
          subtitle={`${uniqueClients} unique client IPs (${telemetry?.client_metrics?.shannon_entropy ?? 0} bits)`}
          icon={<Zap className="w-5 h-5 text-[#00FF9D]" />}
          badge={
            <Badge variant={entropyRatio < 0.35 && totalRequests > 15 ? "critical" : "cyan"}>
              {entropyRatio < 0.35 && totalRequests > 15 ? "Low Diversity" : "Distributed"}
            </Badge>
          }
        />
      </div>

      {/* Latency Percentiles Grid */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="font-mono">Latency Percentiles (ms)</CardTitle>
            <CardDescription>Calculated over active window via numpy.percentile</CardDescription>
          </div>
          <Badge variant="outline">Distribution</Badge>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 text-center">
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-[11px] font-mono text-gray-400 block">Min</span>
              <span className="text-lg font-bold font-mono text-gray-200">
                {telemetry?.latencies?.min_ms ?? 0}ms
              </span>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-[11px] font-mono text-gray-400 block">P50 (Median)</span>
              <span className="text-lg font-bold font-mono text-[#06B6D4]">
                {telemetry?.latencies?.p50_ms ?? 0}ms
              </span>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-[11px] font-mono text-gray-400 block">Average</span>
              <span className="text-lg font-bold font-mono text-gray-200">
                {telemetry?.latencies?.avg_ms ?? 0}ms
              </span>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-[11px] font-mono text-gray-400 block">P90</span>
              <span className="text-lg font-bold font-mono text-gray-200">
                {telemetry?.latencies?.p90_ms ?? 0}ms
              </span>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-[11px] font-mono text-gray-400 block">P95 (SLA)</span>
              <span className={`text-lg font-bold font-mono ${(telemetry?.latencies?.p95_ms ?? 0) > 1500 ? "text-[#FF0055]" : "text-[#00FF9D]"}`}>
                {telemetry?.latencies?.p95_ms ?? 0}ms
              </span>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-[11px] font-mono text-gray-400 block">P99 (Tail)</span>
              <span className="text-lg font-bold font-mono text-amber-400">
                {telemetry?.latencies?.p99_ms ?? 0}ms
              </span>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-[11px] font-mono text-gray-400 block">Max</span>
              <span className="text-lg font-bold font-mono text-gray-300">
                {telemetry?.latencies?.max_ms ?? 0}ms
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
              <CardTitle className="font-mono">HTTP Status Code Breakdown</CardTitle>
              <CardDescription>Relative distribution of responses</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-xs font-mono mb-1">
                  <span className="text-[#00FF9D]">2xx Success: {telemetry?.status_codes?.c_2xx ?? 0}</span>
                  <span className="text-gray-400">{telemetry?.status_codes?.pct_2xx ?? 0}%</span>
                </div>
                <div className="h-2 w-full bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#00FF9D]"
                    style={{ width: `${Math.min(100, telemetry?.status_codes?.pct_2xx ?? 0)}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono mb-1">
                  <span className="text-[#06B6D4]">3xx Redirects: {telemetry?.status_codes?.c_3xx ?? 0}</span>
                  <span className="text-gray-400">{telemetry?.status_codes?.pct_3xx ?? 0}%</span>
                </div>
                <div className="h-2 w-full bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#06B6D4]"
                    style={{ width: `${Math.min(100, telemetry?.status_codes?.pct_3xx ?? 0)}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono mb-1">
                  <span className="text-amber-400">4xx Client Errors: {telemetry?.status_codes?.c_4xx ?? 0}</span>
                  <span className="text-gray-400">{telemetry?.status_codes?.pct_4xx ?? 0}%</span>
                </div>
                <div className="h-2 w-full bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-amber-400"
                    style={{ width: `${Math.min(100, telemetry?.status_codes?.pct_4xx ?? 0)}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono mb-1">
                  <span className="text-[#FF0055]">5xx Server Faults: {telemetry?.status_codes?.c_5xx ?? 0}</span>
                  <span className="text-gray-400">{telemetry?.status_codes?.pct_5xx ?? 0}%</span>
                </div>
                <div className="h-2 w-full bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#FF0055]"
                    style={{ width: `${Math.min(100, telemetry?.status_codes?.pct_5xx ?? 0)}%` }}
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Top Endpoints Table */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle className="font-mono">Frequently Requested Endpoints</CardTitle>
              <CardDescription>Top targets in active telemetry window</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {(!telemetry?.top_uris || telemetry.top_uris.length === 0) ? (
              <p className="text-sm font-mono text-gray-500 py-6 text-center">
                No recent requests in active sliding window.
              </p>
            ) : (
              <div className="divide-y divide-gray-800/60 font-mono text-xs">
                {telemetry.top_uris.map((uriItem) => (
                  <div key={uriItem.uri} className="py-2.5 flex items-center justify-between">
                    <span className="text-gray-200 truncate max-w-[280px]">
                      {uriItem.uri}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="text-gray-400">{uriItem.count} req</span>
                      <Badge variant="outline" className="text-[10px]">
                        {uriItem.pct}%
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Client Sources Table */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle className="font-mono">Top Client Traffic Sources</CardTitle>
              <CardDescription>Highest volume client IP addresses and subnet origins</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {(!telemetry?.top_clients || telemetry.top_clients.length === 0) ? (
              <p className="text-sm font-mono text-gray-500 py-6 text-center">
                No client IP activity recorded in active sliding window.
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 font-mono text-xs">
                {telemetry.top_clients.map((clientItem) => (
                  <div key={clientItem.client_ip} className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg flex items-center justify-between">
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
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
