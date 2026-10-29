"use client";

import { useCallback, useEffect, useState } from "react";
import { ExplainCard } from "@/components/common/ExplainCard";
import { DefensiveRulesCard } from "@/components/mitigation/DefensiveRulesCard";
import { Badge } from "@/components/ui/Badge";
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
  Power,
  RefreshCw,
  Server,
  Shield,
  XCircle,
} from "@/components/ui/icons";
import { Modal } from "@/components/ui/Modal";
import { Pagination } from "@/components/ui/Pagination";
import { usePagination } from "@/hooks/usePagination";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { api, type MitigationItem } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { formatISTTime } from "@/lib/formatters";
import { usePolling } from "@/lib/polling";

interface MitigationStatusData {
  emergency_disabled: boolean;
  mode?: string;
  shield_active?: boolean;
  active_simulated_count?: number;
  max_concurrent_limit?: number;
  status?: string;
  host_ip?: string;
  hostname?: string;
  is_deployed?: boolean;
  environment?: string;
  dns_gateways?: string[];
  protected_gateways?: string[];
  rate_limit_bounds?: {
    min_pps: number;
    max_pps: number;
  };
  duration_bounds?: {
    min_seconds: number;
    max_seconds: number;
  };
  cooldown_ticks?: number;
}

interface PolledMitigationData {
  mitigations: MitigationItem[];
  status: MitigationStatusData | null;
}

export default function ProtectionPage() {
  const [isDisableModalOpen, setIsDisableModalOpen] = useState<boolean>(false);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [localStatusOverride, setLocalStatusOverride] = useState<MitigationStatusData | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const fetchMitigations = useCallback(async (): Promise<PolledMitigationData> => {
    const [statusRes, mitRes] = await Promise.allSettled([
      api.getMitigationStatus(),
      api.getMitigations({ limit: 50 }),
    ]);

    return {
      status: statusRes.status === "fulfilled" ? statusRes.value : null,
      mitigations: mitRes.status === "fulfilled" ? mitRes.value.mitigations || [] : [],
    };
  }, []);

  const { data, loading, error, isStale, isDisconnected, lastUpdated, refresh } =
    usePolling<PolledMitigationData>(fetchMitigations, 3000);

  const mitigationStatus = localStatusOverride ?? data?.status ?? null;
  const isEmergencyActive = Boolean(mitigationStatus?.emergency_disabled);

  useEffect(() => {
    const handleShieldUpdate = () => {
      setLocalStatusOverride(null);
      void refresh();
    };
    window.addEventListener("sentrix:shield_update", handleShieldUpdate);
    return () => window.removeEventListener("sentrix:shield_update", handleShieldUpdate);
  }, [refresh]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    setActionMessage(null);
    try {
      setLocalStatusOverride(null);
      await refresh();
      setActionMessage(`Protection state & rules refreshed at ${formatISTTime(new Date())} IST`);
      setTimeout(() => setActionMessage(null), 3000);
    } catch (err: unknown) {
      setActionMessage(`Refresh failed: ${getErrorMessage(err, "Failed to refresh")}`);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleCancel = async (actionId: string) => {
    setCancellingId(actionId);
    setActionMessage(null);
    try {
      await api.cancelMitigation(actionId);
      setActionMessage(`Protection rule ${actionId.slice(0, 8)}... cancelled.`);
      await refresh();
    } catch (err: unknown) {
      setActionMessage(`Failed to cancel: ${getErrorMessage(err, "Unknown error")}`);
    } finally {
      setCancellingId(null);
    }
  };

  const handleEmergencyDisable = async () => {
    setActionMessage(null);
    try {
      const res = await api.emergencyDisable(false);
      if (mitigationStatus) {
        setLocalStatusOverride({ ...mitigationStatus, emergency_disabled: true });
      }
      setActionMessage(
        res.emergency_disabled
          ? "EMERGENCY SAFETY STOP ACTIVATED: All automatic mitigation rules paused."
          : "Emergency stop toggled."
      );
      setIsDisableModalOpen(false);
      await refresh();
    } catch (err: unknown) {
      setActionMessage(`Emergency disable failed: ${getErrorMessage(err, "Unknown error")}`);
    }
  };

  const handleReenableSafetyGate = async () => {
    setActionMessage(null);
    try {
      await api.emergencyDisable(true);
      if (mitigationStatus) {
        setLocalStatusOverride({ ...mitigationStatus, emergency_disabled: false });
      }
      setActionMessage("Defense Engine restored to active protection!");
      await refresh();
    } catch (err: unknown) {
      setActionMessage(`Failed to restore defense engine: ${getErrorMessage(err, "Unknown error")}`);
    }
  };

  const statusType = isDisconnected
    ? "disconnected"
    : isStale
    ? "stale"
    : loading
    ? "loading"
    : "online";

  const allMitigations = data?.mitigations || [];
  const filteredMitigations =
    statusFilter === "all"
      ? allMitigations
      : allMitigations.filter((m) => (m.status || m.state) === statusFilter);

  const {
    currentPage: mitPage,
    pageSize: mitPageSize,
    paginatedItems: paginatedMitigations,
    setCurrentPage: setMitPage,
    setPageSize: setMitPageSize,
  } = usePagination(filteredMitigations, 10);

  const activeCount = allMitigations.filter((m) => {
    const s = m.status || m.state;
    return s === "active" || s === "simulated";
  }).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-gray-800">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-100 flex items-center gap-3">
            <Shield className="w-6 h-6 text-[#00FF9D]" />
            Attack Protection
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Review actions intended to reduce harmful traffic. Check whether an action was suggested, simulated, or actually applied. These are different outcomes.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <StatusIndicator status={statusType} />
          {lastUpdated && (
            <span className="text-xs text-gray-400 font-mono">
              Updated: {formatISTTime(lastUpdated)} IST
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="text-xs font-sans"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-[#00FF9D]" : ""}`} />
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </Button>

          {isEmergencyActive ? (
            <Button
              variant="primary"
              size="sm"
              onClick={handleReenableSafetyGate}
              title="Clear lockout and restore defense engine"
              className="bg-emerald-600 hover:bg-emerald-500 text-white font-sans text-xs"
            >
              <Power className="w-4 h-4 mr-1" />
              Re-enable Defense Engine
            </Button>
          ) : (
            <Button
              variant="danger"
              size="sm"
              onClick={() => setIsDisableModalOpen(true)}
              title="Pause all defenses"
              className="text-xs font-sans"
            >
              <Power className="w-4 h-4 mr-1" />
              Emergency Pause All Defenses
            </Button>
          )}
        </div>
      </div>

      {/* Emergency Active Alert Banner */}
      {isEmergencyActive && (
        <div className="p-4 rounded-xl border border-rose-500/50 bg-rose-500/15 text-rose-200 flex flex-wrap items-center justify-between gap-4 shadow-xl">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-rose-500/20 border border-rose-500/40 text-rose-400">
              <Power className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-rose-100 uppercase tracking-wider">
                Emergency Pause Active
              </h4>
              <p className="text-xs text-rose-300">
                All automatic & manual protection rules are temporarily paused. Real traffic is flowing without restrictions.
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleReenableSafetyGate}
            className="border-rose-400 text-rose-200 hover:bg-rose-500/20 font-sans shrink-0"
          >
            Re-enable Defenses Now
          </Button>
        </div>
      )}

      {/* Action Notification */}
      {actionMessage && (
        <div className="p-3.5 rounded-xl bg-[#090D16] border border-[#00FF9D]/40 text-[#00FF9D] text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-[#00FF9D] shrink-0" />
          <span>{actionMessage}</span>
        </div>
      )}

      {/* Plain English Explanation Card */}
      <ExplainCard
        title="Understanding Defense Actions & Outcomes"
        summary="SENTRIX separates defense actions into three clear stages so that you never accidentally block real visitors:"
        tips={[
          "Suggested Rule (Dry-Run): The model noticed suspicious traffic and created a draft rule. It monitors traffic without blocking anyone.",
          "Simulated Protection: Safe test mode. It calculates how many requests would be filtered without touching any real visitor.",
          "Applied Protection: An active firewall rule that actually blocks or limits requests from malicious IPs.",
        ]}
        technicalDetails={
          <div className="space-y-1 text-[11px]">
            <p><strong className="text-gray-200">Enforcement Engine:</strong> In-process Token Bucket rate limiter with configurable burst capacity.</p>
            <p><strong className="text-gray-200">Rule Exporters:</strong> Can generate native AWS WAFv2 JSON ACLs, Nginx limit_req_zone snippets, and Caddy rate_limit directives.</p>
            <p><strong className="text-gray-200">Safety Bounds:</strong> 50 to 50,000 PPS rate limits, maximum duration 3,600s with automatic rollback on timer expiry.</p>
          </div>
        }
      />

      {/* Protected Server Guardrails Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="mb-2 pb-2">
            <CardTitle className="text-xs uppercase tracking-wider text-gray-400">
              Protected Server Address
            </CardTitle>
            <Server className="w-4 h-4 text-[#10B981]" />
          </CardHeader>
          <CardContent className="text-xs space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Server IP:</span>
              <div className="flex items-center gap-1.5">
                <span className="text-[#10B981] font-bold font-mono">
                  {mitigationStatus?.host_ip || (loading ? "Checking..." : "Unassigned")}
                </span>
                <Badge
                  variant={mitigationStatus?.is_deployed ? "matrix" : "outline"}
                  className="text-[10px] py-0 px-1.5"
                >
                  {mitigationStatus?.is_deployed ? "Deployed" : "Local Host"}
                </Badge>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Protected Gateways:</span>
              <span className="text-[#10B981] font-bold font-mono">
                {mitigationStatus?.dns_gateways && mitigationStatus.dns_gateways.length > 0
                  ? mitigationStatus.dns_gateways.join(", ")
                  : "None configured"}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="mb-2 pb-2">
            <CardTitle className="text-xs uppercase tracking-wider text-gray-400">
              Rate Limiting Limits
            </CardTitle>
            <Shield className="w-4 h-4 text-[#06B6D4]" />
          </CardHeader>
          <CardContent className="text-xs space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Allowed Rate Range:</span>
              <span className="text-gray-200 font-mono">
                {mitigationStatus?.rate_limit_bounds
                  ? `${mitigationStatus.rate_limit_bounds.min_pps.toLocaleString()} – ${mitigationStatus.rate_limit_bounds.max_pps.toLocaleString()} req/s`
                  : loading
                  ? "Checking..."
                  : "Not set"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Max Rule Duration:</span>
              <span className="text-gray-200 font-mono">
                {mitigationStatus?.duration_bounds?.max_seconds
                  ? `${mitigationStatus.duration_bounds.max_seconds} seconds`
                  : loading
                  ? "Checking..."
                  : "Not set"}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="mb-2 pb-2">
            <CardTitle className="text-xs uppercase tracking-wider text-gray-400">
              Active Protection Rules
            </CardTitle>
            <div className="flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  activeCount > 0 ? "bg-[#00FF9D] animate-pulse" : "bg-gray-500"
                }`}
              />
              <span className="text-xs font-mono font-bold text-gray-200">{activeCount}</span>
            </div>
          </CardHeader>
          <CardContent className="text-xs space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Emergency Stop:</span>
              <Badge variant={isEmergencyActive ? "critical" : "normal"} className="text-[10px]">
                {isEmergencyActive ? "PAUSED" : "ARMED"}
              </Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Auto-Expiry:</span>
              <span className="text-[#00FF9D] font-medium">Automatic rollback enabled</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Suggested Defensive Rules Management Card (Dry-Run, Staging, Promotion & Export) */}
      <DefensiveRulesCard />

      {/* Rules History & Filterable Table */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <CardTitle>Protection Actions Log</CardTitle>
            <CardDescription>
              All simulated, suggested, and applied rate limiting actions with auto-expiry countdowns.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-400">Filter status:</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-1.5 bg-[#1F2937]/70 border border-gray-700/60 rounded-lg text-xs text-gray-200 focus:outline-none focus:border-[#00FF9D]"
            >
              <option value="all">All States</option>
              <option value="active">Active Only</option>
              <option value="simulated">Simulated Only</option>
              <option value="cancelled">Cancelled</option>
              <option value="expired">Expired</option>
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {filteredMitigations.length === 0 ? (
            <p className="text-sm text-gray-500 py-6 text-center">
              No protection actions recorded in this view.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-gray-800 text-gray-400 font-mono uppercase text-[10px]">
                  <tr>
                    <th className="py-2.5 px-3">Target Address</th>
                    <th className="py-2.5 px-3">Action Type</th>
                    <th className="py-2.5 px-3">Rate Limit</th>
                    <th className="py-2.5 px-3">Remaining Time</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/60 font-mono">
                  {paginatedMitigations.map((m) => {
                    const st = m.status || m.state;
                    const isActive = st === "active" || st === "simulated";
                    const remainingSec = m.time_remaining_seconds ?? m.time_remaining_seconds;
                    return (
                      <tr key={m.action_id} className="hover:bg-[#1F2937]/30 transition-colors">
                        <td className="py-3 px-3 text-[#06B6D4] font-bold">{m.target_ip}</td>
                        <td className="py-3 px-3 text-gray-300 uppercase">{m.action_type}</td>
                        <td className="py-3 px-3 text-gray-300">
                          {m.rate_limit_pps ? `${m.rate_limit_pps.toLocaleString()} req/s` : "—"}
                        </td>
                        <td className="py-3 px-3 text-[#00FF9D]">
                          {remainingSec !== undefined && remainingSec !== null ? `${remainingSec}s` : "Expired"}
                        </td>
                        <td className="py-3 px-3">
                          <Badge
                            variant={
                              st === "active"
                                ? "matrix"
                                : st === "simulated"
                                ? "cyan"
                                : st === "expired"
                                ? "outline"
                                : "critical"
                            }
                            className="text-[10px]"
                          >
                            {st === "active"
                              ? "Applied"
                              : st === "simulated"
                              ? "Simulated"
                              : st === "expired"
                              ? "Expired"
                              : "Cancelled"}
                          </Badge>
                        </td>
                        <td className="py-3 px-3 text-right">
                          {isActive && (
                            <Button
                              variant="danger"
                              size="sm"
                              onClick={() => handleCancel(m.action_id)}
                              disabled={cancellingId === m.action_id}
                              className="text-[10px] py-1 px-2 font-sans"
                            >
                              <XCircle className="w-3 h-3 mr-1" />
                              {cancellingId === m.action_id ? "Cancelling..." : "Cancel Rule"}
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {filteredMitigations.length > 0 && (
            <Pagination
              currentPage={mitPage}
              pageSize={mitPageSize}
              totalItems={filteredMitigations.length}
              onPageChange={setMitPage}
              onPageSizeChange={setMitPageSize}
              className="mt-3"
            />
          )}
        </CardContent>
      </Card>

      {/* Emergency Confirmation Modal */}
      <Modal
        isOpen={isDisableModalOpen}
        onClose={() => setIsDisableModalOpen(false)}
        title="Confirm Emergency Pause"
      >
        <div className="space-y-4">
          <p className="text-xs text-gray-300 leading-relaxed">
            Pausing defenses immediately stops all active and future rate limits. Genuine and test traffic will reach your backend without any filtering.
          </p>
          <div className="flex justify-end gap-3 pt-3 border-t border-gray-800">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsDisableModalOpen(false)}
              className="text-xs font-sans"
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={handleEmergencyDisable}
              className="text-xs font-sans"
            >
              Confirm Emergency Pause
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
