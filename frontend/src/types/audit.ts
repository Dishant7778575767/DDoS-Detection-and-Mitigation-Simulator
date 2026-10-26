export interface AuditEventItem {
  event_id: string;
  timestamp: string;
  event_type: string;
  actor: string;
  target?: string;
  details: Record<string, unknown>;
}

export interface AuditListResponse {
  total: number;
  limit: number;
  offset: number;
  events: AuditEventItem[];
}

