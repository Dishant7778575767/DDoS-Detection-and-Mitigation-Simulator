"use client";

import { useCallback, useEffect, useState } from "react";
import { ExplainCard } from "@/components/common/ExplainCard";
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
  loading: boolean;
  onRefresh: () => void;
}

function ThresholdForm({ initialData, loading, onRefresh }: ThresholdFormProps) {
  const [ppsThreshold, setPpsThreshold] = useState<number>(initialData?.pps_threshold ?? 5000);
  const [bpsThreshold, setBpsThreshold] = useState<number>(initialData?.bps_threshold ?? 10000000);
  const [synPpsThreshold, setSynPpsThreshold] = useState<number>(initialData?.syn_pps_threshold ?? 500);
  const [rfCutoff, setRfCutoff] = useState<number>(initialData?.rf_probability_threshold ?? 0.75);

  const [saving, setSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Simulation test sliders for interactive matrix preview
  const [testPps, setTestPps] = useState<number>(4500);
  const [testRfScore, setTestRfScore] = useState<number>(0.65);

  // Keep local form in sync when initialData loads from backend
  useEffect(() => {
    if (initialData) {
      setPpsThreshold(initialData.pps_threshold);
      setBpsThreshold(initialData.bps_threshold);
      setSynPpsThreshold(initialData.syn_pps_threshold);
      setRfCutoff(initialData.rf_probability_threshold);
    }
  }, [initialData]);

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
      setSaveSuccess(`Safety thresholds saved successfully (Version ${res.version})!`);
      onRefresh();
    } catch (err: unknown) {
      setSaveError(`Failed to save: ${getErrorMessage(err, "Please check your authentication token")}`);
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
      action: "ALLOW & MONITOR",
      badge: "normal",
      text: "Traffic and model confidence are both within safe limits. Normal visitors proceed without friction.",
    };
  } else if (isMlThreat && isTrafficExceeded) {
    policyOutcome = {
      action: "SUGGEST PROTECTION",
      badge: "critical",
      text: "BOTH traffic volume and model confidence exceed safety bounds! A defense rule is suggested.",
    };
  } else {
    policyOutcome = {
      action: "FLAG FOR REVIEW",
      badge: "warning",
      text: `Only ONE indicator was exceeded (${isMlThreat ? "Model confidence" : "Traffic surge"}). Logged for review; no blocks applied.`,
    };
  }

  if (loading && !initialData) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-xs text-gray-400">
          Loading active safety thresholds from backend...
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Dual-Signal Safety Thresholds</CardTitle>
            <CardDescription>
              SENTRIX uses two simultaneous checks before suggesting a defense action, preventing false alarms.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {saveSuccess && (
            <div className="p-3.5 rounded-xl bg-[#090D16] border border-[#00FF9D]/40 text-[#00FF9D] text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-[#00FF9D] shrink-0" />
              <span>{saveSuccess}</span>
            </div>
          )}

          {saveError && (
            <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/40 text-[#EF4444] text-xs">
              {saveError}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="field-pps-threshold" className="block text-xs font-medium text-gray-200 mb-1">
                Traffic Surge Limit (Requests/sec)
              </label>
              <input
                id="field-pps-threshold"
                type="number"
                value={ppsThreshold}
                onChange={(e) => setPpsThreshold(Number(e.target.value))}
                className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-2 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
              />
              <span className="text-[10px] text-gray-400">
                Current backend setting: {initialData?.pps_threshold?.toLocaleString() ?? "Loading..."}
              </span>
            </div>

            <div>
              <label htmlFor="field-bps-threshold" className="block text-xs font-medium text-gray-200 mb-1">
                Bandwidth Limit (Bits/sec)
              </label>
              <input
                id="field-bps-threshold"
                type="number"
                value={bpsThreshold}
                onChange={(e) => setBpsThreshold(Number(e.target.value))}
                className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-2 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
              />
              <span className="text-[10px] text-gray-400">
                Current backend setting: {initialData?.bps_threshold?.toLocaleString() ?? "Loading..."}
              </span>
            </div>

            <div>
              <label htmlFor="field-syn-threshold" className="block text-xs font-medium text-gray-200 mb-1">
                Rapid Connection Limit (SYN packets/sec)
              </label>
              <input
                id="field-syn-threshold"
                type="number"
                value={synPpsThreshold}
                onChange={(e) => setSynPpsThreshold(Number(e.target.value))}
                className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-2 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
              />
              <span className="text-[10px] text-gray-400">
                Current backend setting: {initialData?.syn_pps_threshold?.toLocaleString() ?? "Loading..."}
              </span>
            </div>

            <div>
              <label htmlFor="field-rf-cutoff" className="block text-xs font-medium text-gray-200 mb-1">
                Required Model Confidence: {(rfCutoff * 100).toFixed(0)}%
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
              <span className="text-[10px] text-gray-400">
                Current backend setting: {initialData ? `${(initialData.rf_probability_threshold * 100).toFixed(0)}%` : "Loading..."}
              </span>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <Button variant="primary" size="sm" loading={saving} onClick={handleSaveThresholds} className="font-sans text-xs">
              Save Safety Limits
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Interactive Policy Simulation Matrix */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="text-sm flex items-center gap-2">
              <Zap className="w-4 h-4 text-[#00FF9D]" />
              Interactive Policy Preview (Test Your Settings)
            </CardTitle>
            <CardDescription>
              Drag the sliders below to see in real time how your safety thresholds decide when to protect your system.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="slider-test-pps" className="block text-xs text-gray-300">
                Test Traffic Rate: <strong className="text-gray-100 font-mono">{testPps.toLocaleString()} req/s</strong>
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
              <div className="text-[11px]">
                Traffic Limit Exceeded:{" "}
                <span className={isTrafficExceeded ? "text-[#EF4444] font-bold" : "text-[#10B981] font-bold"}>
                  {isTrafficExceeded ? "Yes (Above Limit)" : "No (Normal Range)"}
                </span>
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="slider-test-rf" className="block text-xs text-gray-300">
                Test Model Certainty: <strong className="text-gray-100 font-mono">{(testRfScore * 100).toFixed(0)}%</strong>
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
              <div className="text-[11px]">
                Model Flag Active:{" "}
                <span className={isMlThreat ? "text-[#EF4444] font-bold" : "text-[#10B981] font-bold"}>
                  {isMlThreat ? "Yes (Pattern Flagged)" : "No (Normal Pattern)"}
                </span>
              </div>
            </div>
          </div>

          {/* Dynamic Matrix Result */}
          <div className="p-4 rounded-xl border border-gray-700/60 bg-[#090D16] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <div className="text-xs text-gray-400">Resulting System Action:</div>
              <div className="text-sm text-gray-100 font-semibold mt-1">{policyOutcome.text}</div>
            </div>
            <Badge variant={policyOutcome.badge} className="text-xs px-3 py-1 self-start sm:self-auto font-sans">
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
    loading: thresholdsLoading,
    error: thresholdError,
    isStale,
    isDisconnected,
    refresh,
  } = usePolling<ThresholdConfigResponse>(fetchThresholds, 10000);

  const [modelMeta, setModelMeta] = useState<ModelsResponse | null>(null);
  const [modelMetrics, setModelMetrics] = useState<ModelMetricsResponse | null>(null);
  const [modelLoading, setModelLoading] = useState<boolean>(true);
  const [modelLoadError, setModelLoadError] = useState<string | null>(null);

  const primaryModel = modelMeta?.models?.[0];

  useEffect(() => {
    let ignore = false;
    setModelLoading(true);
    void Promise.allSettled([api.getModels(), api.getModelMetrics()]).then(
      ([modelsResult, metricsResult]) => {
        if (ignore) return;
        setModelLoading(false);

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
    setTokenSavedMsg("Token updated for active session.");
    setTimeout(() => setTokenSavedMsg(null), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-gray-800">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-100 flex items-center gap-3">
            <Sliders className="w-6 h-6 text-[#00FF9D]" />
            Settings
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Review and manage how SENTRIX behaves, including baseline sensitivity, detection limits, and emergency protection controls.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <StatusIndicator
            status={
              isDisconnected
                ? "disconnected"
                : isStale
                ? "stale"
                : thresholdsLoading
                ? "loading"
                : "online"
            }
          />
          <Button variant="outline" size="sm" onClick={() => refresh()} className="text-xs font-sans">
            <RefreshCw className="w-3.5 h-3.5 mr-1" />
            Reload Server Values
          </Button>
        </div>
      </div>

      {(thresholdError || modelLoadError) && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-300">
          {thresholdError && <p>Thresholds: {thresholdError.message}</p>}
          {modelLoadError && <p>Model: {modelLoadError}</p>}
        </div>
      )}

      {/* Plain English Explanation Card */}
      <ExplainCard
        title="Why does SENTRIX use Dual-Signal thresholds?"
        summary="To prevent false alarms, SENTRIX will not suggest blocking traffic unless BOTH the traffic surge limit AND the machine learning confidence limit are crossed at the same time."
        tips={[
          "If traffic spikes but the ML model identifies it as real people (like a viral social media post), NO blocks are suggested.",
          "If the ML model is suspicious but traffic volume is completely normal, SENTRIX logs the event for review without interrupting visitors.",
          "Defense rules are only suggested when a true attack pattern coincides with dangerous traffic volume.",
        ]}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ThresholdForm
            initialData={thresholdData}
            loading={thresholdsLoading}
            onRefresh={refresh}
          />
        </div>

        {/* Right Column: Model Information & API Token */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Active Model Information</CardTitle>
                <CardDescription>Verified detection model in memory</CardDescription>
              </div>
              <Server className="w-5 h-5 text-[#00FF9D]" />
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              <div className="flex justify-between pb-2 border-b border-gray-800">
                <span className="text-gray-400">Model Type:</span>
                <span className="text-gray-100 font-bold font-mono">
                  {primaryModel?.model_type || (modelLoading ? "Loading..." : "None")}
                </span>
              </div>
              <div className="flex justify-between pb-2 border-b border-gray-800">
                <span className="text-gray-400">Version:</span>
                <span className="text-[#00FF9D] font-bold font-mono">
                  {primaryModel?.model_version || (modelLoading ? "Loading..." : "N/A")}
                </span>
              </div>
              <div className="flex justify-between pb-2 border-b border-gray-800">
                <span className="text-gray-400">Benchmark Accuracy:</span>
                <span className="text-[#10B981] font-bold font-mono">
                  {modelMetrics?.rf_metrics?.accuracy !== undefined
                    ? `${(modelMetrics.rf_metrics.accuracy * 100).toFixed(2)}%`
                    : modelLoading
                    ? "Loading..."
                    : "Unavailable"}
                </span>
              </div>
              <div className="flex justify-between pb-2 border-b border-gray-800">
                <span className="text-gray-400">Features Checked:</span>
                <span className="text-[#06B6D4] font-bold font-mono">14 NetFlow Features</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Status:</span>
                <Badge variant={primaryModel?.status === "approved" ? "matrix" : "outline"} className="text-[10px]">
                  {primaryModel?.status || (modelLoading ? "Checking..." : "Unverified")}
                </Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Lock className="w-4 h-4 text-[#00FF9D]" />
                  API Authentication
                </CardTitle>
                <CardDescription>Session token used to authenticate with backend endpoints</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              {tokenSavedMsg && (
                <div className="p-2.5 rounded-lg bg-[rgba(0,255,157,0.12)] border border-[#00FF9D]/40 text-[#00FF9D] flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-[#00FF9D] shrink-0" />
                  <span>{tokenSavedMsg}</span>
                </div>
              )}
              <div>
                <label htmlFor="auth-token-input" className="block text-gray-400 mb-1">
                  API Bearer Token:
                </label>
                <input
                  id="auth-token-input"
                  type="password"
                  value={authToken}
                  onChange={(e) => setAuthTokenState(e.target.value)}
                  placeholder="Paste SENTRIX API Token"
                  className="w-full bg-[#090D16] border border-gray-700/60 rounded-lg px-3 py-2 text-xs text-gray-200 font-mono focus:border-[#00FF9D] focus:outline-none"
                />
              </div>
              <Button variant="outline" size="sm" onClick={handleUpdateToken} className="w-full font-sans text-xs">
                Apply Token
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
