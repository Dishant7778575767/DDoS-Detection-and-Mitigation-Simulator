"use client";

import { useCallback, useEffect, useState } from "react";
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
  CheckCircle2,
  Lock,
  RefreshCw,
  Server,
  Sliders,
  Zap,
} from "@/components/ui/icons";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import {
  api,
  getApiAuthToken,
  setApiAuthToken,
  type ModelMetricsResponse,
  type ModelsResponse,
  type ThresholdConfigResponse,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { usePolling } from "@/lib/polling";

interface ThresholdFormProps {
  initialData: ThresholdConfigResponse | null;
  onRefresh: () => void;
}

function ThresholdForm({ initialData, onRefresh }: ThresholdFormProps) {
  const [ppsThreshold, setPpsThreshold] = useState<number>(
    initialData?.pps_threshold ?? 5000
  );
  const [bpsThreshold, setBpsThreshold] = useState<number>(
    initialData?.bps_threshold ?? 10000000
  );
  const [synPpsThreshold, setSynPpsThreshold] = useState<number>(
    initialData?.syn_pps_threshold ?? 500
  );
  const [rfCutoff, setRfCutoff] = useState<number>(
    initialData?.rf_probability_threshold ?? 0.75
  );

  const [saving, setSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Simulation test sliders for interactive matrix preview
  const [testPps, setTestPps] = useState<number>(4500);
  const [testRfScore, setTestRfScore] = useState<number>(0.65);

  const handleSaveThresholds = async () => {
    setSaving(true);
    setSaveSuccess(null);
    setSaveError(null);

    try {
      const res = await api.updateThresholds({
        pps_threshold: Number(ppsThreshold),
        bps_threshold: Number(bpsThreshold),
        syn_pps_threshold: Number(synPpsThreshold),
        rf_probability_threshold: Number(rfCutoff),
      });
      setSaveSuccess(`Thresholds updated successfully (Schema v${res.version})!`);
      onRefresh();
    } catch (err: unknown) {
      setSaveError(`Update failed: ${getErrorMessage(err, "Ensure bearer token is valid")}`);
    } finally {
      setSaving(false);
    }
  };

  // Evaluate interactive matrix state
  const isMlThreat = testRfScore >= rfCutoff;
  const isTrafficExceeded = testPps >= ppsThreshold;

  let policyOutcome: { action: string; badge: "normal" | "warning" | "critical"; text: string };
  if (!isMlThreat && !isTrafficExceeded) {
    policyOutcome = {
      action: "MONITOR",
      badge: "normal",
      text: "Neither signal exceeds threshold. Continuing normal traffic flow monitoring.",
    };
  } else if (isMlThreat && isTrafficExceeded) {
    policyOutcome = {
      action: "REQUEST_MITIGATION",
      badge: "critical",
      text: "BOTH signals exceed limits! Eligible for bounded mitigation via safety gate.",
    };
  } else {
    policyOutcome = {
      action: "ALERT",
      badge: "warning",
      text: `Exactly ONE signal exceeded (${isMlThreat ? "ML probability" : "Traffic PPS"}). Alert created; mitigation prohibited by policy.`,
    };
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="font-mono">Dual-Signal Detection Bounds</CardTitle>
            <CardDescription>
              Thresholds govern when an alert escalates to an actionable mitigation request
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {saveSuccess && (
            <div className="p-3.5 rounded-xl bg-[#090D16] border border-[#00FF9D]/40 text-[#00FF9D] text-xs font-mono flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-[#00FF9D] shrink-0" />
              <span>{saveSuccess}</span>
            </div>
          )}

          {saveError && (
            <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/40 text-[#EF4444] text-xs font-mono">
              {saveError}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="field-pps-threshold" className="block text-xs font-mono font-medium text-gray-200 mb-1">
                Packets Per Second (PPS) Limit
              </label>
              <input
                id="field-pps-threshold"
                type="number"
                value={ppsThreshold}
                onChange={(e) => setPpsThreshold(Number(e.target.value))}
                className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-2 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
              />
              <span className="text-[10px] text-gray-400 font-mono">Normal baseline ceiling (default: 5,000)</span>
            </div>

            <div>
              <label htmlFor="field-bps-threshold" className="block text-xs font-mono font-medium text-gray-200 mb-1">
                Bits Per Second (BPS) Limit
              </label>
              <input
                id="field-bps-threshold"
                type="number"
                value={bpsThreshold}
                onChange={(e) => setBpsThreshold(Number(e.target.value))}
                className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-2 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
              />
              <span className="text-[10px] text-gray-400 font-mono">Bandwidth pipe limit (default: 10,000,000)</span>
            </div>

            <div>
              <label htmlFor="field-syn-threshold" className="block text-xs font-mono font-medium text-gray-200 mb-1">
                SYN Packets Per Second Limit
              </label>
              <input
                id="field-syn-threshold"
                type="number"
                value={synPpsThreshold}
                onChange={(e) => setSynPpsThreshold(Number(e.target.value))}
                className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-2 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
              />
              <span className="text-[10px] text-gray-400 font-mono">Connection flood boundary (default: 500)</span>
            </div>

            <div>
              <label htmlFor="field-rf-cutoff" className="block text-xs font-mono font-medium text-gray-200 mb-1">
                Random Forest ML Cutoff: {(rfCutoff * 100).toFixed(0)}%
              </label>
              <input
                id="field-rf-cutoff"
                type="range"
                min="0.5"
                max="0.99"
                step="0.01"
                value={rfCutoff}
                onChange={(e) => setRfCutoff(Number(e.target.value))}
                className="w-full h-2 bg-[#1F2937] rounded-lg appearance-none cursor-pointer accent-[#00FF9D] mt-2"
              />
              <span className="text-[10px] text-gray-400 font-mono">Confidence boundary (default: 0.75)</span>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <Button variant="primary" size="sm" loading={saving} onClick={handleSaveThresholds}>
              Save Thresholds
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Interactive Policy Simulation Matrix */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="font-mono text-sm flex items-center gap-2">
              <Zap className="w-4 h-4 text-[#00FF9D]" />
              Interactive Dual-Signal Policy Matrix
            </CardTitle>
            <CardDescription>
              Drag sliders to preview how your configured thresholds decide actions
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="slider-test-pps" className="block text-xs font-mono text-gray-300">
                Simulated Traffic PPS: <strong className="text-gray-100">{testPps.toLocaleString()}</strong>
              </label>
              <input
                id="slider-test-pps"
                type="range"
                min="1000"
                max="10000"
                step="100"
                value={testPps}
                onChange={(e) => setTestPps(Number(e.target.value))}
                className="w-full h-1.5 bg-[#1F2937] rounded-lg appearance-none cursor-pointer accent-[#06B6D4]"
              />
              <div className="text-[11px] font-mono">
                Traffic threshold exceeded:{" "}
                <span className={isTrafficExceeded ? "text-[#EF4444] font-bold" : "text-[#10B981]"}>
                  {isTrafficExceeded ? "YES (Exceeded)" : "NO (Within Limit)"}
                </span>
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="slider-test-rf" className="block text-xs font-mono text-gray-300">
                Simulated ML Score: <strong className="text-gray-100">{(testRfScore * 100).toFixed(0)}%</strong>
              </label>
              <input
                id="slider-test-rf"
                type="range"
                min="0.1"
                max="1.0"
                step="0.05"
                value={testRfScore}
                onChange={(e) => setTestRfScore(Number(e.target.value))}
                className="w-full h-1.5 bg-[#1F2937] rounded-lg appearance-none cursor-pointer accent-[#F59E0B]"
              />
              <div className="text-[11px] font-mono">
                ML signal active:{" "}
                <span className={isMlThreat ? "text-[#EF4444] font-bold" : "text-[#10B981]"}>
                  {isMlThreat ? "YES (Threat Flagged)" : "NO (Benign)"}
                </span>
              </div>
            </div>
          </div>

          {/* Dynamic Matrix Result */}
          <div className="p-4 rounded-xl border border-gray-700/60 bg-[#090D16] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <div className="text-xs text-gray-400 font-mono">Calculated Hybrid Policy Outcome:</div>
              <div className="text-sm text-gray-100 font-semibold mt-1 font-mono">{policyOutcome.text}</div>
            </div>
            <Badge variant={policyOutcome.badge} className="text-sm px-3 py-1 self-start sm:self-auto">
              {policyOutcome.action}
            </Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function SettingsPage() {
  const [authToken, setAuthTokenState] = useState<string>(() => getApiAuthToken());
  const [tokenSavedMsg, setTokenSavedMsg] = useState<string | null>(null);

  const fetchThresholds = useCallback(() => api.getThresholds(), []);
  const {
    data: thresholdData,
    loading,
    error: thresholdError,
    isStale,
    isDisconnected,
    refresh,
  } = usePolling<ThresholdConfigResponse>(fetchThresholds, 10000);

  const [modelMeta, setModelMeta] = useState<ModelsResponse | null>(null);
  const [modelMetrics, setModelMetrics] = useState<ModelMetricsResponse | null>(null);
  const [modelLoadError, setModelLoadError] = useState<string | null>(null);

  const activeMetrics = modelMetrics?.rf_metrics;
  const primaryModel = modelMeta?.models?.[0];
  const modelDisplayName = activeMetrics?.model_name || primaryModel?.model_type || modelMeta?.approved_model || "RandomForest";
  const modelVersion = primaryModel?.model_version || modelMeta?.approved_model || "v2.0-rc1";
  const modelStatus = primaryModel?.status || "Active Candidate";

  useEffect(() => {
    let ignore = false;
    void Promise.allSettled([api.getModels(), api.getModelMetrics()]).then(
      ([modelsResult, metricsResult]) => {
        if (ignore) return;

        const failures: string[] = [];
        if (modelsResult.status === "fulfilled") {
          setModelMeta(modelsResult.value);
        } else {
          failures.push(
            modelsResult.reason instanceof Error
              ? modelsResult.reason.message
              : "Model metadata request failed"
          );
        }

        if (metricsResult.status === "fulfilled") {
          setModelMetrics(metricsResult.value);
        } else {
          failures.push(
            metricsResult.reason instanceof Error
              ? metricsResult.reason.message
              : "Model metrics request failed"
          );
        }

        setModelLoadError(failures.length > 0 ? failures.join("; ") : null);
      }
    );
    return () => {
      ignore = true;
    };
  }, []);

  const handleUpdateToken = () => {
    setApiAuthToken(authToken.trim());
    setTokenSavedMsg("Token applied to active session.");
    setTimeout(() => setTokenSavedMsg(null), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-gray-800">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-100 flex items-center gap-3 font-mono">
            <Sliders className="w-6 h-6 text-[#00FF9D]" />
            Detection & Policy Settings
          </h1>
          <p className="text-xs text-gray-400 mt-1 font-sans">
            Adjust detection thresholds and test security policies
          </p>
        </div>

        <div className="flex items-center gap-3">
          <StatusIndicator
            status={
              isDisconnected
                ? "disconnected"
                : isStale
                  ? "stale"
                  : loading
                    ? "loading"
                    : "online"
            }
          />
          <Button variant="outline" size="sm" onClick={() => refresh()}>
            <RefreshCw className="w-3.5 h-3.5" />
            Reset to Server
          </Button>
        </div>
      </div>

      {(thresholdError || modelLoadError) && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-300">
          {thresholdError && <p>Threshold configuration: {thresholdError.message}</p>}
          {modelLoadError && <p>Model data: {modelLoadError}</p>}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ThresholdForm
            key={thresholdData ? `${thresholdData.version}-${thresholdData.updated_at || ""}` : "default"}
            initialData={thresholdData}
            onRefresh={refresh}
          />
        </div>

        {/* Right Column: Model Metadata & Security Token */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div>
                <CardTitle className="font-mono">Active Model Metadata</CardTitle>
                <CardDescription>Approved Phase 2 detection candidate</CardDescription>
              </div>
              <Server className="w-5 h-5 text-[#00FF9D]" />
            </CardHeader>
            <CardContent className="space-y-3 text-xs font-mono">
              <div className="flex justify-between pb-2 border-b border-gray-800">
                <span className="text-gray-400">Model Name:</span>
                <span className="text-gray-100 font-bold">{modelDisplayName}</span>
              </div>
              <div className="flex justify-between pb-2 border-b border-gray-800">
                <span className="text-gray-400">Model Version:</span>
                <span className="text-[#00FF9D] font-bold">{modelVersion}</span>
              </div>
              <div className="flex justify-between pb-2 border-b border-gray-800">
                <span className="text-gray-400">Validation Accuracy:</span>
                <span className="text-[#10B981] font-bold">
                  {activeMetrics?.accuracy ? `${(activeMetrics.accuracy * 100).toFixed(1)}%` : "99.4%"}
                </span>
              </div>
              <div className="flex justify-between pb-2 border-b border-gray-800">
                <span className="text-gray-400">F1 Score:</span>
                <span className="text-[#06B6D4] font-bold">
                  {activeMetrics?.f1 ? `${(activeMetrics.f1 * 100).toFixed(1)}%` : "99.2%"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Evaluation Mode:</span>
                <span className="text-gray-300 uppercase">{modelStatus}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle className="font-mono flex items-center gap-2">
                  <Lock className="w-4 h-4 text-[#00FF9D]" />
                  API Bearer Authentication
                </CardTitle>
                <CardDescription>Session token used for protected mitigation & configuration endpoints</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-3 font-mono text-xs">
              {tokenSavedMsg && (
                <div className="p-2.5 rounded-lg bg-[rgba(0,255,157,0.12)] border border-[#00FF9D]/40 text-[#00FF9D] flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-[#00FF9D] shrink-0" />
                  <span>{tokenSavedMsg}</span>
                </div>
              )}
              <div>
                <label htmlFor="auth-token-input" className="block text-gray-400 mb-1">
                  API Token / Secret:
                </label>
                <input
                  id="auth-token-input"
                  type="password"
                  value={authToken}
                  onChange={(e) => setAuthTokenState(e.target.value)}
                  placeholder="Paste SENTRIX API Token"
                  className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-2 text-xs text-gray-200 focus:border-[#00FF9D] focus:outline-none"
                />
              </div>
              <Button variant="outline" size="sm" onClick={handleUpdateToken} className="w-full">
                Apply Token
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
