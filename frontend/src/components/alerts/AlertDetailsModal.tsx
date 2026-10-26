"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { CheckCircle2 } from "@/components/ui/icons";
import { api } from "@/lib/api";
import type { AlertItem } from "@/types";

interface AlertDetailsModalProps {
  alert: AlertItem | null;
  onClose: () => void;
}

export function AlertDetailsModal({ alert, onClose }: AlertDetailsModalProps) {
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simulationResult, setSimulationResult] = useState<string | null>(null);

  if (!alert) return null;

  const handleSimulateMitigation = async () => {
    setIsSimulating(true);
    setSimulationResult(null);

    try {
      const res = await api.simulateMitigation({
        target_ip: alert.target_ip || "192.168.1.150",
        action_type: "rate_limit",
        rate_limit_pps: 5000,
        duration_seconds: 60,
        reason: `Operator manual simulation for alert ${alert.alert_id}`,
      });
      setSimulationResult(
        `Action ${res.action_id} simulated successfully! Rate limited to ${res.rate_limit_pps} pps for ${res.duration_seconds}s (Host network remains untouched).`
      );
    } catch (err: unknown) {
      const msg = err && typeof err === "object" && "message" in err ? String(err.message) : "Safety gate error";
      setSimulationResult(`Simulation failed: ${msg}`);
    } finally {
      setIsSimulating(false);
    }
  };

  return (
    <Modal
      isOpen={!!alert}
      onClose={onClose}
      title="Simulate Mitigation Action"
      description={`Target: ${alert.target_ip || alert.source_id || "192.168.1.150"} (${alert.title || "Threat Alert"})`}
    >
      <div className="space-y-4 text-xs font-mono">
        <div className="p-3 rounded-lg bg-[#050b14] border border-cyan-500/20 space-y-2">
          <div className="flex justify-between">
            <span className="text-sky-300/60">Mitigation Mode:</span>
            <span className="text-cyan-300 font-bold">Simulation Only</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sky-300/60">Safety Gate:</span>
            <span className="text-emerald-400 font-bold">Enforced (Allowlists & Bounds)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sky-300/60">Proposed Rate Limit:</span>
            <span className="text-cyan-200">5,000 pps</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sky-300/60">Duration:</span>
            <span className="text-cyan-200">60 seconds (Auto-expiry)</span>
          </div>
        </div>

        <div className="p-3 rounded-lg bg-amber-950/20 border border-amber-900/30 text-amber-200/80">
          Note: Simulation records the defensive action in SQLite and evaluates guardrails, but modifies NO host firewall tables.
        </div>

        {simulationResult && (
          <div className="p-3 rounded-lg bg-cyan-950/30 border border-cyan-500/30 text-cyan-200 flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
            <span>{simulationResult}</span>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-3">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
          <Button
            variant="primary"
            size="sm"
            loading={isSimulating}
            onClick={handleSimulateMitigation}
          >
            Execute Simulation
          </Button>
        </div>
      </div>
    </Modal>
  );
}

