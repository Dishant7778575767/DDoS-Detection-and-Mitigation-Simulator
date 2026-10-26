export interface MitigationItem {
  action_id: string;
  alert_id?: string;
  target_ip: string;
  action_type: string;
  rate_limit_pps: number;
  duration_seconds: number;
  status?: "proposed" | "simulated" | "active" | "cancelled" | "expired" | string;
  state?: "proposed" | "simulated" | "active" | "cancelled" | "expired" | string;
  mode?: string;
  simulation?: boolean;
  created_at: string;
  updated_at: string;
  expires_at?: string | null;
  cancelled_at?: string | null;
  time_remaining_seconds?: number;
}

export interface MitigationListResponse {
  total_count: number;
  total?: number;
  limit: number;
  offset: number;
  mitigations: MitigationItem[];
}

export interface SimulateMitigationRequest {
  target_ip: string;
  action_type: "rate_limit" | "drop_burst";
  rate_limit_pps?: number;
  duration_seconds?: number;
  reason?: string;
}

export interface SimulateMitigationResponse {
  action_id: string;
  target_ip: string;
  action_type: string;
  rate_limit_pps: number;
  duration_seconds: number;
  state: "simulated";
  simulation: true;
  safety_gate_passed: boolean;
  message: string;
}

export interface CancelMitigationResponse {
  action_id: string;
  status: "cancelled";
  message: string;
}

export interface EmergencyDisableResponse {
  emergency_disabled: boolean;
  message: string;
}

