/**
 * Real-Time Telemetry & Threat Detection Types for SENTRIX.
 */

export interface LatencyPercentiles {
  p50_ms: number;
  p90_ms: number;
  p95_ms: number;
  p99_ms: number;
  min_ms: number;
  max_ms: number;
  avg_ms: number;
}

export interface StatusCodeDistribution {
  c_2xx: number;
  c_3xx: number;
  c_4xx: number;
  c_5xx: number;
  pct_2xx: number;
  pct_3xx: number;
  pct_4xx: number;
  pct_5xx: number;
  error_rate_pct: number;
}

export interface ClientEntropyMetrics {
  unique_clients: number;
  shannon_entropy: number;
  max_possible_entropy: number;
  entropy_ratio: number;
}

export interface TopUriItem {
  uri: string;
  count: number;
  pct: number;
}

export interface TopClientItem {
  client_ip: string;
  count: number;
  pct: number;
}

export interface LiveTelemetrySummary {
  window_duration_seconds: number;
  total_requests: number;
  requests_per_second: number;
  bytes_per_second: number;
  status_codes: StatusCodeDistribution;
  latencies: LatencyPercentiles;
  client_metrics: ClientEntropyMetrics;
  top_uris: TopUriItem[];
  top_clients?: TopClientItem[];
  top_methods: Record<string, number>;
  is_anomaly: boolean;
}

export interface ThreatClassificationResult {
  threat_type: string;
  severity: "INFO" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  confidence: number;
  is_threat: boolean;
  is_flash_crowd: boolean;
  recommended_action: string;
  z_scores: Record<string, number>;
  current_metrics: Record<string, number>;
  baseline_metrics: Record<string, unknown>;
  reasons: string[];
  targeted_endpoints: string[];
  candidate_target_ips?: string[];
  timestamp: string;
}

export interface DefensiveRule {
  rule_id: string;
  target_ip_or_cidr: string;
  action_type: "BLOCK" | "RATE_LIMIT" | "CHALLENGE_CAPTCHA";
  rate_limit_rps: number;
  burst_capacity: number;
  mode: "DRY_RUN" | "ACTIVE" | "EXPIRED" | "REVOKED";
  created_at: number;
  expires_at: number;
  ttl_seconds: number;
  reason: string;
  approved_by: string | null;
  simulated_blocked_count: number;
  active_blocked_count: number;
}

export interface ProposeDefensiveRulePayload {
  target_ip_or_cidr: string;
  action_type?: "BLOCK" | "RATE_LIMIT" | "CHALLENGE_CAPTCHA";
  rate_limit_rps?: number;
  burst_capacity?: number;
  ttl_seconds?: number;
  reason?: string;
  dry_run?: boolean;
}

