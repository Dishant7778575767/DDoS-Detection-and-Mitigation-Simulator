export interface ThresholdConfigResponse {
  version: string;
  pps_threshold: number;
  bps_threshold: number;
  syn_pps_threshold: number;
  rf_probability_threshold: number;
  updated_at?: string;
}

export interface UpdateThresholdConfigRequest {
  pps_threshold?: number;
  bps_threshold?: number;
  syn_pps_threshold?: number;
  rf_probability_threshold?: number;
}

