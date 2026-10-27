export interface AlertItem {
  id?: number;
  alert_id: string;
  detection_id?: number | null;
  severity: "info" | "warning" | "critical" | string;
  title: string;
  description: string;
  source_id: string;
  timestamp: string;
  status: "active" | "resolved" | string;

  // Optional derived fields
  target_ip?: string | null;
  classification?: string;
  trigger_signal?: string;
  rf_probability?: number;
  threshold_exceeded?: boolean;
  traffic_rate_pps?: number;
}

export interface AlertsListResponse {
  total_count: number;
  limit: number;
  offset: number;
  alerts: AlertItem[];
  // alias for backward compatibility:
  total?: number;
}
