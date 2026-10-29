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
  Cloud,
  Download,
  Pause,
  Play,
  RefreshCw,
  Server,
  Shield,
  Zap,
} from "@/components/ui/icons";
import { api } from "@/lib/api";
import { formatISTDateTime } from "@/lib/formatters";
import { usePolling } from "@/lib/polling";

export default function IntegrationsPage() {
  const [mounted, setMounted] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [workerToggling, setWorkerToggling] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const fetchKinesisStatus = useCallback(async () => {
    try {
      return await api.getAwsKinesisStatus();
    } catch {
      return null;
    }
  }, []);

  const { data: kinesisData, refresh: refreshKinesis, loading } = usePolling(
    fetchKinesisStatus,
    3000
  );

  const handleStartWorker = async () => {
    setWorkerToggling(true);
    setActionMessage(null);
    try {
      const res = await api.startAwsKinesisWorker();
      setActionMessage(res.message || "Kinesis consumer worker started.");
      await refreshKinesis();
      setTimeout(() => setActionMessage(null), 3500);
    } catch (err: unknown) {
      setActionMessage(err instanceof Error ? err.message : "Failed to start worker");
    } finally {
      setWorkerToggling(false);
    }
  };

  const handleStopWorker = async () => {
    setWorkerToggling(true);
    setActionMessage(null);
    try {
      const res = await api.stopAwsKinesisWorker();
      setActionMessage(res.message || "Kinesis consumer worker stopped.");
      await refreshKinesis();
      setTimeout(() => setActionMessage(null), 3500);
    } catch (err: unknown) {
      setActionMessage(err instanceof Error ? err.message : "Failed to stop worker");
    } finally {
      setWorkerToggling(false);
    }
  };

  const handleDownloadAwsWafJson = async () => {
    try {
      await api.downloadAwsWafConfig();
      setActionMessage("Downloaded AWS WAFv2 rule set (JSON format).");
      setTimeout(() => setActionMessage(null), 3500);
    } catch (err: unknown) {
      setActionMessage(err instanceof Error ? err.message : "Failed to download WAF config");
    }
  };

  const [isTestIngesting, setIsTestIngesting] = useState(false);

  const handleTestIngest = async () => {
    setIsTestIngesting(true);
    try {
      const now = (Date.now() / 1000).toFixed(3);
      const sampleLines = [
        `${now}\t203.0.113.15\t0.035\t200\t1420\tGET\thttps\texample.com\t/api/v1/health\t-\t443\tBOM50-C1\tcf_test_${Date.now()}_1\texample.com\t0.040\tHTTP/2.0\tIPv4\tMozilla/5.0`,
        `${now}\t203.0.113.16\t0.042\t200\t2840\tGET\thttps\texample.com\t/dashboard\t-\t443\tDEL51-C1\tcf_test_${Date.now()}_2\texample.com\t0.048\tHTTP/2.0\tIPv4\tMozilla/5.0`,
        `${now}\t198.51.100.88\t0.012\t200\t890\tGET\thttps\texample.com\t/traffic\t-\t443\tBOM50-C1\tcf_test_${Date.now()}_3\texample.com\t0.015\tHTTP/2.0\tIPv4\tcurl/7.68.0`,
        `${now}\t198.51.100.89\t0.015\t404\t420\tPOST\thttps\texample.com\t/login\t-\t443\tCCU50-C1\tcf_test_${Date.now()}_4\texample.com\t0.018\tHTTP/2.0\tIPv4\tpython-requests`,
        `${now}\t203.0.113.55\t0.065\t200\t5120\tGET\thttps\texample.com\t/api/v1/metrics\t-\t443\tMAA50-C1\tcf_test_${Date.now()}_5\texample.com\t0.070\tHTTP/2.0\tIPv4\tMozilla/5.0`,
        `${now}\t203.0.113.56\t0.030\t200\t3100\tGET\thttps\texample.com\t/overview\t-\t443\tBOM50-C1\tcf_test_${Date.now()}_6\texample.com\t0.032\tHTTP/2.0\tIPv4\tMozilla/5.0`,
        `${now}\t198.51.100.90\t0.018\t500\t650\tGET\thttps\texample.com\t/checkout\t-\t443\tDEL51-C1\tcf_test_${Date.now()}_7\texample.com\t0.022\tHTTP/2.0\tIPv4\tMozilla/5.0`,
      ];
      const res = await api.mockIngestAwsKinesis(sampleLines, kinesisData?.stream_name || "sentrix-cloudfront-realtime-logs");
      setActionMessage(`Test logs ingested: ${res.accepted_count} records sent to telemetry pipeline. Visit /traffic to view live telemetry!`);
      await refreshKinesis();
      setTimeout(() => setActionMessage(null), 5000);
    } catch (err: unknown) {
      setActionMessage(err instanceof Error ? err.message : "Test ingestion failed");
    } finally {
      setIsTestIngesting(false);
    }
  };

  const handleDownloadAwsWafCli = async () => {
    try {
      await api.downloadAwsWafCli();
      setActionMessage("Downloaded AWS WAF deployment script (.sh format).");
      setTimeout(() => setActionMessage(null), 3500);
    } catch (err: unknown) {
      setActionMessage(err instanceof Error ? err.message : "Failed to download WAF script");
    }
  };

  const isWorkerRunning =
    kinesisData?.status === "running" ||
    kinesisData?.status === "connected_awaiting_records" ||
    kinesisData?.status === "receiving_records";
  const isConnected = isWorkerRunning || kinesisData?.status === "healthy";
  const hasError = Boolean(kinesisData?.last_error);
  const totalIngested = kinesisData?.metrics?.records_ingested_total ?? 0;
  const totalDuplicate = kinesisData?.metrics?.records_duplicate_total ?? 0;
  const totalPoison = kinesisData?.metrics?.records_poison_total ?? 0;
  const shards = kinesisData?.shards ? Object.entries(kinesisData.shards) : [];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-gray-800">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
              <Cloud className="w-6 h-6 text-[#00FF9D]" />
              Integrations
            </h1>
            {(() => {
              if (!mounted || !kinesisData) {
                return <Badge variant="outline" className="font-sans text-xs">Stream Standby</Badge>;
              }
              switch (kinesisData.status) {
                case "receiving_records":
                  return <Badge variant="matrix" className="font-sans text-xs">Streaming Live Logs</Badge>;
                case "connected_awaiting_records":
                  return <Badge variant="matrix" className="font-sans text-xs text-cyan-400 border-cyan-400/40">Connected (Awaiting Traffic)</Badge>;
                case "connecting":
                  return <Badge variant="outline" className="font-sans text-xs text-yellow-400 border-yellow-400/40">Connecting...</Badge>;
                case "no_credentials":
                  return <Badge variant="outline" className="font-sans text-xs text-amber-400 border-amber-400/40">AWS Credentials Missing</Badge>;
                case "consumer_disabled":
                  return <Badge variant="outline" className="font-sans text-xs text-gray-400 border-gray-600">Consumer Disabled in Config</Badge>;
                case "access_denied":
                  return <Badge variant="critical" className="font-sans text-xs">IAM Access Denied</Badge>;
                case "stream_unavailable":
                  return <Badge variant="critical" className="font-sans text-xs">Stream Not Found</Badge>;
                case "consumer_error":
                  return <Badge variant="critical" className="font-sans text-xs">Consumer Error</Badge>;
                default:
                  return <Badge variant="outline" className="font-sans text-xs">{kinesisData.status || "Stream Standby"}</Badge>;
              }
            })()}
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Check which external services are connected to SENTRIX and whether they are sending data successfully.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleTestIngest}
            disabled={isTestIngesting}
            className="text-xs font-sans text-[#00FF9D] border-[#00FF9D]/40 hover:bg-[#00FF9D]/10"
          >
            <Zap className={`w-3.5 h-3.5 mr-1 text-[#00FF9D] ${isTestIngesting ? "animate-spin" : ""}`} />
            {isTestIngesting ? "Ingesting..." : "Send Test Telemetry Batch"}
          </Button>

          {isWorkerRunning ? (
            <Button
              variant="danger"
              size="sm"
              onClick={handleStopWorker}
              disabled={workerToggling}
              className="text-xs font-sans"
            >
              <Pause className="w-3.5 h-3.5 mr-1" />
              Stop Consumer Worker
            </Button>
          ) : (
            <Button
              variant="primary"
              size="sm"
              onClick={handleStartWorker}
              disabled={workerToggling}
              className="text-xs font-sans"
            >
              <Play className="w-3.5 h-3.5 mr-1" />
              Start Consumer Worker
            </Button>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={() => void refreshKinesis()}
            disabled={loading}
            className="text-xs font-sans"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-[#00FF9D]" : ""}`} />
            {loading ? "Checking..." : "Check Status"}
          </Button>
        </div>
      </div>

      {actionMessage && (
        <div className="p-3 bg-[#1F2937]/90 border border-[#00FF9D]/40 rounded-lg text-xs text-[#00FF9D] flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          {actionMessage}
        </div>
      )}

      {/* Integration Error Notice */}
      {hasError && (
        <div className="p-4 rounded-xl border border-amber-500/40 bg-amber-500/10 text-amber-200 text-xs flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <div className="font-bold text-amber-100 mb-0.5">Integration Notice:</div>
            <p>{kinesisData?.last_error}</p>
            <p className="text-gray-400 text-[11px] mt-1 font-mono">
              To connect real AWS Kinesis streams in production, attach an IAM role or provide standard AWS credentials.
            </p>
          </div>
        </div>
      )}

      {/* Plain English Explanation Card */}
      <ExplainCard
        title="How External Services Connect to SENTRIX"
        summary="SENTRIX connects directly to Amazon Web Services (AWS) to receive web traffic data in real time and export defense firewall rules:"
        tips={[
          "AWS CloudFront Real-Time Logs: Whenever a visitor requests your website, CloudFront logs it within seconds and streams it to Amazon Kinesis.",
          "Amazon Kinesis Worker: Our worker reads the incoming log stream continuously, removing duplicate records and sending clean telemetry to detection.",
          "AWS WAFv2 Export: One-click export that lets you deploy generated rate limit rules directly to your Amazon CloudFront distributions.",
        ]}
        technicalDetails={
          <div className="space-y-1 text-[11px]">
            <p><strong className="text-gray-200">Data Stream:</strong> Amazon Kinesis Data Streams (ShardIteratorType: LATEST, Bounded batch size: 500).</p>
            <p><strong className="text-gray-200">IAM Auth:</strong> Uses AWS Default Credential Provider Chain (IAM roles on EC2/ECS/EKS, no hardcoded secrets).</p>
            <p><strong className="text-gray-200">De-duplication:</strong> Deduplicates records using CloudFront request IDs (x-edge-request-id) backed by SQLite/PostgreSQL durable event store.</p>
          </div>
        }
      />

      {/* Integration KPI Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="AWS Kinesis Stream"
          value={
            !mounted || kinesisData === null
              ? "Loading..."
              : kinesisData.status === "connected_awaiting_records"
              ? "Connected"
              : kinesisData.status === "receiving_records"
              ? "Streaming Live"
              : kinesisData.status === "no_credentials"
              ? "Needs Credentials"
              : kinesisData.status === "consumer_disabled"
              ? "Disabled"
              : kinesisData.status === "running"
              ? "Active (Polling)"
              : hasError
              ? "Standby"
              : kinesisData.status.replace(/_/g, " ")
          }
          subtitle={mounted ? (kinesisData?.stream_name || "Stream not configured") : "Stream not configured"}
          icon={<Cloud className="w-5 h-5 text-[#00FF9D]" />}
          badge={
            <Badge
              variant={
                !mounted
                  ? "outline"
                  : kinesisData?.status === "connected_awaiting_records"
                  ? "cyan"
                  : kinesisData?.status === "receiving_records"
                  ? "matrix"
                  : hasError
                  ? "warning"
                  : "outline"
              }
            >
              {!mounted
                ? "Offline"
                : kinesisData?.status === "connected_awaiting_records"
                ? "Awaiting Traffic"
                : kinesisData?.status === "receiving_records"
                ? "Active Stream"
                : kinesisData?.status === "no_credentials"
                ? "Missing Keys"
                : kinesisData?.status.replace(/_/g, " ") || "Offline"}
            </Badge>
          }
        />
        <MetricCard
          title="Records Ingested"
          value={kinesisData ? totalIngested.toLocaleString() : "—"}
          subtitle="Real-time access log events"
          icon={<Server className="w-5 h-5 text-[#06B6D4]" />}
        />
        <MetricCard
          title="Duplicates Filtered"
          value={kinesisData ? totalDuplicate.toLocaleString() : "—"}
          subtitle="Prevented double-counting"
          icon={<Shield className="w-5 h-5 text-[#10B981]" />}
          badge={<Badge variant="normal">Safe</Badge>}
        />
        <MetricCard
          title="Malformed Records"
          value={kinesisData ? totalPoison.toLocaleString() : "—"}
          subtitle="Invalid log formats rejected"
          icon={<Zap className="w-5 h-5 text-amber-400" />}
        />
      </div>

      {/* Stream Configuration Summary */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Stream Connection Configuration</CardTitle>
            <CardDescription>Verified settings from the SENTRIX environment</CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-gray-400 block mb-1">Target Stream Name:</span>
              <span className="text-gray-200 font-mono font-bold">
                {kinesisData?.stream_name || "sentrix-cloudfront-realtime-logs"}
              </span>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-gray-400 block mb-1">AWS Region:</span>
              <span className="text-gray-200 font-mono font-bold">
                {kinesisData?.region || "us-east-1"}
              </span>
            </div>
            <div className="p-3 bg-[#111827]/70 border border-gray-800 rounded-lg">
              <span className="text-gray-400 block mb-1">Last Poll Timestamp:</span>
              <span className="text-gray-200 font-mono">
                {mounted && kinesisData?.last_poll_at ? formatISTDateTime(kinesisData.last_poll_at) : "None recorded"}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Shard Replication Status Card */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Active Stream Shards & Delivery Lag</CardTitle>
            <CardDescription>Real-time delivery progress per stream partition</CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          {shards.length === 0 ? (
            <div className="py-8 text-center text-xs text-gray-400 font-sans">
              No active Kinesis shards discovered.{" "}
              {hasError ? "Verify AWS credentials to discover stream shards." : "Start consumer worker to poll shards."}
            </div>
          ) : (
            <div className="divide-y divide-gray-800 text-xs font-mono">
              {shards.map(([shardId, info]) => (
                <div key={shardId} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="text-gray-200 font-bold block">{shardId}</span>
                    <span className="text-[11px] text-gray-400">
                      Last Sequence: {info.last_sequence_number ? `${info.last_sequence_number.slice(0, 16)}...` : "None"}
                    </span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-gray-300">{info.records_processed} records</span>
                    <Badge variant={info.millis_behind_latest < 1000 ? "matrix" : "warning"} className="text-[10px]">
                      {info.millis_behind_latest} ms behind
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* AWS WAFv2 Rule Exporters */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Export Firewall Rules to AWS WAFv2</CardTitle>
            <CardDescription>
              Export active and suggested defense rules for deployment to your Amazon CloudFront web ACLs.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 bg-[#111827]/70 border border-gray-800 rounded-xl space-y-3">
              <div>
                <h4 className="text-xs font-bold text-gray-200">AWS WAFv2 Rule Set (JSON)</h4>
                <p className="text-[11px] text-gray-400 mt-1">
                  Standard JSON payload formatted for the AWS Management Console or CloudFormation.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadAwsWafJson}
                className="text-xs font-sans"
              >
                <Download className="w-3.5 h-3.5 mr-1.5" />
                Download JSON Rules
              </Button>
            </div>

            <div className="p-4 bg-[#111827]/70 border border-gray-800 rounded-xl space-y-3">
              <div>
                <h4 className="text-xs font-bold text-gray-200">AWS CLI Deployment Script</h4>
                <p className="text-[11px] text-gray-400 mt-1">
                  Ready-to-run shell script to deploy rules directly via the <code className="text-gray-300">aws wafv2</code> command-line tool.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadAwsWafCli}
                className="text-xs font-sans"
              >
                <Download className="w-3.5 h-3.5 mr-1.5" />
                Download CLI Script (.sh)
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
