export interface AuditEventItem {
  event_id: string;
  timestamp: string;
  event_type: string;
  action?: string;
  actor: string;
  target?: string;
  details: Record<string, unknown>;
}

export interface AuditListResponse {
  total_count: number;
  total?: number;
  limit: number;
  offset: number;
  events: AuditEventItem[];
}

