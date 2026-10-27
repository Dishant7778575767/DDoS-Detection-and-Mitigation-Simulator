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
  Activity,
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
      const msg = err && typeof err === "object" && "message" in err ? String(err.message) : "Ensure bearer token is valid";
      setSaveError(`Update failed: ${msg}`);
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
      text: `Exactly ONE signal exceeded (${isMlThreat ? "ML probability" : "Traffic PPS"}). Alert created mitigation prohibited by policy.`,
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
            <div className="p-3 rounded-lg bg-[rgba(0,255,157,0.12)] border border-[#00FF9D]/40 text-[#00FF9D] text-xs font-mono flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-[#00FF9D] shrink-0" />
              <span>{saveSuccess}</span>
            </div>
          )}
          {saveError && (
            <div className="p-3 rounded-lg bg-[rgba(239,68,68,0.15)] border border-red-500/40 text-[#EF4444] text-xs font-mono">
              {saveError}
            </div>
          )}

          {/* Slider 1: PPS Threshold */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <label className="text-gray-200 font-semibold flex items-center gap-2">
                <Zap className="w-3.5 h-3.5 text-[#00FF9D]" />
                Packets Per Second (PPS) Threshold:
              </label>
              <span className="px-2 py-0.5 rounded bg-[#090D16] border border-[#00FF9D]/40 text-[#00FF9D] font-bold">
                {ppsThreshold.toLocaleString()} pps
              </span>
            </div>
            <input
              suppressHydrationWarning
              type="range"
              min="1000"
              max="50000"
              step="500"
              value={ppsThreshold}
              onChange={(e) => setPpsThreshold(Number(e.target.value))}
              className="w-full h-1.5 bg-[#1F2937] rounded-lg appearance-none cursor-pointer accent-[#00FF9D]"
            />
            <div className="flex justify-between text-[10px] text-[#9CA3AF]/60 font-mono">
              <span>Min: 1,000 pps</span>
              <span>Default: 5,000 pps</span>
              <span>Max: 50,000 pps</span>
            </div>
          </div>

          {/* Slider 2: SYN PPS Threshold */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <label className="text-gray-200 font-semibold flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 text-[#06B6D4]" />
                SYN Flood Rate Threshold:
              </label>
              <span className="px-2 py-0.5 rounded bg-[#090D16] border border-[#06B6D4]/40 text-[#06B6D4] font-bold">
                {synPpsThreshold.toLocaleString()} syn/s
              </span>
            </div>
            <input
              suppressHydrationWarning
              type="range"
              min="50"
              max="5000"
              step="50"
              value={synPpsThreshold}
              onChange={(e) => setSynPpsThreshold(Number(e.target.value))}
              className="w-full h-1.5 bg-[#1F2937] rounded-lg appearance-none cursor-pointer accent-[#06B6D4]"
            />
            <div className="flex justify-between text-[10px] text-[#9CA3AF]/60 font-mono">
              <span>Min: 50 syn/s</span>
              <span>Default: 500 syn/s</span>
              <span>Max: 5,000 syn/s</span>
            </div>
          </div>

          {/* Slider 3: RF Cutoff */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <label className="text-gray-200 font-semibold flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 text-[#F59E0B]" />
                Random Forest Probability Cutoff:
              </label>
              <span className="px-2 py-0.5 rounded bg-[#090D16] border border-amber-500/40 text-[#F59E0B] font-bold">
                {(rfCutoff * 100).toFixed(0)}% ({rfCutoff.toFixed(2)})
              </span>
            </div>
            <input
              suppressHydrationWarning
              type="range"
              min="0.50"
              max="0.99"
              step="0.01"
              value={rfCutoff}
              onChange={(e) => setRfCutoff(Number(e.target.value))}
              className="w-full h-1.5 bg-[#1F2937] rounded-lg appearance-none cursor-pointer accent-[#F59E0B]"
            />
            <div className="flex justify-between text-[10px] text-[#9CA3AF]/60 font-mono">
              <span>Conservative: 0.50</span>
              <span>Default: 0.75</span>
              <span>High Precision: 0.95</span>
            </div>
          </div>

          {/* Input: BPS Bandwidth Threshold */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <label className="text-gray-200 font-semibold">
                Bandwidth Threshold (Bits/s):
              </label>
              <span className="text-[#06B6D4] text-xs">
                {(bpsThreshold / 1000000).toFixed(1)} Mbps
              </span>
            </div>
            <input
              suppressHydrationWarning
              type="number"
              min="1000000"
              max="100000000"
              step="1000000"
              value={bpsThreshold}
              onChange={(e) => setBpsThreshold(Number(e.target.value))}
              className="w-full bg-[#090D16] border border-[rgba(75,85,99,0.4)] rounded-lg px-3 py-2 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
            />
          </div>

          {/* Save & Apply Button */}
          <div className="pt-4 flex justify-end">
            <Button
              variant="primary"
              loading={saving}
              disabled={!initialData}
              onClick={handleSaveThresholds}
            >
              Save & Apply Thresholds
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Interactive Policy Decision Simulator */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="font-mono">Interactive Policy Decision Simulator</CardTitle>
            <CardDescription>
              Drag the sliders below to test how incoming flows trigger the dual-signal matrix
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3 rounded-xl bg-[#090D16] border border-[rgba(75,85,99,0.3)] space-y-2">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-[#9CA3AF]">Test Ingress Rate:</span>
                <span className="text-[#00FF9D] font-bold">{testPps.toLocaleString()} pps</span>
              </div>
              <input
                suppressHydrationWarning
                type="range"
                min="500"
                max="15000"
                step="250"
                value={testPps}
                onChange={(e) => setTestPps(Number(e.target.value))}
                className="w-full h-1.5 bg-[#1F2937] rounded-lg appearance-none cursor-pointer accent-[#00FF9D]"
              />
              <div className="text-[11px] font-mono">
                Threshold exceeded:{" "}
                <span className={isTrafficExceeded ? "text-[#EF4444] font-bold" : "text-[#10B981]"}>
                  {isTrafficExceeded ? "YES (Exceeds Limit)" : "NO (Within Limit)"}
                </span>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-[#090D16] border border-[rgba(75,85,99,0.3)] space-y-2">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-[#9CA3AF]">Test RF Threat Score:</span>
                <span className="text-[#F59E0B] font-bold">{(testRfScore * 100).toFixed(0)}%</span>
              </div>
              <input
                suppressHydrationWarning
                type="range"
                min="0.10"
                max="1.00"
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
          <div className="p-4 rounded-xl border border-[rgba(75,85,99,0.3)] bg-[#090D16] flex items-center justify-between">
            <div>
              <div className="text-xs text-[#9CA3AF] font-mono">Calculated Hybrid Policy Outcome:</div>
              <div className="text-sm text-gray-100 font-semibold mt-1 font-mono">{policyOutcome.text}</div>
            </div>
            <Badge variant={policyOutcome.badge} className="text-sm px-3 py-1">
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
  } =
    usePolling<ThresholdConfigResponse>(fetchThresholds, 10000);

  const [modelMeta, setModelMeta] = useState<ModelsResponse | null>(null);
  const [modelMetrics, setModelMetrics] = useState<ModelMetricsResponse | null>(null);
  const [modelLoadError, setModelLoadError] = useState<string | null>(null);

  const activeMetrics = modelMetrics?.rf_metrics;

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
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-[rgba(75,85,99,0.3)]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-100 flex items-center gap-3 font-mono">
  <Sliders className="w-6 h-6 text-[#00FF9D]" />
  Detection & Policy Settings
</h1>

<p className="text-xs text-[#9CA3AF] mt-1 font-sans">
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
              <div className="flex justify-between pb-2 border-b border-[rgba(75,85,99,0.2)]">
                <span className="text-[#9CA3AF]">Candidate:</span>
                <span className="text-gray-100 font-bold">
                  {modelMeta?.approved_model ? `RandomForestClassifier (${modelMeta.approved_model})` : "—"}
                </span>
              </div>
              <div className="flex justify-between pb-2 border-b border-[rgba(75,85,99,0.2)]">
                <span className="text-[#9CA3AF]">Model Version:</span>
                <span className="text-gray-200">{modelMeta?.approved_model || "—"}</span>
              </div>
              <div className="flex justify-between pb-2 border-b border-[rgba(75,85,99,0.2)]">
                <span className="text-[#9CA3AF]">Feature Schema:</span>
                <span className="text-gray-200">
                  {modelMeta ? `v${modelMeta.schema_version} (14 features)` : "—"}
                </span>
              </div>
              <div className="flex justify-between pb-2 border-b border-[rgba(75,85,99,0.2)]">
                <span className="text-[#9CA3AF]">Precision:</span>
                <span className="text-[#10B981] font-bold">
                  {activeMetrics?.precision !== undefined ? `${(activeMetrics.precision * 100).toFixed(2)}%` : "—"}
                </span>
              </div>
              <div className="flex justify-between pb-2 border-b border-[rgba(75,85,99,0.2)]">
                <span className="text-[#9CA3AF]">Recall:</span>
                <span className="text-[#10B981] font-bold">
                  {activeMetrics?.recall !== undefined ? `${(activeMetrics.recall * 100).toFixed(2)}%` : "—"}
                </span>
              </div>
              <div className="flex justify-between pb-2 border-b border-[rgba(75,85,99,0.2)]">
                <span className="text-[#9CA3AF]">False Positive Rate:</span>
                <span className="text-[#10B981] font-bold">
                  {activeMetrics?.false_positive_rate !== undefined ? `${(activeMetrics.false_positive_rate * 100).toFixed(2)}%` : "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#9CA3AF]">P95 Latency:</span>
                <span className="text-[#00FF9D] font-bold">
                  {activeMetrics?.p95_latency_ms !== undefined ? `${activeMetrics.p95_latency_ms.toFixed(2)} ms` : "—"}
                </span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle className="font-mono">Operator Bearer Token</CardTitle>
                <CardDescription>Authentication for protected administrative API endpoints</CardDescription>
              </div>
              <Lock className="w-5 h-5 text-[#F59E0B]" />
            </CardHeader>
            <CardContent className="space-y-4 text-xs font-mono">
              <p className="text-[#9CA3AF] font-sans">
                SENTRIX enforces backend authorization. Dashboard controls supply this token with HTTP Bearer authentication.
              </p>
              <div className="space-y-2">
                <input
                  suppressHydrationWarning
                  autoComplete="off"
                  data-1p-ignore="true"
                  data-lpignore="true"
                  type="password"
                  value={authToken}
                  onChange={(e) => setAuthTokenState(e.target.value)}
                  placeholder="Enter API token..."
                  className="w-full bg-[#090D16] border border-[rgba(75,85,99,0.4)] rounded-lg px-3 py-2 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
                />
                <Button variant="outline" size="sm" onClick={handleUpdateToken} className="w-full">
                  Update Session Token
                </Button>
                {tokenSavedMsg && (
                  <p className="text-[11px] text-[#00FF9D] text-center font-mono">{tokenSavedMsg}</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
