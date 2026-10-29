"use client";

import { useCallback, useState } from "react";
import { AlertDetailsModal } from "@/components/alerts/AlertDetailsModal";
import { AlertsTable } from "@/components/alerts/AlertsTable";
import { ExplainCard } from "@/components/common/ExplainCard";
import { MetricCard } from "@/components/common/MetricCard";
import { Badge, type BadgeVariant } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import {
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Search,
  Shield,
  Zap,
} from "@/components/ui/icons";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import {
  api,
  type AlertItem,
  type ThreatClassificationResult,
} from "@/lib/api";
import { formatISTTime } from "@/lib/formatters";
import { usePolling } from "@/lib/polling";

export default function DetectionPage() {
  const [windowSec, setWindowSec] = useState<number>(10);
  const [proposingRule, setProposingRule] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [searchIp, setSearchIp] = useState<string>("");
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);

  // Poll live threat assessment
  const fetchThreats = useCallback(
    () => api.getLiveThreatAssessment(windowSec),
    [windowSec]
  );
  const { data: threat, refresh: refreshThreat } = usePolling<ThreatClassificationResult>(
    fetchThreats,
    2500
  );

  // Poll persisted alerts
  const fetchAlerts = useCallback(() => {
    return api.getAlerts({
      limit: 50,
      severity: severityFilter === "all" ? undefined : severityFilter,
      target_ip: searchIp.trim() ? searchIp.trim() : undefined,
    });
  }, [severityFilter, searchIp]);

  const {
    data: alertsData,
    loading: alertsLoading,
    isStale,
    isDisconnected,
    lastUpdated,
    refresh: refreshAlerts,
  } = usePolling(fetchAlerts, 3000);

  const [isManualRefreshing, setIsManualRefreshing] = useState(false);

  const handleManualRefresh = async () => {
    setIsManualRefreshing(true);
    try {
      await Promise.all([refreshThreat(), refreshAlerts()]);
      setActionMessage("Detection data refreshed.");
      setTimeout(() => setActionMessage(null), 3000);
    } finally {
      setIsManualRefreshing(false);
    }
  };

  const alerts = alertsData?.alerts || [];

  const handleProposeDefense = async () => {
    if (!threat) return;

    // Use only verified candidate IPs from backend detection or recent alerts
    const candidateIp =
      (threat.candidate_target_ips && threat.candidate_target_ips.length > 0)
        ? threat.candidate_target_ips[0]
        : alerts.length > 0
        ? alerts[0].target_ip
        : null;

    if (!candidateIp) {
      setActionMessage("Cannot propose rule: No specific target IP identified by the detection engine.");
      setTimeout(() => setActionMessage(null), 4000);
      return;
    }

    setProposingRule(true);
    try {
      const isSingleSource = threat.threat_type === "SINGLE_SOURCE_FLOOD";
      await api.proposeDefensiveRule({
        target_ip_or_cidr: candidateIp,
        action_type: isSingleSource ? "BLOCK" : "RATE_LIMIT",
        rate_limit_rps: 10,
        burst_capacity: 20,
        ttl_seconds: 600,
        reason: `Generated from ${threat.threat_type}: ${threat.reasons?.[0] || "Anomaly detected"}`,
        dry_run: true,
      });
      setActionMessage(
        `Suggested defense rule created for ${candidateIp} in Safe Dry-Run mode. View in Attack Protection.`
      );
      setTimeout(() => setActionMessage(null), 4000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to propose rule";
      setActionMessage(`Error: ${msg}`);
    } finally {
      setProposingRule(false);
    }
  };

  const isThreat = Boolean(threat?.is_threat);
  const isFlashCrowd = Boolean(threat?.is_flash_crowd);
  const severity = threat?.severity ?? "INFO";
  const confidencePct =
    threat?.confidence !== undefined && threat?.confidence !== null
      ? Math.round(threat.confidence * 100)
      : null;

  const threatBadgeVariant: BadgeVariant = isFlashCrowd
    ? "cyan"
    : isThreat
    ? severity === "CRITICAL"
      ? "critical"
      : "warning"
    : "normal";

  const criticalCount = alerts.filter((a) => a.severity.toLowerCase() === "critical").length;
  const highCount = alerts.filter(
    (a) => a.severity.toLowerCase() === "high" || a.severity.toLowerCase() === "warning"
  ).length;

  const statusType = isDisconnected
    ? "disconnected"
    : isStale
    ? "stale"
    : alertsLoading
    ? "loading"
    : "online";

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-gray-800">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
              <AlertTriangle className="w-6 h-6 text-amber-400" />
              Attack Detection
            </h1>
            <Badge variant="cyan" className="font-sans text-xs">
              AI Inspection
            </Badge>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Review traffic that SENTRIX has identified as potentially harmful. Open any event to understand why it was flagged and whether it has been reviewed.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <StatusIndicator status={statusType} />
          {lastUpdated && (
            <span className="text-xs text-gray-400 font-mono">
              Last checked: {formatISTTime(lastUpdated)} IST
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleManualRefresh}
            disabled={isManualRefreshing}
            className="text-xs font-sans"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isManualRefreshing ? "animate-spin text-[#00FF9D]" : ""}`} />
            {isManualRefreshing ? "Refreshing..." : "Refresh"}
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
        title="How Attack Detection Works"
        summary="SENTRIX checks incoming traffic using two layers of protection: a trained Machine Learning model (Random Forest) and a Velocity Tracker (statistical surge detector). We differentiate harmless traffic rushes from harmful attacks:"
        tips={[
          "Harmless Traffic Surge (Flash Crowd): Many different real people visiting at once (e.g., viral news). We recommend keeping access open.",
          "Single-Source Flood: One computer or bot sending thousands of requests in seconds to overwhelm the system.",
          "Slow Connection Stalling (Slowloris): Keeping connections open very slowly to run the server out of memory.",
          "A flagged event is an estimate based on patterns, not an absolute guarantee. You have full control over defense rules.",
        ]}
        technicalDetails={
          <div className="space-y-1 text-[11px]">
            <p><strong className="text-gray-200">Statistical Engine:</strong> Exponentially Weighted Moving Average (EWMA) tracking mean and standard deviation.</p>
            <p><strong className="text-gray-200">Z-Score Trigger:</strong> Triggers when |Z| &gt;= 3.0 standard deviations from baseline with entropy ratio &lt; 0.35.</p>
            <p><strong className="text-gray-200">Flash Crowd Classification:</strong> Identified when RPS spikes but unique client entropy remains above 0.70 with low error rates.</p>
          </div>
        }
      />

      {/* Live Threat Banner */}
      <div
        className={`p-6 rounded-xl border transition-all ${
          isFlashCrowd
            ? "bg-[rgba(6,182,212,0.1)] border-[#06B6D4]/50 shadow-[0_0_24px_rgba(6,182,212,0.2)]"
            : isThreat
            ? severity === "CRITICAL"
              ? "bg-[rgba(255,0,85,0.12)] border-[#FF0055]/60 shadow-[0_0_30px_rgba(255,0,85,0.3)]"
              : "bg-[rgba(245,158,11,0.12)] border-amber-500/60 shadow-[0_0_20px_rgba(245,158,11,0.2)]"
            : "bg-[#111827]/80 border-gray-800"
        }`}
      >
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-xs uppercase tracking-wider text-gray-400">
                Current Live Assessment:
              </span>
              <Badge variant={threatBadgeVariant} className="text-sm px-3 py-1 font-bold">
                {isFlashCrowd
                  ? "Sudden Popular Traffic Surge (Harmless)"
                  : isThreat
                  ? threat?.threat_type || "Potential Attack"
                  : "All Traffic Normal"}
              </Badge>
              <Badge variant="outline" className="text-xs">
                Urgency: {severity}
              </Badge>
            </div>

            <h2 className="text-xl font-bold text-gray-100">
              {isFlashCrowd
                ? "Legitimate Viral Traffic Surge (Flash Crowd)"
                : isThreat
                ? `Suspicious Traffic Pattern Detected (${threat?.threat_type})`
                : "Normal Baseline Operation — All Signals Healthy"}
            </h2>

            <p className="text-sm text-gray-300">
              Recommended Action:{" "}
              <span className="text-[#00FF9D] font-bold">
                {isFlashCrowd ? "ALLOW (Keep open for genuine visitors)" : threat?.recommended_action ?? "ALLOW"}
              </span>
              {confidencePct !== null && (
                <span>{" — "}Confidence: {confidencePct}%</span>
              )}
            </p>
          </div>

          {/* Action Trigger */}
          {isThreat && (
            <Button
              variant="primary"
              onClick={handleProposeDefense}
              disabled={proposingRule}
              className="text-xs font-sans whitespace-nowrap"
            >
              <Shield className="w-4 h-4 mr-1.5" />
              Suggest Safe Defense Rule
            </Button>
          )}
        </div>
      </div>

      {/* Quick Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Incidents Recorded"
          value={alerts.length}
          subtitle="Events stored in audit database"
          icon={<AlertTriangle className="w-5 h-5 text-[#00FF9D]" />}
        />
        <MetricCard
          title="Critical Attacks"
          value={criticalCount}
          subtitle="High-impact flood or resource drain"
          icon={<AlertTriangle className="w-5 h-5 text-[#FF0055]" />}
          badge={<Badge variant={criticalCount > 0 ? "critical" : "normal"}>{criticalCount > 0 ? "Action Needed" : "Zero"}</Badge>}
        />
        <MetricCard
          title="Medium & Warning Events"
          value={highCount}
          subtitle="Unusual spikes or credential attempts"
          icon={<Zap className="w-5 h-5 text-amber-400" />}
        />
        <MetricCard
          title="Active Model Status"
          value="Random Forest"
          subtitle="14 CIC-DDoS2019 features active"
          icon={<Shield className="w-5 h-5 text-[#06B6D4]" />}
          badge={<Badge variant="matrix">Online</Badge>}
        />
      </div>

      {/* Filter and Search Bar */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <CardTitle>Flagged Events & Incident History</CardTitle>
            <CardDescription>
              Click any incident to inspect its features, reasons for flagging, and suggest mitigation.
            </CardDescription>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchIp}
                onChange={(e) => setSearchIp(e.target.value)}
                placeholder="Filter by IP address..."
                className="pl-9 pr-3 py-1.5 bg-[#1F2937]/70 border border-gray-700/60 rounded-lg text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-[#00FF9D]"
              />
            </div>

            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="px-3 py-1.5 bg-[#1F2937]/70 border border-gray-700/60 rounded-lg text-xs text-gray-200 focus:outline-none focus:border-[#00FF9D]"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical Only</option>
              <option value="warning">Warning / High</option>
              <option value="info">Info / Normal</option>
            </select>
          </div>
        </CardHeader>
        <CardContent>
          <AlertsTable
            alerts={alerts}
            onSelectAlert={(alert) => setSelectedAlert(alert)}
          />
        </CardContent>
      </Card>

      {/* Interactive Incident Details Modal */}
      <AlertDetailsModal
        alert={selectedAlert}
        onClose={() => setSelectedAlert(null)}
      />
    </div>
  );
}
