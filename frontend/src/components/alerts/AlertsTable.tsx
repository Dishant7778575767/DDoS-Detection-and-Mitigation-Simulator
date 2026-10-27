"use client";

import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Shield, Terminal } from "@/components/ui/icons";
import type { AlertItem } from "@/types";

interface AlertsTableProps {
  alerts: AlertItem[];
  onSelectAlert?: (alert: AlertItem) => void;
}

export function AlertsTable({ alerts, onSelectAlert }: AlertsTableProps) {
  const router = useRouter();
  if (alerts.length === 0) {
    return (
      <div className="text-center py-12 text-xs text-[#9CA3AF] font-mono border border-dashed border-[rgba(75,85,99,0.3)] rounded-xl bg-[#090D16]/50">
        <Terminal className="w-8 h-8 text-[#00FF9D]/40 mx-auto mb-2" />
        <div>No active threat alerts.</div>
        <div className="text-[11px] text-[#9CA3AF]/60 mt-1">
          eBPF kernel probe is actively monitoring all ingress packets with normal flow distribution.
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-[rgba(75,85,99,0.3)] bg-[#090D16]/80 font-mono text-xs">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="border-b border-[rgba(75,85,99,0.3)] bg-[#1F2937]/50 text-[#9CA3AF] text-[11px] uppercase tracking-wider">
            <th className="py-3 px-3">Timestamp (IST)</th>
            <th className="py-3 px-3">Attack Type</th>
            <th className="py-3 px-3">Severity</th>
            <th className="py-3 px-3">Target IP</th>
            <th className="py-3 px-3">Detection Vector</th>
            <th className="py-3 px-3">Attack Status</th>
            <th className="py-3 px-3 text-right">Inspection</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[rgba(75,85,99,0.2)]">
          {alerts.map((alert) => {
            let formattedTime = "Just now";
            if (alert.timestamp) {
              try {
                const d = new Date(alert.timestamp);
                if (!isNaN(d.getTime())) {
                  formattedTime = new Intl.DateTimeFormat("sv-SE", {
                    timeZone: "Asia/Kolkata",
                    hour12: false,
                    year: "numeric",
                    month: "2-digit",
                    day: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  }).format(d);
                }
              } catch {
                formattedTime = alert.timestamp;
              }
            }

            const rawSev = (alert.severity || "low").toLowerCase();
            const isCritical = rawSev === "critical";
            const isHigh = rawSev === "high" || rawSev === "warning";
            const isMedium = rawSev === "medium";
            const displayLabel = isCritical
              ? "CRITICAL"
              : isHigh
              ? "HIGH"
              : isMedium
              ? "MEDIUM"
              : "LOW";
            const badgeVariant = isCritical
              ? "critical"
              : isHigh
              ? "warning"
              : isMedium
              ? "cyan"
              : "normal";

            return (
              <tr
                key={alert.alert_id}
                className="hover:bg-[#1F2937]/40 transition-colors group cursor-pointer"
                onClick={() => onSelectAlert?.(alert)}
              >
                {/* Timestamp */}
                <td className="py-3 px-3 text-[#9CA3AF] whitespace-nowrap">
                  {formattedTime}
                </td>

                {/* Threat */}
                <td className="py-3 px-3">
                  <div className="font-semibold text-gray-100 flex items-center gap-2">
                    <span className="text-[#00FF9D]">{alert.title || "Anomalous Traffic Spike"}</span>
                  </div>
                </td>

                {/* Severity */}
                <td className="py-3 px-3">
                  <Badge
                    variant={badgeVariant}
                    className="text-[10px] px-2 py-0.5"
                  >
                    {displayLabel}
                  </Badge>
                </td>

                {/* Target IP */}
                <td className="py-3 px-3 whitespace-nowrap">
                  <div className="text-gray-200">
                    {alert.target_ip || "192.168.1.150"}
                  </div>
                </td>

                {/* Detection Vector */}
                <td className="py-3 px-3 max-w-xs">
                  <div
                    className="truncate text-[#9CA3AF] text-[11px]"
                    title={alert.description || alert.title}
                  >
                    {alert.description ||
                      (alert.trigger_signal
                        ? alert.trigger_signal.replace(/_/g, " ")
                        : "Dual-signal ML + PPS limit exceeded")}
                  </div>
                </td>

                {/* Status */}
                <td className="py-3 px-3">
                  <Badge
                    variant={
                      alert.status === "active"
                        ? "warning"
                        : "normal"
                    }
                    className="text-[10px] uppercase font-mono font-bold"
                  >
                    {alert.status === "active" ? "ACTIVE" : "RESOLVED"}
                  </Badge>
                </td>

                {/* Action */}
                <td className="py-3 px-3 text-right whitespace-nowrap">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onSelectAlert) {
                        onSelectAlert(alert);
                      } else {
                        router.push("/alerts");
                      }
                    }}
                    className="text-xs"
                  >
                    <Shield className="w-3.5 h-3.5 text-[#00FF9D]" />
                    Inspect
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
