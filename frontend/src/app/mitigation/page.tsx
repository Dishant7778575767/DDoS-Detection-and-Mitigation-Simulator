"use client";

import { useCallback, useState } from "react";

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
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { api, type MitigationItem } from "@/lib/api";
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

export default function MitigationPage() {
  const [isDisableModalOpen, setIsDisableModalOpen] = useState<boolean>(false);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [isEmergencyActive, setIsEmergencyActive] = useState<boolean>(false);
  const [mitigationStatus, setMitigationStatus] = useState<MitigationStatusData | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const fetchMitigations = useCallback(async () => {
    try {
      const statusRes = await api.getMitigationStatus();
      setMitigationStatus(statusRes);
      setIsEmergencyActive(statusRes.emergency_disabled);
    } catch {
      // Ignore fallback if status endpoint unavailable
    }
    return api.getMitigations({ limit: 50 });
  }, []);

  const { data, loading, error, isStale, isDisconnected, lastUpdated, refresh } =
    usePolling(fetchMitigations, 3000);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    setActionMessage(null);
    try {
      const [statusRes] = await Promise.all([
        api.getMitigationStatus(),
        refresh(),
      ]);
      setMitigationStatus(statusRes);
      setIsEmergencyActive(statusRes.emergency_disabled);
      const timeStr = new Date().toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour12: false,
      });
      setActionMessage(`Protection state & rules refreshed at ${timeStr} IST`);
      setTimeout(() => setActionMessage(null), 3000);
    } catch (err: unknown) {
      const msg = err && typeof err === "object" && "message" in err ? String(err.message) : "Failed to refresh";
      setActionMessage(`Refresh failed: ${msg}`);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleCancel = async (actionId: string) => {
    setCancellingId(actionId);
    setActionMessage(null);
    try {
      await api.cancelMitigation(actionId);
      setActionMessage(`Action ${actionId.slice(0, 8)}... successfully cancelled.`);
      refresh();
    } catch (err: unknown) {
      const msg = err && typeof err === "object" && "message" in err ? String(err.message) : "Unknown error";
      setActionMessage(`Failed to cancel: ${msg}`);
    } finally {
      setCancellingId(null);
    }
  };

  const handleEmergencyDisable = async () => {
    setActionMessage(null);
    try {
      const res = await api.emergencyDisable(false);
      setIsEmergencyActive(true);
      setActionMessage(
        res.emergency_disabled
          ? "EMERGENCY DISABLE ACTIVATED: All future mitigation requests blocked."
          : "Emergency disable toggled."
      );
      setIsDisableModalOpen(false);
      refresh();
    } catch (err: unknown) {
      const msg = err && typeof err === "object" && "message" in err ? String(err.message) : "Unknown error";
      setActionMessage(`Emergency disable request failed: ${msg}`);
    }
  };

  const handleReenableSafetyGate = async () => {
    setActionMessage(null);
    try {
      await api.emergencyDisable(true);
      setIsEmergencyActive(false);
      setActionMessage("Safety Gate restored! Mitigation requests are now operational.");
      refresh();
    } catch (err: unknown) {
      const msg = err && typeof err === "object" && "message" in err ? String(err.message) : "Unknown error";
      setActionMessage(`Failed to restore safety gate: ${msg}`);
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
  const filteredMitigations = statusFilter === "all"
    ? allMitigations
    : allMitigations.filter((m) => (m.status || m.state) === statusFilter);

  const activeCount = allMitigations.filter((m) => {
    const s = m.status || m.state;
    return s === "active" || s === "simulated";
  }).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-[rgba(75,85,99,0.3)]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-100 flex items-center gap-3 font-mono">
            <Shield className="w-6 h-6 text-matrix-green" />
            DDoS Defense Rules & Protection State
          </h1>
          <p className="text-xs text-cool-silver mt-1 font-sans">
            Automated rate limiting and bounded DDoS mitigations evaluated safely with zero host impact
          </p>
        </div>

        <div className="flex items-center gap-3">
          <StatusIndicator status={statusType} />
          {lastUpdated && (
            <span className="text-xs text-cool-silver font-mono">
              Updated: {lastUpdated.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false })} IST
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="border-[rgba(75,85,99,0.4)] hover:border-matrix-green hover:text-matrix-green transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-matrix-green" : ""}`} />
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </Button>
          {isEmergencyActive ? (
            <Button
              variant="primary"
              size="sm"
              onClick={handleReenableSafetyGate}
              title="Clear lockout and restore safety gate"
              className="bg-emerald-600 hover:bg-emerald-500 text-white font-mono"
            >
              <Power className="w-4 h-4" />
              Re-enable Safety Gate
            </Button>
          ) : (
            <Button
              variant="danger"
              size="sm"
              onClick={() => setIsDisableModalOpen(true)}
              title="Emergency kill switch"
            >
              <Power className="w-4 h-4" />
              Emergency Kill-Switch
            </Button>
          )}
        </div>
      </div>

      {/* Emergency Active Alert Banner */}
      {isEmergencyActive && (
        <div className="p-4 rounded-xl border border-rose-500/50 bg-rose-500/15 text-rose-200 flex items-center justify-between gap-4 shadow-xl">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-rose-500/20 border border-rose-500/40 text-rose-400">
              <Power className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-rose-100 uppercase tracking-wider font-mono">
                Emergency Kill-Switch Active
              </h4>
              <p className="text-xs text-rose-300 font-sans">
                All automatic & manual mitigation simulations are currently locked out by the Safety Gate.
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleReenableSafetyGate}
            className="border-rose-400 text-rose-200 hover:bg-rose-500/20 font-mono shrink-0"
          >
            Re-enable System Now
          </Button>
        </div>
      )}

      {/* Action Notification */}
      {actionMessage && (
        <div className="p-3.5 rounded-xl bg-obsidian border border-matrix-green/40 text-matrix-green text-xs font-mono flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-[#00FF9D] shrink-0" />
          <span>{actionMessage}</span>
        </div>
      )}

      {/* Guardrails Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="mb-2 pb-2">
            <CardTitle className="text-xs font-mono uppercase tracking-wider text-[#9CA3AF]">
              Protected Infrastructure
            </CardTitle>
            <Server className="w-4 h-4 text-[#10B981]" />
          </CardHeader>
          <CardContent className="text-xs font-mono space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-[#9CA3AF]">Host IP / Server:</span>
              <div className="flex items-center gap-1.5">
                <span className="text-[#10B981] font-bold">
                  {mitigationStatus?.host_ip || "127.0.0.1"}
                </span>
                <Badge
                  variant={mitigationStatus?.is_deployed ? "matrix" : "outline"}
                  className="text-[10px] py-0 px-1.5 uppercase font-mono font-normal tracking-wide"
                >
                  {mitigationStatus?.is_deployed ? "Deployed Server" : "Protected Host"}
                </Badge>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[#9CA3AF]">Default DNS Gateways:</span>
              <span className="text-[#10B981] font-bold">
                {mitigationStatus?.dns_gateways && mitigationStatus.dns_gateways.length > 0
                  ? mitigationStatus.dns_gateways.join(", ")
                  : "8.8.8.8, 1.1.1.1"}
              </span>
            </div>
            {mitigationStatus?.hostname && (
              <div className="flex justify-between items-center">
                <span className="text-[#9CA3AF]">Node Name:</span>
                <span className="text-[#9CA3AF] font-mono text-[11px]">
                  {mitigationStatus.hostname}
                </span>
              </div>
            )}
            <p className="text-[11px] text-[#9CA3AF]/70 pt-1 font-sans">
              Mitigation requests targeting essential infrastructure are unconditionally rejected by policy.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="mb-2 pb-2">
            <CardTitle className="text-xs font-mono uppercase tracking-wider text-[#9CA3AF]">
              Rate Limit Safety Bounds
            </CardTitle>
            <Shield className="w-4 h-4 text-[#06B6D4]" />
          </CardHeader>
          <CardContent className="text-xs font-mono space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-[#9CA3AF]">Permitted Rates:</span>
              <span className="text-[#00FF9D] font-bold">
                {mitigationStatus?.rate_limit_bounds
                  ? `${mitigationStatus.rate_limit_bounds.min_pps.toLocaleString()} - ${mitigationStatus.rate_limit_bounds.max_pps.toLocaleString()} PPS`
                  : "100 - 50,000 PPS"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[#9CA3AF]">Permitted Durations:</span>
              <span className="text-[#06B6D4] font-bold">
                {mitigationStatus?.duration_bounds
                  ? `${mitigationStatus.duration_bounds.min_seconds} - ${mitigationStatus.duration_bounds.max_seconds} seconds`
                  : "10 - 300 seconds"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[#9CA3AF]">Max Concurrency:</span>
              <span className="text-[#9CA3AF] font-mono text-[11px]">
                {mitigationStatus?.max_concurrent_limit || 100} active rules
              </span>
            </div>
            <p className="text-[11px] text-[#9CA3AF]/70 pt-1 font-sans">
              All mitigation actions are time-bounded and expire automatically to prevent permanent blocks.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="mb-2 pb-2">
            <CardTitle className="text-xs font-mono uppercase tracking-wider text-[#9CA3AF]">
              Active Protection State
            </CardTitle>
            <AlertTriangle className="w-4 h-4 text-[#F59E0B]" />
          </CardHeader>
          <CardContent className="text-xs font-mono space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-[#9CA3AF]">Active Rules:</span>
              <span className="text-[#00FF9D] font-bold">{activeCount} Rules Active</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[#9CA3AF]">Target Cooldown:</span>
              <span className="text-[#F59E0B] font-bold">
                {mitigationStatus?.cooldown_ticks ?? 10} ticks cooldown
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[#9CA3AF]">Shield Mode:</span>
              <span className={`font-mono text-[11px] uppercase ${mitigationStatus?.shield_active ? "text-[#00FF9D]" : "text-[#9CA3AF]"}`}>
                {mitigationStatus?.shield_active ? "Shield Active" : "Standby / Fail-Closed"}
              </span>
            </div>
            <p className="text-[11px] text-[#9CA3AF]/70 pt-1 font-sans">
              Cooldown guards prevent rapid rule oscillation and alert storms.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Mitigations List Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-4 w-full">
            <div>
              <CardTitle className="font-mono">
                Protection Rules & Mitigations ({filteredMitigations.length})
              </CardTitle>
              <CardDescription>
                Live rate-limiting rules protecting server targets from DDoS volumetric attacks
              </CardDescription>
            </div>

            {/* Filter */}
            <div className="flex items-center gap-2">
              <label className="text-xs text-[#9CA3AF] font-mono">Status:</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-[#090D16] border border-[rgba(75,85,99,0.4)] rounded-lg px-2.5 py-1 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
              >
                <option value="all">All Statuses</option>
                <option value="active">Active</option>
                <option value="simulated">Simulated</option>
                <option value="cancelled">Cancelled</option>
                <option value="expired">Expired</option>
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="p-4 mb-4 rounded-xl border border-red-500/40 bg-[rgba(239,68,68,0.15)] text-[#EF4444] text-xs font-mono">
              Error fetching mitigations: {error.message}
            </div>
          )}

          <div className="overflow-x-auto rounded-xl border border-[rgba(75,85,99,0.3)] bg-[#090D16]/80 font-mono text-xs">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[rgba(75,85,99,0.3)] bg-[#1F2937]/50 text-[#9CA3AF] text-[11px] uppercase tracking-wider">
                  <th className="py-3 px-3">Action ID</th>
                  <th className="py-3 px-3">Target IP</th>
                  <th className="py-3 px-3">Rule Type</th>
                  <th className="py-3 px-3">Rate Limit</th>
                  <th className="py-3 px-3">Duration</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3">Mode</th>
                  <th className="py-3 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[rgba(75,85,99,0.2)]">
                {filteredMitigations.length > 0 ? (
                  filteredMitigations.map((item: MitigationItem) => {
                    const currentState = item.status || item.state || "unknown";
                    const isActionActive = currentState === "active" || currentState === "simulated";

                    return (
                      <tr key={item.action_id} className="hover:bg-[#1F2937]/40 transition-colors">
                        <td className="py-3 px-3 text-[#00FF9D] font-bold">
                          {item.action_id.slice(0, 10)}
                        </td>
                        <td className="py-3 px-3 text-gray-200">{item.target_ip}</td>
                        <td className="py-3 px-3 text-[#9CA3AF] uppercase">{item.action_type}</td>
                        <td className="py-3 px-3 text-[#06B6D4]">
                          {item.rate_limit_pps ? `${item.rate_limit_pps.toLocaleString()} PPS` : "Rate Limit"}
                        </td>
                        <td className="py-3 px-3 text-[#9CA3AF]">
                          {item.duration_seconds}s
                        </td>
                        <td className="py-3 px-3">
                          <Badge
                            variant={
                              isActionActive
                                ? "normal"
                                : currentState === "cancelled"
                                ? "warning"
                                : currentState === "expired"
                                ? "outline"
                                : "info"
                            }
                          >
                            {currentState}
                          </Badge>
                        </td>
                        <td className="py-3 px-3">
                          <span className="text-[11px] text-[#06B6D4] font-semibold uppercase">
                            {item.mode || "SIMULATION"}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right">
                          {isActionActive ? (
                            <Button
                              variant="outline"
                              size="sm"
                              loading={cancellingId === item.action_id}
                              onClick={() => handleCancel(item.action_id)}
                              title="Stop this mitigation rule"
                            >
                              <XCircle className="w-3.5 h-3.5 text-[#EF4444]" />
                              Cancel
                            </Button>
                          ) : (
                            <span className="text-gray-600">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-[#9CA3AF]">
                      No mitigation rules matching this filter recorded yet. Launch an attack in the Simulator to trigger automated defenses!
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Emergency Disable Confirmation Modal */}
      <Modal
        isOpen={isDisableModalOpen}
        onClose={() => setIsDisableModalOpen(false)}
        title="Trigger Emergency Kill-Switch"
        variant="danger"
      >
        <div className="space-y-4 font-mono text-xs">
          <p className="text-gray-200 leading-relaxed font-sans">
            Are you sure you want to trigger the emergency kill-switch? This will immediately disable
            all active virtual mitigation rules and prevent new rules from deploying.
          </p>
          <div className="flex justify-end gap-3 pt-3">
            <Button variant="ghost" onClick={() => setIsDisableModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleEmergencyDisable}>
              Confirm Emergency Disable
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
