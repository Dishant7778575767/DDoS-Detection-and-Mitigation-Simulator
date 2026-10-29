"use client";

import { useRouter } from "next/navigation";
import { Badge, type BadgeVariant } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Pagination } from "@/components/ui/Pagination";
import { Shield, Terminal } from "@/components/ui/icons";
import { usePagination } from "@/hooks/usePagination";
import { formatISTDateTime } from "@/lib/formatters";
import type { AlertItem } from "@/types";

interface AlertsTableProps {
  alerts: AlertItem[];
  onSelectAlert?: (alert: AlertItem) => void;
}

export function AlertsTable({ alerts, onSelectAlert }: AlertsTableProps) {
  const router = useRouter();

  const {
    currentPage,
    pageSize,
    totalPages,
    totalItems,
    paginatedItems: paginatedAlerts,
    setPage,
    setPageSize,
  } = usePagination(alerts, 10);

  if (alerts.length === 0) {
    return (
      <div className="text-center py-12 text-xs text-gray-400 font-mono border border-dashed border-gray-700/60 rounded-xl bg-[#090D16]/60">
        <Terminal className="w-8 h-8 text-[#00FF9D]/40 mx-auto mb-2" aria-hidden="true" />
        <div className="text-gray-300 font-semibold">No matching threat alerts.</div>
        <div className="text-[11px] text-gray-500 mt-1">
          No matching alert records were returned by the SENTRIX API.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-xl border border-gray-700/60 bg-[#090D16]/80 font-mono text-xs">
      <table className="w-full text-left border-collapse" aria-label="Security Threat Incidents">
        <thead>
          <tr className="border-b border-gray-800 bg-[#1F2937]/50 text-gray-400 text-[11px] uppercase tracking-wider">
            <th scope="col" className="py-3 px-3">Timestamp (IST)</th>
            <th scope="col" className="py-3 px-3">Attack Type</th>
            <th scope="col" className="py-3 px-3">Severity</th>
            <th scope="col" className="py-3 px-3">Target IP</th>
            <th scope="col" className="py-3 px-3">Detection Vector</th>
            <th scope="col" className="py-3 px-3">Attack Status</th>
            <th scope="col" className="py-3 px-3 text-right">Inspection</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/80">
          {paginatedAlerts.map((alert) => {
            const formattedTime = formatISTDateTime(alert.timestamp);
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

            const badgeVariant: BadgeVariant = isCritical
              ? "critical"
              : isHigh
              ? "warning"
              : isMedium
              ? "cyan"
              : "normal";

            return (
              <tr
                key={alert.alert_id}
                tabIndex={0}
                role="button"
                aria-label={`Inspect alert: ${alert.title || "Anomalous Traffic Spike"}`}
                className="hover:bg-[#1F2937]/50 focus-visible:bg-[#1F2937]/60 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#00FF9D] transition-colors group cursor-pointer"
                onClick={() => onSelectAlert?.(alert)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelectAlert?.(alert);
                  }
                }}
              >
                {/* Timestamp */}
                <td className="py-3 px-3 text-gray-400 whitespace-nowrap">
                  {formattedTime}
                </td>

                {/* Threat */}
                <td className="py-3 px-3">
                  <div className="font-semibold text-gray-100 flex items-center gap-2">
                    <span className="text-[#00FF9D] group-hover:underline">
                      {alert.title || "Anomalous Traffic Spike"}
                    </span>
                  </div>
                </td>

                {/* Severity */}
                <td className="py-3 px-3">
                  <Badge variant={badgeVariant} className="text-[10px] px-2 py-0.5">
                    {displayLabel}
                  </Badge>
                </td>

                {/* Target IP */}
                <td className="py-3 px-3 whitespace-nowrap">
                  <span className="text-gray-300 font-mono">
                    {alert.target_ip || "Not recorded"}
                  </span>
                </td>

                {/* Detection Vector */}
                <td className="py-3 px-3 max-w-xs">
                  <div
                    className="truncate text-gray-400 text-[11px]"
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
                    variant={alert.status === "active" ? "warning" : "normal"}
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
                    aria-label={`Inspect details for ${alert.title || "alert"}`}
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
  );
}
