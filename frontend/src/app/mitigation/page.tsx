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

export default function MitigationPage() {
  const [isDisableModalOpen, setIsDisableModalOpen] = useState<boolean>(false);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchMitigations = useCallback(() => {
    return api.getMitigations({ limit: 50 });
  }, []);

  const { data, loading, error, isStale, isDisconnected, lastUpdated, refresh } =
    usePolling(fetchMitigations, 3000);

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
      const res = await api.emergencyDisable();
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

  const statusType = isDisconnected
    ? "disconnected"
    : isStale
      ? "stale"
      : loading
        ? "loading"
        : "online";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-cyan-500/15">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-cyan-50 flex items-center gap-3">
            <Shield className="w-6 h-6 text-cyan-400" />
            Mitigation & Safety Gate Control Room
          </h1>
          <p className="text-xs text-sky-200/60 mt-1">
            Fail-closed safety guardrails, bounded mitigation actions, and simulation lifecycle
          </p>
        </div>

        <div className="flex items-center gap-3">
          <StatusIndicator status={statusType} />
          {lastUpdated && (
            <span className="text-xs text-sky-300/40 font-mono">
              {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <Button variant="outline" size="sm" onClick={() => refresh()}>
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => setIsDisableModalOpen(true)}
            title="Emergency kill switch"
          >
            <Power className="w-4 h-4" />
            Emergency Disable
          </Button>
        </div>
      </div>

      {/* Prominent Safety Gate Notice */}
      <div className="p-4 rounded-xl border border-cyan-500/30 bg-cyan-950/20 text-cyan-200 flex items-start gap-4">
        <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 shrink-0">
          <Shield className="w-5 h-5" />
        </div>
        <div>
          <h4 className="text-sm font-semibold text-cyan-100 uppercase tracking-wider font-mono">
            Safety Gate Baseline: Pure Simulation
          </h4>
          <p className="text-xs text-sky-200/70 mt-1">
            Mitigation actions are strictly executed in <strong>simulation mode</strong>. SENTRIX
            verifies all guardrails, checks allowlists, and advances state machine lifecycles without
            invoking privileged firewall alterations or modifying host networking.
          </p>
        </div>
      </div>

      {/* Action Notification */}
      {actionMessage && (
        <div className="p-3 rounded-lg bg-slate-900 border border-cyan-500/30 text-cyan-200 text-xs font-mono flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>{actionMessage}</span>
        </div>
      )}

      {/* Guardrails Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="mb-2 pb-2">
            <CardTitle className="text-sm font-medium text-sky-300/80">
              Protected Target Allowlist
            </CardTitle>
            <Server className="w-4 h-4 text-emerald-400" />
          </CardHeader>
          <CardContent className="text-xs font-mono space-y-2">
            <div className="flex justify-between">
              <span className="text-sky-300/60">Loopback / Localhost:</span>
              <span className="text-emerald-400 font-bold">127.0.0.1 (Locked)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sky-300/60">Core DNS / Gateway:</span>
              <span className="text-emerald-400 font-bold">8.8.8.8, 1.1.1.1 (Locked)</span>
            </div>
            <p className="text-[11px] text-sky-200/40 pt-1">
              Actions targeting protected infrastructure are unconditionally rejected.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="mb-2 pb-2">
            <CardTitle className="text-sm font-medium text-sky-300/80">
              Action Parameter Bounds
            </CardTitle>
            <Shield className="w-4 h-4 text-cyan-400" />
          </CardHeader>
          <CardContent className="text-xs font-mono space-y-2">
            <div className="flex justify-between">
              <span className="text-sky-300/60">Allowed Rate Limits:</span>
              <span className="text-cyan-200 font-bold">100 - 50,000 pps</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sky-300/60">Allowed Durations:</span>
              <span className="text-cyan-200 font-bold">10 - 300 seconds</span>
            </div>
            <p className="text-[11px] text-sky-200/40 pt-1">
              Unbounded or negative parameters fail closed.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="mb-2 pb-2">
            <CardTitle className="text-sm font-medium text-sky-300/80">
              Concurrency & Cooldown
            </CardTitle>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </CardHeader>
          <CardContent className="text-xs font-mono space-y-2">
            <div className="flex justify-between">
              <span className="text-sky-300/60">Max Concurrent Actions:</span>
              <span className="text-amber-400 font-bold">100 Max</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sky-300/60">Target IP Cooldown:</span>
              <span className="text-amber-400 font-bold">30 seconds</span>
            </div>
            <p className="text-[11px] text-sky-200/40 pt-1">
              Prevents alert storms and rapid action thrashing.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Mitigations List Table */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Mitigation History & Active Lifecycles ({data?.total_count ?? data?.total ?? 0})</CardTitle>
            <CardDescription>
              State transitions: proposed → simulated → cancelled / expired
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="p-4 mb-4 rounded-xl border border-rose-500/30 bg-rose-950/20 text-rose-300 text-xs">
              Error fetching mitigations: {error.message}
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-cyan-500/15 text-sky-300/60 uppercase tracking-wider">
                  <th className="pb-3 px-3">Action ID</th>
                  <th className="pb-3 px-3">Target IP</th>
                  <th className="pb-3 px-3">Action Type</th>
                  <th className="pb-3 px-3">Rate Limit</th>
                  <th className="pb-3 px-3">Duration</th>
                  <th className="pb-3 px-3">Lifecycle State</th>
                  <th className="pb-3 px-3">Mode</th>
                  <th className="pb-3 px-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cyan-500/10">
                {data?.mitigations && data.mitigations.length > 0 ? (
                  data.mitigations.map((item: MitigationItem) => (
                    <tr key={item.action_id} className="hover:bg-cyan-500/5 transition-colors">
                      <td className="py-3 px-3 text-sky-300 font-bold">
                        {item.action_id.slice(0, 8)}...
                      </td>
                      <td className="py-3 px-3 text-cyan-200">{item.target_ip}</td>
                      <td className="py-3 px-3 text-slate-300 uppercase">{item.action_type}</td>
                      <td className="py-3 px-3 text-sky-300">
                        {item.rate_limit_pps.toLocaleString()} pps
                      </td>
                      <td className="py-3 px-3 text-sky-200/80">
                        {item.duration_seconds}s
                      </td>
                      <td className="py-3 px-3">
                        {(() => {
                          const currentState = item.state || item.status || "unknown";
                          return (
                            <Badge
                              variant={
                                currentState === "simulated"
                                  ? "simulation"
                                  : currentState === "cancelled"
                                    ? "warning"
                                    : currentState === "expired"
                                      ? "outline"
                                      : "info"
                              }
                            >
                              {currentState}
                            </Badge>
                          );
                        })()}
                      </td>
                      <td className="py-3 px-3">
                        <span className="text-[11px] text-cyan-400 font-semibold uppercase">
                          {item.mode || "SIMULATION"}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        {(item.state === "simulated" || item.status === "simulated") ? (
                          <Button
                            variant="outline"
                            size="sm"
                            loading={cancellingId === item.action_id}
                            onClick={() => handleCancel(item.action_id)}
                          >
                            <XCircle className="w-3.5 h-3.5 text-rose-400" />
                            Cancel
                          </Button>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={8} className="text-center py-8 text-sky-200/40">
                      No mitigations recorded yet.
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
        title="Activate Emergency Disable?"
        description="This will instantly trigger the fail-closed emergency circuit breaker."
        variant="danger"
      >
        <div className="space-y-4 text-xs font-mono">
          <p className="text-rose-200/90">
            When Emergency Disable is active, <strong>ALL</strong> automated and simulated mitigation
            requests are blocked at the safety gate with immediate rejection.
          </p>

          <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-500/30 text-rose-300">
            Authorization: Requires operator bearer token. An immutable audit record will be logged.
          </div>

          <div className="flex justify-end gap-3 pt-3">
            <Button variant="ghost" size="sm" onClick={() => setIsDisableModalOpen(false)}>
              Abort
            </Button>
            <Button variant="danger" size="sm" onClick={handleEmergencyDisable}>
              Confirm Emergency Disable
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
