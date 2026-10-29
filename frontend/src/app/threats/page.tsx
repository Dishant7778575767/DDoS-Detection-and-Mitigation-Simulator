"use client";

import { useCallback, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Shield,
} from "@/components/ui/icons";
import { Badge, type BadgeVariant } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { api, type ThreatClassificationResult } from "@/lib/api";
import { usePolling } from "@/lib/polling";

export default function ThreatsPage() {
  const [windowSec, setWindowSec] = useState<number>(10);
  const [proposingRule, setProposingRule] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchThreats = useCallback(
    () => api.getLiveThreatAssessment(windowSec),
    [windowSec]
  );

  const { data: threat } = usePolling<ThreatClassificationResult>(
    fetchThreats,
    2500
  );

  const handleProposeDefense = async () => {
    if (!threat) return;
    setProposingRule(true);
    try {
      const isSingleSource = threat.threat_type === "SINGLE_SOURCE_FLOOD";
      const resolvedTarget =
        threat.candidate_target_ips && threat.candidate_target_ips.length > 0
          ? threat.candidate_target_ips[0]
          : isSingleSource
          ? "198.51.100.99"
          : "198.51.100.0/24";
      await api.proposeDefensiveRule({
        target_ip_or_cidr: resolvedTarget,
        action_type: isSingleSource ? "BLOCK" : "RATE_LIMIT",
        rate_limit_rps: 10,
        burst_capacity: 20,
        ttl_seconds: 600,
        reason: `Generated from ${threat.threat_type}: ${threat.reasons[0] || "Anomaly detected"}`,
        dry_run: true,
      });
      setActionMessage(`Defensive mitigation rule proposed for ${resolvedTarget} in Dry-Run mode. Review in Defense Shield.`);
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
  const confidencePct = Math.round((threat?.confidence ?? 0.95) * 100);

  const threatBadgeVariant: BadgeVariant = isFlashCrowd
    ? "cyan"
    : isThreat
    ? severity === "CRITICAL"
      ? "critical"
      : "warning"
    : "normal";

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold font-mono text-gray-100 flex items-center gap-2">
              <AlertTriangle className="w-6 h-6 text-amber-400" />
              Threat Detection & Velocity Center
            </h1>
            <Badge variant="cyan" className="font-mono text-xs">
              Milestone 2 Active
            </Badge>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Multi-tier detection funnel, statistical Z-score velocity shifts, and Flash-Crowd differentiation.
          </p>
        </div>

        {/* Window Selector */}
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-[#1F2937]/70 border border-gray-700/60 rounded-lg p-1 text-xs font-mono">
            <span className="px-2 text-gray-400">Analysis Window:</span>
            {[5, 10, 30].map((sec) => (
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
        </div>
      </div>

      {actionMessage && (
        <div className="p-3 bg-[#1F2937]/90 border border-[#00FF9D]/40 rounded-lg text-xs font-mono text-[#00FF9D] flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          {actionMessage}
        </div>
      )}

      {/* Primary Threat Banner */}
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
              <span className="text-xs font-mono uppercase tracking-wider text-gray-400">
                Current Threat Classification:
              </span>
              <Badge
                variant={threatBadgeVariant}
                className="font-mono text-sm px-3 py-1 font-bold"
              >
                {threat?.threat_type ?? "BENIGN"}
              </Badge>
              <Badge variant="outline" className="text-xs font-mono">
                Severity: {severity}
              </Badge>
            </div>

            <h2 className="text-xl font-bold font-mono text-gray-100">
              {isFlashCrowd
                ? "Legitimate Viral Traffic Surge (Flash Crowd)"
                : isThreat
                ? `Malicious Traffic Signature Detected (${threat?.threat_type})`
                : "Normal Baseline Operation — All Signals Healthy"}
            </h2>

            <p className="text-sm text-gray-300 font-mono">
              Recommended Action:{" "}
              <span className="text-[#00FF9D] font-bold">
                {threat?.recommended_action ?? "ALLOW"}
              </span>
              {" — "}
              Confidence: {confidencePct}%
            </p>
          </div>

          {/* Action Trigger */}
          {isThreat && (
            <Button
              variant="primary"
              onClick={handleProposeDefense}
              disabled={proposingRule}
              className="font-mono text-xs whitespace-nowrap"
            >
              <Shield className="w-4 h-4 mr-1.5" />
              Propose Staged Mitigation (Dry-Run)
            </Button>
          )}
        </div>
      </div>

      {/* Statistical Velocity Z-Scores Grid */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="font-mono">
              Statistical Velocity Z-Scores (Standard Deviations from EWMA Baseline)
            </CardTitle>
            <CardDescription>
              Values |Z| &gt;= 3.0 indicate extreme statistical anomaly velocity
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg text-center">
              <span className="text-xs font-mono text-gray-400 block">RPS Velocity (Z-RPS)</span>
              <span
                className={`text-2xl font-bold font-mono block mt-1 ${
                  Math.abs(threat?.z_scores?.z_rps ?? 0) >= 3.0
                    ? "text-[#FF0055]"
                    : Math.abs(threat?.z_scores?.z_rps ?? 0) >= 2.0
                    ? "text-amber-400"
                    : "text-[#00FF9D]"
                }`}
              >
                {threat?.z_scores?.z_rps ?? 0}σ
              </span>
            </div>

            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg text-center">
              <span className="text-xs font-mono text-gray-400 block">Error Velocity (Z-Err)</span>
              <span
                className={`text-2xl font-bold font-mono block mt-1 ${
                  Math.abs(threat?.z_scores?.z_error_rate ?? 0) >= 3.0
                    ? "text-[#FF0055]"
                    : "text-gray-200"
                }`}
              >
                {threat?.z_scores?.z_error_rate ?? 0}σ
              </span>
            </div>

            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg text-center">
              <span className="text-xs font-mono text-gray-400 block">Latency Shift (Z-Lat)</span>
              <span
                className={`text-2xl font-bold font-mono block mt-1 ${
                  Math.abs(threat?.z_scores?.z_p95_latency ?? 0) >= 3.0
                    ? "text-[#FF0055]"
                    : "text-gray-200"
                }`}
              >
                {threat?.z_scores?.z_p95_latency ?? 0}σ
              </span>
            </div>

            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg text-center">
              <span className="text-xs font-mono text-gray-400 block">Throughput Shift (Z-Bps)</span>
              <span className="text-2xl font-bold font-mono block mt-1 text-gray-200">
                {threat?.z_scores?.z_bytes_per_sec ?? 0}σ
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Decision Factors & Evidence */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="font-mono">Explainable Decision Evidence & Root Causes</CardTitle>
            <CardDescription>Mathematical trigger factors evaluated by detection tier</CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 font-mono text-xs text-gray-300">
            {(threat?.reasons ?? ["Telemetry is within calibrated statistical bounds."]).map(
              (reason, idx) => (
                <li
                  key={idx}
                  className="p-2.5 bg-[#111827]/70 border border-gray-800/80 rounded flex items-start gap-2.5"
                >
                  <span className="text-[#00FF9D] font-bold">›</span>
                  <span>{reason}</span>
                </li>
              )
            )}
          </ul>

          {threat?.targeted_endpoints && threat.targeted_endpoints.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-800/60">
              <span className="text-xs font-mono text-gray-400 block mb-2">
                Targeted URI Endpoints:
              </span>
              <div className="flex flex-wrap gap-2">
                {threat.targeted_endpoints.map((uri) => (
                  <span
                    key={uri}
                    className="px-2 py-1 bg-[#1F2937] border border-gray-700/60 rounded text-xs font-mono text-gray-200"
                  >
                    {uri}
                  </span>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
