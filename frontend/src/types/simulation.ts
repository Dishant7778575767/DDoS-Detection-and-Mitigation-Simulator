/**
 * TypeScript types for SENTRIX Simulation Engine (Phase 11)
 */

export type ScenarioType =
  | "syn_flood"
  | "udp_flood"
  | "http_flood"
  | "low_and_slow"
  | "mixed"
  | "flash_crowd";

export type SimulationStatus =
  | "created"
  | "running"
  | "paused"
  | "completed"
  | "interrupted"
  | "cancelled";

export interface VirtualVictimConfig {
  bandwidth_mbps: number;
  cpu_capacity_pps: number;
  max_active_connections: number;
  baseline_latency_ms: number;
  max_latency_ms?: number;
}

export interface ScenarioConfig {
  scenario_type: ScenarioType;
  seed: number;
  duration_seconds: number;
  baseline_pps: number;
  attack_peak_pps: number;
  attack_start_tick: number;
  attack_end_tick: number;
  target_ip?: string;
  target_port?: number;
}

export interface CreateSimulationRequest {
  scenario_type: ScenarioType;
  seed: number;
  duration_seconds: number;
  baseline_pps: number;
  attack_peak_pps: number;
  attack_start_tick: number;
  attack_end_tick: number;
  target_ip?: string;
  target_port?: number;
  victim?: VirtualVictimConfig;
  speed_multiplier?: number;
}

export interface SimulationScorecard {
  time_to_detect_seconds: number | null;
  time_to_mitigate_seconds: number | null;
  attack_traffic_blocked_pct: number | null;
  collateral_legitimate_pct: number | null;
  downtime_seconds: number;
  average_availability_pct: number;
  average_latency_ms: number;
  max_latency_ms: number;
  total_ticks: number;
  attack_ticks: number;
  benign_ticks: number;
  true_positives: number;
  false_positives: number;
  true_negatives: number;
  false_negatives: number;
  precision: number | null;
  recall: number | null;
  false_positive_rate: number | null;
  total_offered_attack_packets: number;
  total_blocked_attack_packets: number;
  total_offered_legitimate_packets: number;
  total_dropped_legitimate_packets: number;
  simulator_version: string;
  model_version: string;
  schema_version: string;
}

export interface SimulationRunResponse {
  run_id: string;
  scenario_type: ScenarioType;
  status: SimulationStatus;
  seed: number;
  total_ticks: number;
  current_tick: number;
  speed_multiplier: number;
  config: {
    scenario: ScenarioConfig;
    victim: VirtualVictimConfig;
  };
  scorecard: SimulationScorecard | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface SimulationRunSummary {
  run_id: string;
  scenario_type: ScenarioType;
  status: SimulationStatus;
  seed: number;
  total_ticks: number;
  current_tick: number;
  speed_multiplier: number;
  created_at: string;
  updated_at: string;
}

export interface SimulationListResponse {
  total_count: number;
  limit: number;
  offset: number;
  runs: SimulationRunSummary[];
}

export interface SimulationControlRequest {
  action: "start" | "pause" | "resume" | "step" | "cancel" | "reset";
}

export interface SimulationControlResponse {
  run_id: string;
  status: SimulationStatus;
  current_tick: number;
  message: string;
}

export interface SimulationTickItem {
  tick: number;
  offered_legit_pps: number;
  offered_attack_pps: number;
  served_legit_pps: number;
  dropped_legit_pps: number;
  dropped_attack_pps: number;
  latency_ms: number;
  availability_pct: number;
  prediction: string;
  policy_action: string;
  active_mitigations_count: number;
  timestamp: string;
}

export interface SimulationTicksResponse {
  run_id: string;
  total_ticks: number;
  ticks: SimulationTickItem[];
}
