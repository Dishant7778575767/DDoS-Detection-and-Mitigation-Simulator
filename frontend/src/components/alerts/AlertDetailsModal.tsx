"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { AlertTriangle, CheckCircle2, Lock, Shield } from "@/components/ui/icons";
import { Modal } from "@/components/ui/Modal";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import type { AlertItem } from "@/types";

interface AlertDetailsModalProps {
  alert: AlertItem | null;
  onClose: () => void;
}

export function AlertDetailsModal({ alert, onClose }: AlertDetailsModalProps) {
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationResult, setSimulationResult] = useState<string | null>(null);
  const [simulationError, setSimulationError] = useState<string | null>(null);

  if (!alert) return null;

  const rawSev = (alert.severity || "low").toLowerCase();
  const isCritical = rawSev === "critical";
  const isHigh = rawSev === "high" || rawSev === "warning";
  const isMedium = rawSev === "medium";

  // Threat explanation based on genuine alert metadata
  let threatExplanation =
    alert.description ||
    "Anomalous traffic spike detected. The AI brain observed traffic patterns exceeding safety thresholds.";
  let actionSuggestion = "Monitor connection rates and apply rate limiting if traffic worsens.";

  if (alert.title?.includes("SYN")) {
    threatExplanation =
      "SYN Flood pattern detected: high rate of connection attempts without completing the TCP handshake.";
    actionSuggestion = "Enforce TCP SYN rate limiting and verify client handshake authenticity.";
  } else if (alert.title?.includes("UDP")) {
    threatExplanation =
      "UDP Flood pattern detected: high-volume stateless packet flood saturating bandwidth.";
    actionSuggestion = "Apply bandwidth rate limits and drop unverified UDP packets at the perimeter.";
  } else if (alert.title?.includes("HTTP")) {
    threatExplanation =
      "HTTP Flood pattern detected: excessive application-layer requests aimed at exhausting web workers.";
    actionSuggestion = "Apply rate limiting or challenge rules on targeted endpoints.";
  } else if (alert.title?.includes("Slow")) {
    threatExplanation =
      "Slow connection exhaustion (Slowloris) pattern detected: sockets held open with minimal byte rates.";
    actionSuggestion = "Reduce keep-alive timeouts and enforce minimum transfer speed thresholds.";
  }

  // Clean actual target IP
  const effectiveIp = alert.target_ip ? alert.target_ip.trim().replace(/\.+$/, "") : "";
  const hasValidIp = effectiveIp.length > 0;

  const handleSimulateMitigation = async () => {
    if (!hasValidIp) {
      setSimulationError("Cannot trigger mitigation: no target address recorded for this event.");
      return;
    }

    setIsSimulating(true);
    setSimulationResult(null);
    setSimulationError(null);

    try {
      const res = await api.simulateMitigation({
        target_ip: effectiveIp,
        action_type: "rate_limit",
        rate_limit_pps: 5000,
        duration_seconds: 60,
        reason: `Operator manual simulation for alert ${alert.alert_id}`,
      });
      setSimulationResult(
        `Action verified! Rate limited to ${res.rate_limit_pps.toLocaleString()} req/sec for ${res.duration_seconds}s on ${effectiveIp} (Safely executed in simulation mode with 0 downtime).`
      );
    } catch (err: unknown) {
      setSimulationError(getErrorMessage(err, "Safety Gate rejected request."));
    } finally {
      setIsSimulating(false);
    }
  };

  return (
    <Modal
      isOpen={!!alert}
      onClose={onClose}
      title="Threat Investigation & Defense Action"
      description={`Target: ${hasValidIp ? effectiveIp : "Unspecified target"}`}
      variant={isCritical ? "danger" : "info"}
    >
      <div className="space-y-4 text-xs font-mono">
        {/* Simple Threat Summary Card */}
        <div className="p-3.5 rounded-xl bg-[#090D16] border border-gray-700/60 space-y-2">
          <div className="flex items-center justify-between gap-3">
            <span className="text-gray-100 font-bold text-sm truncate">
              {alert.title || "Traffic Anomaly"}
            </span>

            <div className="flex flex-col items-end gap-1 shrink-0">
              <Badge
                variant={
                  isCritical
                    ? "critical"
                    : isHigh
                    ? "warning"
                    : isMedium
                    ? "cyan"
                    : "normal"
                }
                className="text-[10px] font-bold uppercase"
              >
                {rawSev === "warning" ? "HIGH" : rawSev.toUpperCase()}
              </Badge>
            </div>
          </div>
          <p className="text-[11px] text-gray-400 font-sans leading-relaxed">
            {threatExplanation}
          </p>
        </div>

        {/* Target & Action Summary */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 font-sans">
          <div className="p-3 rounded-lg bg-[#090D16] border border-gray-700/50 space-y-1">
            <span className="text-[10px] font-mono text-[#06B6D4] font-bold block uppercase tracking-wider">
              Target Being Attacked:
            </span>
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-gray-200 font-bold font-mono text-xs">
                {hasValidIp ? effectiveIp : "None specified"}
              </span>
            </div>
            <span className="text-[10px] text-gray-400 block font-mono">
              Status: {alert.status === "active" ? "ACTIVE" : "RESOLVED"}
            </span>
          </div>

          <div className="p-3 rounded-lg bg-[#090D16] border border-gray-700/50 space-y-1">
            <span className="text-[10px] font-mono text-[#00FF9D] font-bold block uppercase tracking-wider">
              Recommended Action:
            </span>
            <p className="text-[11px] text-gray-300 leading-tight">
              {actionSuggestion}
            </p>
          </div>
        </div>

        {/* Safety Gate Guardrails Box */}
        <div className="p-3 rounded-lg bg-[#090D16] border border-gray-700/50 space-y-2">
          <div className="text-[11px] font-bold text-gray-200 flex items-center justify-between border-b border-gray-800 pb-1.5">
            <span className="flex items-center gap-1.5 font-mono">
              <Lock className="w-3.5 h-3.5 text-[#00FF9D]" />
              Automated Defense Shield Settings
            </span>
            <span className="text-[10px] text-[#00FF9D] font-mono">SAFE TEST MODE</span>
          </div>
          <div className="flex justify-between text-gray-300">
            <span className="text-gray-400">Protective Action:</span>
            <span className="text-[#06B6D4] font-bold">Smart Rate-Limiting</span>
          </div>
          <div className="flex justify-between text-gray-300">
            <span className="text-gray-400">Detection Engine:</span>
            <span>Random Forest Model</span>
          </div>
          <div className="flex justify-between text-gray-300">
            <span className="text-gray-400">Target Address:</span>
            <span className="text-gray-200 font-mono">{hasValidIp ? effectiveIp : "N/A"}</span>
          </div>
          <div className="flex justify-between text-gray-300">
            <span className="text-gray-400">Allowed Rate:</span>
            <span className="text-[#00FF9D] font-bold">5,000 req/sec</span>
          </div>
          <div className="flex justify-between text-gray-300">
            <span className="text-gray-400">Rule Expiry:</span>
            <span>60 seconds auto-reset</span>
          </div>
        </div>

        {/* Success Feedback */}
        {simulationResult && (
          <div className="p-3 rounded-lg bg-[rgba(0,255,157,0.12)] border border-[#00FF9D]/40 text-[#00FF9D] flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 text-[#00FF9D] shrink-0 mt-0.5" />
            <span className="leading-relaxed font-sans">{simulationResult}</span>
          </div>
        )}

        {/* Safety Gate Error Feedback */}
        {simulationError && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/40 text-rose-300 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <div className="font-sans leading-relaxed">
              <div className="font-bold text-xs">Action Rejected:</div>
              <div className="text-[11px] text-rose-200 mt-0.5">{simulationError}</div>
            </div>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-3 border-t border-gray-800">
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
          <Button
            variant="primary"
            size="sm"
            loading={isSimulating}
            disabled={!hasValidIp}
            onClick={handleSimulateMitigation}
          >
            <Shield className="w-3.5 h-3.5" />
            Trigger Shield Protection
          </Button>
        </div>
      </div>
    </Modal>
  );
}
