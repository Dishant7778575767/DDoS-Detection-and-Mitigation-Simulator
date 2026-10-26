export interface FlowObservationRequest {
  source_id: string;
  timestamp: string;
  window_seconds: number;
  feature_schema_version: string;
  features: Record<string, number>;
  target_ip?: string;
}

export interface FlowObservationResponse {
  observation_id: string;
  timestamp: string;
  status: string;
  prediction: {
    prediction: string;
    score: number;
    score_type: string;
    model_version: string;
  };
  policy_decision: {
    action: "monitor" | "alert" | "request_mitigation";
    reason: string;
    trigger_signals: string[];
  };
}

export interface TrafficSeriesPoint {
  time: string;
  pps: number;
  syn_pps: number;
  bps: number;
}

export interface TrafficSummaryResponse {
  total_flows: number;
  recent_flows_10s: number;
  recent_flows_30s: number;
  avg_fwd_pps: number;
  avg_syn_pps: number;
  target_breakdown: Record<string, number>;
  time_series?: TrafficSeriesPoint[];
}

export interface AnalyzeFlowRequest {
  feature_schema_version: string;
  features: Record<string, number>;
}

export interface AnalyzeFlowResponse {
  prediction: string;
  score: number;
  score_type: string;
  model_version: string;
  feature_schema_version: string;
  timestamp: string;
  interpretation: string;
}

