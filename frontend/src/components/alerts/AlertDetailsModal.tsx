"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import {
  AlertTriangle,
  CheckCircle2,
  Lock,
  Shield,
} from "@/components/ui/icons";
import { api } from "@/lib/api";
import type { AlertItem } from "@/types";

interface AlertDetailsModalProps {
  alert: AlertItem | null;
  onClose: () => void;
}

export function AlertDetailsModal({ alert, onClose }: AlertDetailsModalProps) {
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simulationResult, setSimulationResult] = useState<string | null>(null);
  const [simulationError, setSimulationError] = useState<string | null>(null);

  if (!alert) return null;

  const rawSev = (alert.severity || "medium").toLowerCase();
  const isCritical = rawSev === "critical";
  const isHigh = rawSev === "high";
  const isMedium = rawSev === "medium" || rawSev === "warning";

  // Friendly threat explanation for non-tech / recruiter
  let threatExplanation = "Anomalous traffic spike detected. The AI brain observed traffic patterns exceeding safety thresholds.";
  let actionSuggestion = "Monitor connection rates and apply rate limiting if traffic worsens.";

  if (alert.title?.includes("SYN")) {
    threatExplanation = "Fake connection spam attack (SYN Flood). Attackers are opening millions of half-open TCP requests to exhaust memory.";
    actionSuggestion = "Block malicious IP & enforce TCP SYN Cookies.";
  } else if (alert.title?.includes("UDP")) {
    threatExplanation = "High-bandwidth pipe clogging attack (UDP Flood). Random packets are saturating the network pipeline.";
    actionSuggestion = "Drop unverified UDP packets at the ingress gateway.";
  } else if (alert.title?.includes("HTTP")) {
    threatExplanation = "Website overload attack (HTTP Flood). A swarm of bots is spamming heavy web pages to crash the server.";
    actionSuggestion = "Trigger challenge / rate limiting on repetitive GET requests.";
  } else if (alert.title?.includes("Slow")) {
    threatExplanation = "Stealth slow connection attack (Slowloris). Tiny data fragments are sent very slowly to hold connection sockets open silently.";
    actionSuggestion = "Terminate long-hanging connections with short keep-alive timeouts.";
  }

  // Sanitize target IP: strip ports/whitespace/trailing dots
  let targetIp = (alert.target_ip || "").trim().replace(/\.+$/, "");
  if (targetIp.includes(":")) {
    targetIp = targetIp.split(":")[0];
  }

  const isLoopbackOrProtected =
    targetIp === "127.0.0.1" ||
    targetIp === "localhost" ||
    targetIp === "192.168.1.1" ||
    targetIp === "10.0.0.1" ||
    targetIp.startsWith("127.");

  const isIpPattern = /^(\d{1,3}\.){3}\d{1,3}$/.test(targetIp);
  const effectiveIp =
    !isIpPattern || isLoopbackOrProtected ? "192.168.1.100" : targetIp;

  const handleSimulateMitigation = async () => {
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
        `Action verified! Rate limited to ${res.rate_limit_pps.toLocaleString()} PPS for ${res.duration_seconds}s on ${effectiveIp} (Safely executed in simulation mode with 0 downtime).`
      );
    } catch (err: unknown) {
      const msg = err && typeof err === "object" && "message" in err ? String(err.message) : "Safety Gate rejected request.";
      setSimulationError(msg);
    } finally {
      setIsSimulating(false);
    }
  };

  return (
    <Modal
      isOpen={!!alert}
      onClose={onClose}
      title="Threat Investigation & Defense Action"
      description={`Target Server: ${alert.target_ip || "Under Inspection"}`}
    >
      <div className="space-y-4 text-xs font-mono">
        {/* Simple Threat Summary Card */}
        <div className="p-3.5 rounded-xl bg-[#090D16] border border-[rgba(75,85,99,0.4)] space-y-2">
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
                {alert.severity.toUpperCase()}
              </Badge>
            </div>
          </div>
          <p className="text-[11px] text-[#9CA3AF] font-sans leading-relaxed">
            {threatExplanation}
          </p>
        </div>

        {/* What AI Found & Recommended Action */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 font-sans">
          <div className="p-3 rounded-lg bg-[#090D16] border border-[rgba(75,85,99,0.3)] space-y-1">
            <span className="text-[10px] font-mono text-[#06B6D4] font-bold block uppercase tracking-wider">
              Target Being Attacked:
            </span>
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-gray-200 font-bold font-mono text-xs">{effectiveIp}</span>
              {isLoopbackOrProtected && (
                <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 font-mono">
                  Virtual Node
                </span>
              )}
            </div>
            <span className="text-[10px] text-[#9CA3AF] block font-mono">
              Status: {alert.status === "active" ? "ACTIVE" : "RESOLVED"}
            </span>
          </div>

          <div className="p-3 rounded-lg bg-[#090D16] border border-[rgba(75,85,99,0.3)] space-y-1">
            <span className="text-[10px] font-mono text-[#00FF9D] font-bold block uppercase tracking-wider">
              Recommended Fix:
            </span>
            <p className="text-[11px] text-gray-300 leading-tight">
              {actionSuggestion}
            </p>
          </div>
        </div>

        {/* Safety Gate Guardrails Box */}
        <div className="p-3 rounded-lg bg-[#090D16] border border-[rgba(75,85,99,0.3)] space-y-2">
          <div className="text-[11px] font-bold text-gray-200 flex items-center justify-between border-b border-[rgba(75,85,99,0.3)] pb-1.5">
            <span className="flex items-center gap-1.5 font-mono">
              <Lock className="w-3.5 h-3.5 text-[#00FF9D]" />
              Automated Defense Shield Settings
            </span>
            <span className="text-[10px] text-[#00FF9D] font-mono">SAFE TEST MODE</span>
          </div>
          <div className="flex justify-between text-gray-300">
            <span className="text-[#9CA3AF]">Protective Action:</span>
            <span className="text-[#06B6D4] font-bold">Smart Rate-Limiting</span>
          </div>
          <div className="flex justify-between text-gray-300">
            <span className="text-[#9CA3AF]">AI Detection Engine:</span>
            <span>Random Forest AI</span>
          </div>
          <div className="flex justify-between text-gray-300">
            <span className="text-[#9CA3AF]">Target Safe Node:</span>
            <span className="text-gray-200 font-mono">{effectiveIp}</span>
          </div>
          <div className="flex justify-between text-gray-300">
            <span className="text-[#9CA3AF]">Allowed Safe Speed:</span>
            <span className="text-[#00FF9D] font-bold">5,000 PPS</span>
          </div>
          <div className="flex justify-between text-gray-300">
            <span className="text-[#9CA3AF]">Rule Expiry:</span>
            <span>60 seconds auto-reset</span>
          </div>
        </div>

        {/* Success Feedback */}
        {simulationResult && (
          <div className="p-3 rounded-lg bg-[rgba(0,255,157,0.1)] border border-[#00FF9D]/40 text-[#00FF9D] flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 text-[#00FF9D] shrink-0 mt-0.5" />
            <span className="leading-relaxed font-sans">{simulationResult}</span>
          </div>
        )}

        {/* Safety Gate Error Feedback */}
        {simulationError && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/40 text-rose-300 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <div className="font-sans leading-relaxed">
              <div className="font-bold text-xs">Safety Gate Blocked Request:</div>
              <div className="text-[11px] text-rose-200 mt-0.5">{simulationError}</div>
            </div>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-3 border-t border-[rgba(75,85,99,0.3)]">
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
          <Button
            variant="primary"
            size="sm"
            loading={isSimulating}
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
