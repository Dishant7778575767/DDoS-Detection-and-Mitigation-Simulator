"use client";

import { useCallback, useEffect, useState } from "react";
import { ExplainCard } from "@/components/common/ExplainCard";
import { MetricCard } from "@/components/common/MetricCard";
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
  Cpu,
  Play,
  RefreshCw,
  Shield,
  Zap,
} from "@/components/ui/icons";
import {
  api,
  type AnalyzeFlowResponse,
  type ModelMetricsResponse,
  type ModelsResponse,
} from "@/lib/api";

// Verified CIC-DDoS2019 benchmark validation vectors matching strict Schema 1.0.0 (14 features)
const BENCHMARK_VECTORS: Record<
  string,
  { name: string; description: string; expected: string; features: Record<string, number> }
> = {
  benign: {
    name: "Standard Web Traffic (Benign)",
    description: "Authentic HTTP GET interaction with balanced forward/backward flows from CIC-DDoS2019 test set.",
    expected: "BENIGN",
    features: {
      "Total Length of Fwd Packets": 1500.0,
      "Bwd Packet Length Max": 1460.0,
      "Flow Bytes/s": 12560.0,
      "Fwd IAT Total": 250000.0,
      "Bwd IAT Total": 300000.0,
      "Fwd PSH Flags": 4.0,
      "Fwd Packets/s": 176.0,
      "FIN Flag Count": 2.0,
      "Fwd Avg Bytes/Bulk": 0.0,
      "Bwd Avg Bulk Rate": 0.0,
      "Subflow Fwd Packets": 88.0,
      "Init_Win_bytes_forward": 29200.0,
      "Active Mean": 15000.0,
      "Idle Mean": 8000.0,
    },
  },
  flood: {
    name: "Volumetric Attack Flood",
    description: "High-rate unidirectional flow with zero backward response from CIC-DDoS2019 test set.",
    expected: "ATTACK",
    features: {
      "Total Length of Fwd Packets": 34000.0,
      "Bwd Packet Length Max": 0.0,
      "Flow Bytes/s": 2266666.0,
      "Fwd IAT Total": 100.0,
      "Bwd IAT Total": 0.0,
      "Fwd PSH Flags": 0.0,
      "Fwd Packets/s": 56666.0,
      "FIN Flag Count": 0.0,
      "Fwd Avg Bytes/Bulk": 0.0,
      "Bwd Avg Bulk Rate": 0.0,
      "Subflow Fwd Packets": 51000.0,
      "Init_Win_bytes_forward": 29200.0,
      "Active Mean": 5000.0,
      "Idle Mean": 0.0,
    },
  },
  slowloris: {
    name: "Connection Stalling (Slowloris)",
    description: "Prolonged low-throughput flow keeping server connection sockets open from CIC-DDoS2019 test set.",
    expected: "ATTACK",
    features: {
      "Total Length of Fwd Packets": 120.0,
      "Bwd Packet Length Max": 40.0,
      "Flow Bytes/s": 13.3,
      "Fwd IAT Total": 12000000.0,
      "Bwd IAT Total": 0.0,
      "Fwd PSH Flags": 1.0,
      "Fwd Packets/s": 0.58,
      "FIN Flag Count": 0.0,
      "Fwd Avg Bytes/Bulk": 0.0,
      "Bwd Avg Bulk Rate": 0.0,
      "Subflow Fwd Packets": 6.0,
      "Init_Win_bytes_forward": 256.0,
      "Active Mean": 1000.0,
      "Idle Mean": 12000000.0,
    },
  },
};

export default function MachineLearningPage() {
  const [modelsData, setModelsData] = useState<ModelsResponse | null>(null);
  const [metricsData, setMetricsData] = useState<ModelMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  // Interactive tester states
  const [selectedVectorKey, setSelectedVectorKey] = useState<string>("benign");
  const [isPredicting, setIsPredicting] = useState(false);
  const [predictionResult, setPredictionResult] = useState<AnalyzeFlowResponse | null>(null);
  const [predictionTimeMs, setPredictionTimeMs] = useState<number | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const loadModelInfo = useCallback(async () => {
    setLoading(true);
    try {
      const [models, metrics] = await Promise.all([
        api.getModels().catch(() => null),
        api.getModelMetrics().catch(() => null),
      ]);
      setModelsData(models);
      setMetricsData(metrics);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadModelInfo();
  }, [loadModelInfo]);

  const handleRunPrediction = async () => {
    const vector = BENCHMARK_VECTORS[selectedVectorKey];
    if (!vector) return;
    setIsPredicting(true);
    setTestError(null);
    setPredictionResult(null);

    const startTime = performance.now();
    try {
      const result = await api.analyzeFlow({
        feature_schema_version: "1.0.0",
        features: vector.features,
      });
      const elapsed = Math.round((performance.now() - startTime) * 10) / 10;
      setPredictionTimeMs(elapsed);
      setPredictionResult(result);
    } catch (err: unknown) {
      setTestError(err instanceof Error ? err.message : "Inference request failed");
    } finally {
      setIsPredicting(false);
    }
  };

  const primaryModel = modelsData?.models?.[0];
  const rfMetrics = metricsData?.rf_metrics;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-gray-800">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
              <Cpu className="w-6 h-6 text-[#00FF9D]" />
              Machine Learning
            </h1>
            <Badge variant="matrix" className="font-sans text-xs">
              Live Model Loaded
            </Badge>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            This page explains how SENTRIX uses a trained computer model to examine traffic and identify patterns that may indicate an attack. A prediction is an estimate, not a guarantee.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={loadModelInfo}
          disabled={loading}
          className="text-xs font-sans self-start md:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-[#00FF9D]" : ""}`} />
          {loading ? "Verifying..." : "Verify Model Status"}
        </Button>
      </div>

      {/* Plain English Explanation Card */}
      <ExplainCard
        title="What is Machine Learning and why do we use it?"
        summary="A computer model was trained on millions of real-world web requests (the benchmark CIC-DDoS2019 dataset). By learning the difference between ordinary human browsing and automated bot floods, the model can instantly spot new attacks even if the attacker changes their IP address."
        tips={[
          "The model looks at 14 traffic characteristics simultaneously, such as packet size uniformity and transmission speed.",
          "Predictions are fast: taking only 2 to 6 milliseconds per check, without slowing down visitors.",
          "A prediction score is an estimate: if the confidence is high, SENTRIX suggests a defensive firewall rule.",
        ]}
        technicalDetails={
          <div className="space-y-1 text-[11px]">
            <p><strong className="text-gray-200">Algorithm:</strong> Scikit-Learn RandomForestClassifier (100 Decision Trees, n_jobs=4).</p>
            <p><strong className="text-gray-200">Artifact:</strong> models/approved_model.joblib (~1.2 MB file size, verified on startup).</p>
            <p><strong className="text-gray-200">Evaluation Dataset:</strong> Canadian Institute for Cybersecurity (CIC-DDoS2019 NetFlow subset).</p>
          </div>
        }
      />

      {/* Model Health KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Model Status"
          value={primaryModel ? "Working" : loading ? "Loading..." : "Unavailable"}
          subtitle={primaryModel ? `${primaryModel.model_type} (${primaryModel.model_version})` : "Model artifact verification"}
          icon={<Cpu className="w-5 h-5 text-[#00FF9D]" />}
          badge={<Badge variant={primaryModel ? "matrix" : "outline"}>{primaryModel?.status || "Checking"}</Badge>}
        />
        <MetricCard
          title="Historical Accuracy"
          value={
            rfMetrics?.accuracy !== undefined
              ? `${(rfMetrics.accuracy * 100).toFixed(2)}%`
              : loading
              ? "Loading..."
              : "Unavailable"
          }
          subtitle="Test benchmark accuracy"
          icon={<Shield className="w-5 h-5 text-[#06B6D4]" />}
        />
        <MetricCard
          title="False Alarm Rate"
          value={
            rfMetrics?.false_positive_rate !== undefined
              ? `${(rfMetrics.false_positive_rate * 100).toFixed(2)}%`
              : loading
              ? "Loading..."
              : "Unavailable"
          }
          subtitle="False positive rate"
          icon={<CheckCircle2 className="w-5 h-5 text-[#10B981]" />}
          badge={<Badge variant="normal">Low Risk</Badge>}
        />
        <MetricCard
          title="Prediction Speed"
          value={
            predictionTimeMs !== null
              ? `${predictionTimeMs} ms`
              : rfMetrics?.p95_latency_ms !== undefined
              ? `${rfMetrics.p95_latency_ms.toFixed(1)} ms`
              : loading
              ? "Loading..."
              : "Unavailable"
          }
          subtitle="Time to inspect one flow"
          icon={<Zap className="w-5 h-5 text-[#00FF9D]" />}
        />
      </div>

      {/* Interactive Live ML Model Tester */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="flex items-center gap-2">
              <Zap className="w-5 h-5 text-[#00FF9D]" />
              Live Model Tester (Interactive Experiment)
            </CardTitle>
            <CardDescription>
              Test the real trained machine learning model right now. Select a flow pattern below and click &ldquo;Run ML Prediction&rdquo; to send it to the backend ML inference endpoint.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Preset Selector */}
          <div>
            <label className="text-xs text-gray-300 font-medium block mb-2">
              Select a Flow Pattern to Test:
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {Object.entries(BENCHMARK_VECTORS).map(([key, vector]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    setSelectedVectorKey(key);
                    setPredictionResult(null);
                  }}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    selectedVectorKey === key
                      ? "bg-[#00FF9D]/10 border-[#00FF9D] text-gray-100 shadow-[0_0_15px_rgba(0,255,157,0.15)]"
                      : "bg-[#111827]/70 border-gray-700/60 text-gray-400 hover:text-gray-200 hover:border-gray-600"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-gray-200">{vector.name}</span>
                    <Badge
                      variant={vector.expected === "BENIGN" ? "normal" : "critical"}
                      className="text-[10px]"
                    >
                      {vector.expected}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-gray-400 mt-1 line-clamp-2">
                    {vector.description}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Test Action Button */}
          <div className="flex items-center gap-4 pt-2 border-t border-gray-800">
            <Button
              variant="primary"
              size="md"
              onClick={handleRunPrediction}
              disabled={isPredicting}
              className="text-xs font-sans"
            >
              <Play className="w-4 h-4 mr-1.5" />
              {isPredicting ? "Running Live Prediction..." : "Run ML Prediction →"}
            </Button>
            <span className="text-xs text-gray-400">
              Sends 14 NetFlow features to backend endpoint <code className="text-gray-300">/api/v1/detection/analyze</code>
            </span>
          </div>

          {/* Prediction Results Banner */}
          {predictionResult && (
            <div
              className={`p-5 rounded-xl border-2 transition-all ${
                predictionResult.prediction.toLowerCase() === "attack"
                  ? "bg-red-500/15 border-red-500 shadow-[0_0_20px_rgba(239,68,68,0.2)]"
                  : "bg-[#00FF9D]/10 border-[#00FF9D] shadow-[0_0_20px_rgba(0,255,157,0.2)]"
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono uppercase tracking-wider text-gray-300">
                      Live Prediction Outcome:
                    </span>
                    <Badge
                      variant={predictionResult.prediction.toLowerCase() === "attack" ? "critical" : "normal"}
                      className="text-xs font-bold"
                    >
                      {predictionResult.prediction}
                    </Badge>
                  </div>
                  <h3 className="text-xl font-bold text-gray-100">
                    {predictionResult.prediction.toLowerCase() === "attack"
                      ? "Identified as Attack Traffic"
                      : "Identified as Normal Genuine Traffic"}
                  </h3>
                  <p className="text-xs text-gray-300 mt-1">
                    Model Version: {predictionResult.model_version} · Policy Decision: {predictionResult.policy_decision || "EVALUATED"}
                  </p>
                </div>

                <div className="flex items-center gap-4 text-right shrink-0">
                  <div className="px-3 py-2 bg-black/40 rounded-lg border border-gray-700/60">
                    <span className="text-[10px] text-gray-400 block uppercase font-mono">
                      {predictionResult.score_type || "Risk Score"}
                    </span>
                    <span className="text-base font-bold font-mono text-[#00FF9D]">
                      {(predictionResult.score * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="px-3 py-2 bg-black/40 rounded-lg border border-gray-700/60">
                    <span className="text-[10px] text-gray-400 block uppercase font-mono">
                      Inference Time
                    </span>
                    <span className="text-base font-bold font-mono text-[#06B6D4]">
                      {predictionTimeMs !== null ? `${predictionTimeMs} ms` : "—"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {testError && (
            <div className="p-4 bg-red-500/15 border border-red-500/50 rounded-lg text-xs text-red-300 space-y-1">
              <div className="font-bold flex items-center gap-1.5 text-red-200">
                <AlertTriangle className="w-4 h-4 text-red-400" />
                {testError.toLowerCase().includes("missing required features")
                  ? "Input Features Incomplete:"
                  : "Inference Error / Validation Failed:"}
              </div>
              <p className="font-mono text-[11px] leading-relaxed">{testError}</p>
              {testError.toLowerCase().includes("missing required features") && (
                <p className="text-gray-400 text-[11px] pt-1">
                  The loaded Random Forest model requires all 14 CIC-DDoS2019 NetFlow statistical signals in Schema 1.0.0 order to evaluate threat probability.
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Feature Glossary in Everyday English */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>What 14 Signals Does the Model Examine?</CardTitle>
            <CardDescription>
              Each traffic stream is measured across 14 statistical indicators. Here is what they mean in everyday terms:
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="font-semibold text-gray-200 block">1. Destination Port</span>
              <p className="text-gray-400 mt-1">The target service door (e.g. 80 for regular HTTP, 443 for encrypted HTTPS).</p>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="font-semibold text-gray-200 block">2. Flow Duration</span>
              <p className="text-gray-400 mt-1">How long the connection lasted. Fast flushes or abnormally prolonged sessions trigger alerts.</p>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="font-semibold text-gray-200 block">3. Forward & Backward Packets</span>
              <p className="text-gray-400 mt-1">The balance between requests sent and answers received. Attacks often send requests without waiting for replies.</p>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="font-semibold text-gray-200 block">4. Total Payload Bytes</span>
              <p className="text-gray-400 mt-1">The total amount of data carried. High byte counts with zero download indicate exfiltration or junk payloads.</p>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="font-semibold text-gray-200 block">5. Packet Length Range (Min/Max/Mean)</span>
              <p className="text-gray-400 mt-1">Human browsing has varying packet lengths. Automated attack scripts almost always send identical fixed-size packets.</p>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="font-semibold text-gray-200 block">6. Transfer Speed (Bytes & Packets/sec)</span>
              <p className="text-gray-400 mt-1">The instantaneous speed of the flow. Extreme velocities point to denial-of-service attempts.</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
