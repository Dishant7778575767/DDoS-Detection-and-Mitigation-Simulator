"use client";

import { useCallback, useState } from "react";
import {
  CheckCircle2,
  Download,
  Shield,
} from "@/components/ui/icons";
import { Badge, type BadgeVariant } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Pagination } from "@/components/ui/Pagination";
import { usePagination } from "@/hooks/usePagination";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { api, type DefensiveRule } from "@/lib/api";
import { usePolling } from "@/lib/polling";

export function DefensiveRulesCard() {
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [newTarget, setNewTarget] = useState("");
  const [newAction, setNewAction] = useState<"BLOCK" | "RATE_LIMIT">("RATE_LIMIT");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchRules = useCallback(() => api.getDefensiveRules(true), []);
  const { data: rules, refresh } = usePolling<DefensiveRule[]>(fetchRules, 3000);

  const {
    currentPage,
    pageSize,
    totalPages,
    totalItems,
    paginatedItems: paginatedRules,
    setPage,
    setPageSize,
  } = usePagination(rules || [], 5);

  const handleApprove = async (ruleId: string) => {
    setApprovingId(ruleId);
    try {
      await api.approveDefensiveRule(ruleId);
      setActionMsg(`Rule ${ruleId} promoted from Dry-Run to Active Enforcement.`);
      await refresh();
      setTimeout(() => setActionMsg(null), 3500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to approve rule";
      setActionMsg(`Approval error: ${msg}`);
    } finally {
      setApprovingId(null);
    }
  };

  const handleRevoke = async (ruleId: string) => {
    setRevokingId(ruleId);
    try {
      await api.revokeDefensiveRule(ruleId);
      setActionMsg(`Rule ${ruleId} revoked.`);
      await refresh();
      setTimeout(() => setActionMsg(null), 3500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to revoke rule";
      setActionMsg(`Revocation error: ${msg}`);
    } finally {
      setRevokingId(null);
    }
  };

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTarget.trim()) return;
    setIsSubmitting(true);
    try {
      await api.proposeDefensiveRule({
        target_ip_or_cidr: newTarget.trim(),
        action_type: newAction,
        rate_limit_rps: 10,
        burst_capacity: 20,
        ttl_seconds: 600,
        reason: "Operator manual defensive entry",
        dry_run: true,
      });
      setNewTarget("");
      setActionMsg("New defensive rule created in safe Dry-Run mode.");
      await refresh();
      setTimeout(() => setActionMsg(null), 3500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to propose rule";
      setActionMsg(`Error: ${msg}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleExportNginx = async () => {
    try {
      await api.downloadNginxConfig();
      setActionMsg("Downloaded sentrix_nginx_defense.conf successfully.");
      setTimeout(() => setActionMsg(null), 3500);
    } catch (error) {
      setActionMsg(error instanceof Error ? error.message : "Nginx export failed");
    }
  };

  const handleExportCaddy = async () => {
    try {
      await api.downloadCaddyConfig();
      setActionMsg("Downloaded Caddyfile_sentrix.snippet successfully.");
      setTimeout(() => setActionMsg(null), 3500);
    } catch (error) {
      setActionMsg(error instanceof Error ? error.message : "Caddy export failed");
    }
  };

  const handleExportAwsWaf = async () => {
    try {
      await api.downloadAwsWafConfig();
      setActionMsg("Downloaded sentrix_aws_wafv2.json successfully.");
      setTimeout(() => setActionMsg(null), 3500);
    } catch (error) {
      setActionMsg(error instanceof Error ? error.message : "AWS WAF export failed");
    }
  };

  const handleExportAwsCli = async () => {
    try {
      await api.downloadAwsWafCli();
      setActionMsg("Downloaded sentrix_aws_waf_deploy.sh successfully.");
      setTimeout(() => setActionMsg(null), 3500);
    } catch (error) {
      setActionMsg(error instanceof Error ? error.message : "AWS WAF CLI export failed");
    }
  };

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle className="font-mono flex items-center gap-2">
            <Shield className="w-5 h-5 text-[#00FF9D]" />
            Real-World Defensive Policies & Staged Dry-Run Rules
          </CardTitle>
          <CardDescription>
            Defensive rate-limiting and reverse proxy firewall integration
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Actions Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-gray-800">
            <form onSubmit={handleCreateRule} className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                placeholder="e.g. 198.51.100.0/24"
                value={newTarget}
                onChange={(e) => setNewTarget(e.target.value)}
                className="bg-[#090D16] border border-gray-700/60 rounded px-2.5 py-1 text-xs font-mono text-gray-200 placeholder-gray-500 focus:border-[#00FF9D] focus:outline-none"
              />
              <select
                value={newAction}
                onChange={(e) => setNewAction(e.target.value as "BLOCK" | "RATE_LIMIT")}
                className="bg-[#090D16] border border-gray-700/60 rounded px-2 py-1 text-xs font-mono text-gray-200 focus:border-[#00FF9D] focus:outline-none"
              >
                <option value="RATE_LIMIT">Rate Limit (10 r/s)</option>
                <option value="BLOCK">Block IP</option>
              </select>
              <Button
                type="submit"
                size="sm"
                variant="outline"
                disabled={isSubmitting || !newTarget.trim()}
                className="text-xs"
              >
                <Shield className="w-3.5 h-3.5 mr-1 text-[#00FF9D]" />
                Propose Dry-Run
              </Button>
            </form>

            {/* Export Buttons */}
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={handleExportNginx}
                className="text-xs font-mono"
              >
                <Download className="w-3.5 h-3.5 mr-1 text-[#00FF9D]" />
                Export Nginx
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleExportCaddy}
                className="text-xs font-mono"
              >
                <Download className="w-3.5 h-3.5 mr-1 text-[#06B6D4]" />
                Export Caddyfile
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleExportAwsWaf}
                className="text-xs font-mono"
              >
                <Download className="w-3.5 h-3.5 mr-1 text-[#F59E0B]" />
                Export AWS WAFv2
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleExportAwsCli}
                className="text-xs font-mono"
              >
                <Download className="w-3.5 h-3.5 mr-1 text-[#EC4899]" />
                Export AWS CLI (.sh)
              </Button>
            </div>
          </div>

          {actionMsg && (
            <div className="p-2.5 bg-[#1F2937]/90 border border-[#00FF9D]/40 rounded text-xs font-mono text-[#00FF9D] flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" />
              {actionMsg}
            </div>
          )}

          {/* Rules Table */}
          {(!rules || rules.length === 0) ? (
            <p className="text-xs font-mono text-gray-500 py-4 text-center">
              No defensive mitigation rules configured. Propose a rule above or trigger one from the Threat Center.
            </p>
          ) : (
            <div className="space-y-3">
              <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-xs">
                <thead className="bg-[#111827]/70 text-gray-400 uppercase text-[10px]">
                  <tr>
                    <th className="py-2 px-3">Rule ID</th>
                    <th className="py-2 px-3">Target Subnet / IP</th>
                    <th className="py-2 px-3">Action</th>
                    <th className="py-2 px-3">Mode</th>
                    <th className="py-2 px-3">Impact (Sim/Active)</th>
                    <th className="py-2 px-3">TTL</th>
                    <th className="py-2 px-3 text-right">Operator Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/60">
                  {paginatedRules.map((rule) => {
                    const isDryRun = rule.mode === "DRY_RUN";
                    const isActive = rule.mode === "ACTIVE";

                    const badgeVariant: BadgeVariant = isActive
                      ? "matrix"
                      : isDryRun
                      ? "warning"
                      : "outline";

                    return (
                      <tr key={rule.rule_id} className="hover:bg-white/[0.02]">
                        <td className="py-2.5 px-3 text-gray-300 font-bold">{rule.rule_id}</td>
                        <td className="py-2.5 px-3 text-[#00FF9D] font-bold">{rule.target_ip_or_cidr}</td>
                        <td className="py-2.5 px-3">
                          <Badge variant={rule.action_type === "BLOCK" ? "critical" : "cyan"}>
                            {rule.action_type === "RATE_LIMIT" ? `${rule.rate_limit_rps} r/s` : "BLOCK"}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-3">
                          <Badge variant={badgeVariant}>
                            {rule.mode}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-3 text-gray-300">
                          {rule.simulated_blocked_count} sim / {rule.active_blocked_count} act
                        </td>
                        <td className="py-2.5 px-3 text-gray-400">
                          {rule.ttl_seconds}s
                        </td>
                        <td className="py-2.5 px-3 text-right space-x-2">
                          {isDryRun && (
                            <Button
                              size="sm"
                              variant="primary"
                              onClick={() => handleApprove(rule.rule_id)}
                              disabled={approvingId === rule.rule_id}
                              className="text-[10px] py-0.5 px-2 font-mono"
                            >
                              Approve
                            </Button>
                          )}
                          {(isDryRun || isActive) && (
                            <Button
                              size="sm"
                              variant="danger"
                              onClick={() => handleRevoke(rule.rule_id)}
                              disabled={revokingId === rule.rule_id}
                              className="text-[10px] py-0.5 px-2 font-mono"
                            >
                              Revoke
                            </Button>
                          )}
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
              pageSizeOptions={[5, 10, 20]}
            />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
