/**
 * Typed API Client for SENTRIX REST Endpoints
 * Conforms to PRD Section 7 and docs/api_schemas.md contracts.
 */

import type {
  AlertsListResponse,
  AnalyzeFlowRequest,
  AnalyzeFlowResponse,
  ApiError,
  AuditListResponse,
  CancelMitigationResponse,
  EmergencyDisableResponse,
  FlowObservationRequest,
  FlowObservationResponse,
  HealthResponse,
  MitigationListResponse,
  ModelMetricsResponse,
  ModelsResponse,
  SimulateMitigationRequest,
  SimulateMitigationResponse,
  ThresholdConfigResponse,
  TrafficSummaryResponse,
  UpdateThresholdConfigRequest,
} from "@/types";

export * from "@/types";

// Client configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const DEFAULT_AUTH_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN || "7c4e9f2b1a8d3f6cf1b2c3d4e5f60789";

let currentToken: string = DEFAULT_AUTH_TOKEN;

export function setApiAuthToken(token: string): void {
  currentToken = token;
}

export function getApiAuthToken(): string {
  return currentToken;
}

async function fetchJson<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");

  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  if (currentToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${currentToken}`);
  }

  const url = `${API_BASE_URL}${endpoint}`;

  try {
    const res = await fetch(url, {
      ...options,
      headers,
    });

    if (!res.ok) {
      let errPayload: { error?: { code?: string; message?: string; request_id?: string; details?: unknown } } | undefined;
      try {
        errPayload = (await res.json()) as typeof errPayload;
      } catch {
        throw {
          code: `HTTP_${res.status}`,
          message: res.statusText || "Request failed",
        } as ApiError;
      }

      throw {
        code: errPayload?.error?.code || `HTTP_${res.status}`,
        message: errPayload?.error?.message || "An error occurred",
        requestId: errPayload?.error?.request_id,
        details: errPayload?.error?.details,
      } as ApiError;
    }

    return (await res.json()) as T;
  } catch (err: unknown) {
    if (err && typeof err === "object" && "code" in err) {
      throw err as ApiError;
    }
    const message = err instanceof Error ? err.message : "Could not connect to SENTRIX API backend";
    throw {
      code: "NETWORK_ERROR",
      message,
    } as ApiError;
  }
}

// API methods
export const api = {
  // 1. Health
  getHealth: () => fetchJson<HealthResponse>("/api/v1/health"),

  // 2 & 3. Models
  getModels: () => fetchJson<ModelsResponse>("/api/v1/models"),
  getModelMetrics: (version?: string) =>
    fetchJson<ModelMetricsResponse>(
      version ? `/api/v1/models/metrics?version=${encodeURIComponent(version)}` : "/api/v1/models/metrics"
    ),

  // 4 & 5. Traffic
  ingestFlow: (payload: FlowObservationRequest) =>
    fetchJson<FlowObservationResponse>("/api/v1/traffic/flows", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getTrafficSummary: () => fetchJson<TrafficSummaryResponse>("/api/v1/traffic/summary"),

  // 6. Detection
  analyzeFlow: (payload: AnalyzeFlowRequest) =>
    fetchJson<AnalyzeFlowResponse>("/api/v1/detection/analyze", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // 7. Alerts
  getAlerts: (params?: { limit?: number; offset?: number; severity?: string; target_ip?: string }) => {
    const q = new URLSearchParams();
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.offset) q.set("offset", String(params.offset));
    if (params?.severity) q.set("severity", params.severity);
    if (params?.target_ip) q.set("target_ip", params.target_ip);
    const qs = q.toString() ? `?${q.toString()}` : "";
    return fetchJson<AlertsListResponse>(`/api/v1/alerts${qs}`);
  },

  // 8, 9, 10, 11. Mitigations
  getMitigations: (params?: { limit?: number; offset?: number; state?: string }) => {
    const q = new URLSearchParams();
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.offset) q.set("offset", String(params.offset));
    if (params?.state) q.set("state", params.state);
    const qs = q.toString() ? `?${q.toString()}` : "";
    return fetchJson<MitigationListResponse>(`/api/v1/mitigations${qs}`);
  },
  simulateMitigation: (payload: SimulateMitigationRequest) =>
    fetchJson<SimulateMitigationResponse>("/api/v1/mitigations/simulate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  cancelMitigation: (actionId: string) =>
    fetchJson<CancelMitigationResponse>(`/api/v1/mitigations/${encodeURIComponent(actionId)}/cancel`, {
      method: "POST",
    }),
  emergencyDisable: () =>
    fetchJson<EmergencyDisableResponse>("/api/v1/mitigations/disable", {
      method: "POST",
    }),

  // 12. Audit
  getAudit: (params?: { limit?: number; offset?: number; event_type?: string }) => {
    const q = new URLSearchParams();
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.offset) q.set("offset", String(params.offset));
    if (params?.event_type) q.set("event_type", params.event_type);
    const qs = q.toString() ? `?${q.toString()}` : "";
    return fetchJson<AuditListResponse>(`/api/v1/audit${qs}`);
  },
  getAuditCsvUrl: () => `${API_BASE_URL}/api/v1/audit?format=csv`,

  // 13 & 14. Threshold Config
  getThresholds: () => fetchJson<ThresholdConfigResponse>("/api/v1/config/thresholds"),
  updateThresholds: (payload: UpdateThresholdConfigRequest) =>
    fetchJson<ThresholdConfigResponse>("/api/v1/config/thresholds", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
};
