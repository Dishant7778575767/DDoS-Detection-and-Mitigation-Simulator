"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Shield } from "@/components/ui/icons";
import type { AlertItem } from "@/types";

interface AlertsTableProps {
  alerts: AlertItem[];
  onSelectAlert?: (alert: AlertItem) => void;
}

export function AlertsTable({ alerts, onSelectAlert }: AlertsTableProps) {
  if (alerts.length === 0) {
    return (
      <div className="text-center py-10 text-xs text-sky-200/40 font-mono">
        No threat alerts found matching criteria. System running normal traffic monitoring.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs font-mono">
        <thead>
          <tr className="border-b border-cyan-500/15 text-sky-300/60 uppercase tracking-wider">
            <th className="pb-3 px-3">Timestamp (UTC)</th>
            <th className="pb-3 px-3">Alert & Details</th>
            <th className="pb-3 px-3">Severity</th>
            <th className="pb-3 px-3">Source / Target</th>
            <th className="pb-3 px-3">Detection Context</th>
            <th className="pb-3 px-3">Status</th>
            <th className="pb-3 px-3">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-cyan-500/10">
          {alerts.map((alert) => {
            const formattedTime = alert.timestamp
              ? new Date(alert.timestamp).toISOString().replace("T", " ").slice(0, 19)
              : "Just now";

            return (
              <tr key={alert.alert_id} className="hover:bg-cyan-500/5 transition-colors">
                <td className="py-3 px-3 text-sky-200/70 whitespace-nowrap">
                  {formattedTime}
                </td>
                <td className="py-3 px-3">
                  <div className="font-semibold text-cyan-200">
                    {alert.title || alert.classification || "Threat Alert"}
                  </div>
                  <div className="text-[11px] text-sky-400/50">{alert.alert_id}</div>
                </td>
                <td className="py-3 px-3">
                  <Badge
                    variant={
                      alert.severity === "critical"
                        ? "critical"
                        : alert.severity === "warning" || alert.severity === "high"
                          ? "warning"
                          : "info"
                    }
                  >
                    {alert.severity || "warning"}
                  </Badge>
                </td>
                <td className="py-3 px-3 font-mono text-cyan-300">
                  {alert.target_ip || alert.source_id || "sensor-01"}
                </td>
                <td className="py-3 px-3 max-w-xs">
                  <div
                    className="truncate text-slate-300"
                    title={alert.description || alert.title}
                  >
                    {alert.description ||
                      (alert.trigger_signal
                        ? alert.trigger_signal.replace(/_/g, " ")
                        : "Dual-signal anomaly detected")}
                  </div>
                </td>
                <td className="py-3 px-3">
                  <Badge
                    variant={
                      alert.status === "active"
                        ? "warning"
                        : alert.status === "resolved" || alert.status === "mitigated"
                          ? "normal"
                          : "outline"
                    }
                  >
                    {alert.status || "active"}
                  </Badge>
                </td>
                <td className="py-3 px-3 whitespace-nowrap">
                  {onSelectAlert ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onSelectAlert(alert)}
                    >
                      <Shield className="w-3.5 h-3.5 text-cyan-400" />
                      Simulate
                    </Button>
                  ) : (
                    <span className="text-sky-300/40 text-[11px]">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

