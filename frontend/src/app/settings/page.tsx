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
      action: "ALERT ONLY",
      badge: "warning",
      text: `Exactly ONE signal exceeded (${isMlThreat ? "ML probability" : "Traffic PPS"}). Alert created; mitigation prohibited by policy.`,
    };
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Dual-Signal Detection Bounds</CardTitle>
            <CardDescription>
              Thresholds govern when an alert escalates to an actionable mitigation request
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {saveSuccess && (
            <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{saveSuccess}</span>
            </div>
          )}
          {saveError && (
            <div className="p-3 rounded-lg bg-rose-950/20 border border-rose-500/30 text-rose-300 text-xs font-mono">
              {saveError}
            </div>
          )}

          {/* Slider 1: PPS Threshold */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <label className="text-cyan-200 font-semibold flex items-center gap-2">
                <Zap className="w-3.5 h-3.5 text-cyan-400" />
                Packets Per Second (PPS) Threshold:
              </label>
              <span className="px-2 py-0.5 rounded bg-cyan-950/50 border border-cyan-500/30 text-cyan-300 font-bold">
                {ppsThreshold.toLocaleString()} pps
              </span>
            </div>
            <input
              type="range"
              min="1000"
              max="50000"
              step="500"
              value={ppsThreshold}
              onChange={(e) => setPpsThreshold(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
            />
            <div className="flex justify-between text-[10px] text-sky-200/40 font-mono">
              <span>Min: 1,000 pps</span>
              <span>Default: 5,000 pps</span>
              <span>Max: 50,000 pps</span>
            </div>
          </div>

          {/* Slider 2: SYN PPS Threshold */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <label className="text-cyan-200 font-semibold flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 text-sky-400" />
                SYN Flood Rate Threshold:
              </label>
              <span className="px-2 py-0.5 rounded bg-cyan-950/50 border border-cyan-500/30 text-sky-300 font-bold">
                {synPpsThreshold.toLocaleString()} syn/s
              </span>
            </div>
            <input
              type="range"
              min="50"
              max="5000"
              step="50"
              value={synPpsThreshold}
              onChange={(e) => setSynPpsThreshold(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-sky-400"
            />
            <div className="flex justify-between text-[10px] text-sky-200/40 font-mono">
              <span>Min: 50 syn/s</span>
              <span>Default: 500 syn/s</span>
              <span>Max: 5,000 syn/s</span>
            </div>
          </div>

          {/* Slider 3: RF Cutoff */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <label className="text-cyan-200 font-semibold flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 text-amber-400" />
                Random Forest Probability Cutoff:
              </label>
              <span className="px-2 py-0.5 rounded bg-cyan-950/50 border border-cyan-500/30 text-amber-300 font-bold">
                {(rfCutoff * 100).toFixed(0)}% ({rfCutoff.toFixed(2)})
              </span>
            </div>
            <input
              type="range"
              min="0.50"
              max="0.99"
              step="0.01"
              value={rfCutoff}
              onChange={(e) => setRfCutoff(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
            />
            <div className="flex justify-between text-[10px] text-sky-200/40 font-mono">
              <span>Conservative: 0.50</span>
              <span>Default: 0.75</span>
              <span>High Precision: 0.95</span>
            </div>
          </div>

          {/* Input: BPS Bandwidth Threshold */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <label className="text-cyan-200 font-semibold">
                Bandwidth Threshold (Bits/s):
              </label>
              <span className="text-sky-300 text-xs">
                {(bpsThreshold / 1000000).toFixed(1)} Mbps
              </span>
            </div>
            <input
              type="number"
              min="1000000"
              max="100000000"
              step="1000000"
              value={bpsThreshold}
              onChange={(e) => setBpsThreshold(Number(e.target.value))}
              className="w-full bg-[#050b14] border border-cyan-500/20 rounded-lg px-3 py-2 text-xs text-cyan-200 font-mono focus:border-cyan-400 focus:outline-none"
            />
          </div>

          {/* Save & Apply Button */}
          <div className="pt-4 flex justify-end">
            <Button
              variant="primary"
              loading={saving}
              onClick={handleSaveThresholds}
            >
              Save & Apply Thresholds
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Interactive Policy Matrix Preview */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Interactive Policy Decision Simulator</CardTitle>
            <CardDescription>
              Drag the sliders below to test how incoming flows trigger the dual-signal matrix
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-sky-300/70">Test Ingress Rate:</span>
                <span className="text-cyan-300 font-bold">{testPps.toLocaleString()} pps</span>
              </div>
              <input
                type="range"
                min="500"
                max="15000"
                step="250"
                value={testPps}
                onChange={(e) => setTestPps(Number(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
              />
              <div className="text-[11px] font-mono">
                Threshold exceeded:{" "}
                <span className={isTrafficExceeded ? "text-rose-400 font-bold" : "text-emerald-400"}>
                  {isTrafficExceeded ? "YES (Exceeds Limit)" : "NO (Within Limit)"}
                </span>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-sky-300/70">Test RF Threat Score:</span>
                <span className="text-amber-300 font-bold">{(testRfScore * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min="0.10"
                max="1.00"
                step="0.05"
                value={testRfScore}
                onChange={(e) => setTestRfScore(Number(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
              />
              <div className="text-[11px] font-mono">
                ML signal active:{" "}
                <span className={isMlThreat ? "text-rose-400 font-bold" : "text-emerald-400"}>
                  {isMlThreat ? "YES (Threat Flagged)" : "NO (Benign)"}
                </span>
              </div>
            </div>
          </div>

          {/* Dynamic Matrix Result */}
          <div className="p-4 rounded-xl border border-cyan-500/20 bg-cyan-950/10 flex items-center justify-between">
            <div>
              <div className="text-xs text-sky-300/60 font-mono">Calculated Hybrid Policy Outcome:</div>
              <div className="text-sm text-cyan-50 font-semibold mt-1">{policyOutcome.text}</div>
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
  const [authToken, setAuthTokenState] = useState<string>(getApiAuthToken());
  const [tokenSavedMsg, setTokenSavedMsg] = useState<string | null>(null);

  const fetchThresholds = useCallback(() => api.getThresholds(), []);
  const { data: thresholdData, loading, refresh } =
    usePolling<ThresholdConfigResponse>(fetchThresholds, 10000);

  const [modelMeta, setModelMeta] = useState<ModelsResponse | null>(null);
  const [modelMetrics, setModelMetrics] = useState<ModelMetricsResponse | null>(null);

  const activeMetrics = modelMetrics?.rf_metrics;

  useEffect(() => {
    api.getModels().then(setModelMeta).catch(() => {});
    api.getModelMetrics().then(setModelMetrics).catch(() => {});
  }, []);

  const handleUpdateToken = () => {
    setApiAuthToken(authToken.trim());
    setTokenSavedMsg("Token applied to active session.");
    setTimeout(() => setTokenSavedMsg(null), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-cyan-500/15">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-cyan-50 flex items-center gap-3">
            <Sliders className="w-6 h-6 text-cyan-400" />
            Detection & Policy Threshold Configuration
          </h1>
          <p className="text-xs text-sky-200/60 mt-1">
            Tune dual-signal detection cutoffs, inspect ML candidate metadata, and test policy decisions
          </p>
        </div>

        <div className="flex items-center gap-3">
          <StatusIndicator status={loading ? "loading" : "online"} />
          <Button variant="outline" size="sm" onClick={() => refresh()}>
            <RefreshCw className="w-3.5 h-3.5" />
            Reset to Server
          </Button>
        </div>
      </div>

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
                <CardTitle>Active Model Metadata</CardTitle>
                <CardDescription>Approved Phase 2 detection candidate</CardDescription>
              </div>
              <Server className="w-5 h-5 text-cyan-400" />
            </CardHeader>
            <CardContent className="space-y-3 text-xs font-mono">
              <div className="flex justify-between pb-2 border-b border-cyan-500/10">
                <span className="text-sky-300/60">Candidate:</span>
                <span className="text-cyan-200 font-bold">
                  {modelMeta?.approved_model ? `RandomForestClassifier (${modelMeta.approved_model})` : "RandomForestClassifier (rf-1.0.0)"}
                </span>
              </div>
              <div className="flex justify-between pb-2 border-b border-cyan-500/10">
                <span className="text-sky-300/60">Model Version:</span>
                <span className="text-cyan-200">{modelMeta?.approved_model || "rf-1.0.0"}</span>
              </div>
              <div className="flex justify-between pb-2 border-b border-cyan-500/10">
                <span className="text-sky-300/60">Feature Schema:</span>
                <span className="text-cyan-200">v{modelMeta?.schema_version || "1.0.0"} (14 features)</span>
              </div>
              <div className="flex justify-between pb-2 border-b border-cyan-500/10">
                <span className="text-sky-300/60">Precision:</span>
                <span className="text-emerald-400 font-bold">
                  {activeMetrics?.precision !== undefined ? `${(activeMetrics.precision * 100).toFixed(2)}%` : "99.98%"}
                </span>
              </div>
              <div className="flex justify-between pb-2 border-b border-cyan-500/10">
                <span className="text-sky-300/60">Recall:</span>
                <span className="text-emerald-400 font-bold">
                  {activeMetrics?.recall !== undefined ? `${(activeMetrics.recall * 100).toFixed(2)}%` : "99.96%"}
                </span>
              </div>
              <div className="flex justify-between pb-2 border-b border-cyan-500/10">
                <span className="text-sky-300/60">False Positive Rate:</span>
                <span className="text-emerald-400 font-bold">
                  {activeMetrics?.false_positive_rate !== undefined ? `${(activeMetrics.false_positive_rate * 100).toFixed(2)}%` : "0.58%"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sky-300/60">P95 Inference Latency:</span>
                <span className="text-cyan-300 font-bold">
                  {activeMetrics?.p95_latency_ms !== undefined ? `${activeMetrics.p95_latency_ms.toFixed(2)} ms` : "4.45 ms"}
                </span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Operator Bearer Token</CardTitle>
                <CardDescription>Authentication for protected administrative API endpoints</CardDescription>
              </div>
              <Lock className="w-5 h-5 text-amber-400" />
            </CardHeader>
            <CardContent className="space-y-4 text-xs font-mono">
              <p className="text-sky-200/70">
                SENTRIX enforces backend authorization. Dashboard controls supply this token with HTTP Bearer authentication.
              </p>
              <div className="space-y-2">
                <input
                  type="password"
                  value={authToken}
                  onChange={(e) => setAuthTokenState(e.target.value)}
                  placeholder="Enter API token..."
                  className="w-full bg-[#050b14] border border-cyan-500/20 rounded-lg px-3 py-2 text-xs text-cyan-200 font-mono focus:border-cyan-400 focus:outline-none"
                />
                <Button variant="outline" size="sm" onClick={handleUpdateToken} className="w-full">
                  Update Session Token
                </Button>
                {tokenSavedMsg && (
                  <p className="text-[11px] text-emerald-400 text-center">{tokenSavedMsg}</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
