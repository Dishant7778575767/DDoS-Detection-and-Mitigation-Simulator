export interface ModelSummary {
  model_version: string;
  model_type: string;
  status: string;
  schema_version: string;
}

export interface ModelsResponse {
  approved_model: string;
  schema_version: string;
  models: ModelSummary[];
  active_model?: string;
}

export interface CandidateMetrics {
  model_name: string;
  schema_version: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  false_positive_rate: number;
  p95_latency_ms: number;
  confusion_matrix?: number[][];
  training_time_seconds?: number;
  calibrated_threshold?: number;
  score_convention?: string;
}

export interface ModelMetricsResponse {
  dataset: string;
  schema_version: string;
  rf_metrics?: CandidateMetrics;
  iforest_metrics?: CandidateMetrics;
}

