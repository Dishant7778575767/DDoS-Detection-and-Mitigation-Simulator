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
  CreateSimulationRequest,
  EmergencyDisableResponse,
  FlowObservationRequest,
  FlowObservationResponse,
  HealthResponse,
  MitigationListResponse,
  ModelMetricsResponse,
  ModelsResponse,
  SimulateMitigationRequest,
  SimulateMitigationResponse,
  SimulationControlResponse,
  SimulationListResponse,
  SimulationRunResponse,
  SimulationTicksResponse,
  ThresholdConfigResponse,
  TrafficSummaryResponse,
  UpdateThresholdConfigRequest,
} from "@/types";

export * from "@/types";

// Client configuration: Supports direct API connection or secure server-side Vercel proxy
const USE_PROXY = process.env.NEXT_PUBLIC_USE_PROXY === "true";
const API_BASE_URL = USE_PROXY
  ? "/api/proxy"
  : process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const DEFAULT_AUTH_TOKEN =
  process.env.NEXT_PUBLIC_API_TOKEN || "7c4e9f2b1a8d3f6cf1b2c3d4e5f60789";

let currentToken: string =
  typeof window !== "undefined"
    ? localStorage.getItem("sentrix_api_token") || DEFAULT_AUTH_TOKEN
    : DEFAULT_AUTH_TOKEN;

export function setApiAuthToken(token: string): void {
  currentToken = token;
  if (typeof window !== "undefined") {
    try {
      localStorage.setItem("sentrix_api_token", token);
    } catch {
      // Ignored in restricted environments
    }
  }
}

export function getApiAuthToken(): string {
  if (!currentToken && typeof window !== "undefined") {
    currentToken =
      localStorage.getItem("sentrix_api_token") || DEFAULT_AUTH_TOKEN;
  }
  return currentToken || DEFAULT_AUTH_TOKEN;
}

export class SentrixApiError extends Error implements ApiError {
  code: string;
  requestId?: string;
  details?: unknown;

  constructor(
    message: string,
    code: string,
    requestId?: string,
    details?: unknown
  ) {
    super(message);
    this.name = "SentrixApiError";
    this.code = code;
    this.requestId = requestId;
    this.details = details;
    Object.setPrototypeOf(this, SentrixApiError.prototype);
  }
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

  const tokenToUse = currentToken || DEFAULT_AUTH_TOKEN;
  if (tokenToUse && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${tokenToUse}`);
  }

  const url = `${API_BASE_URL}${endpoint}`;

  try {
    const res = await fetch(url, {
      ...options,
      headers,
    });

    if (!res.ok) {
      let errPayload: Record<string, unknown> | undefined;
      try {
        errPayload = (await res.json()) as Record<string, unknown>;
      } catch {
        throw new SentrixApiError(
          res.statusText || "Request failed",
          `HTTP_${res.status}`
        );
      }

      let message = "An error occurred";
      let code = `HTTP_${res.status}`;
      let requestId: string | undefined;
      let details: unknown;

      if (errPayload) {
        if (errPayload.error && typeof errPayload.error === "object") {
          const errObj = errPayload.error as Record<string, unknown>;
          message = (errObj.message as string) || message;
          code = (errObj.code as string) || code;
          requestId = errObj.request_id as string | undefined;
          details = errObj.details;
        } else if (typeof errPayload.detail === "string") {
          message = errPayload.detail;
        } else if (Array.isArray(errPayload.detail)) {
          message = errPayload.detail
            .map((d: { msg?: string }) => d.msg || JSON.stringify(d))
            .join(", ");
        } else if (typeof errPayload.message === "string") {
          message = errPayload.message;
        }
      }

      throw new SentrixApiError(message, code, requestId, details);
    }

    return (await res.json()) as T;
  } catch (err: unknown) {
    if (err instanceof SentrixApiError) {
      throw err;
    }
    const rawMsg = err instanceof Error ? err.message : "";
    const message =
      rawMsg === "Failed to fetch" || !rawMsg
        ? `Could not connect to SENTRIX API backend at ${API_BASE_URL}. Ensure the backend server is running.`
        : rawMsg;
    throw new SentrixApiError(message, "NETWORK_ERROR");
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
  getMitigations: (params?: { limit?: number; offset?: number; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.offset) q.set("offset", String(params.offset));
    if (params?.status) q.set("status", params.status);
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
  emergencyDisable: (enable = false) =>
    fetchJson<EmergencyDisableResponse>(
      `/api/v1/mitigations/disable${enable ? "?enable=true" : ""}`,
      {
        method: "POST",
      }
    ),
  getMitigationStatus: () =>
    fetchJson<{
      emergency_disabled: boolean;
      mode: string;
      shield_active?: boolean;
      active_simulated_count: number;
      max_concurrent_limit: number;
      status: string;
      latest_mitigation?: {
        action_id: string;
        source?: "mitigation" | "simulation_run";
        run_id?: string;
        target_ip: string;
        target_port?: number | null;
        rate_limit_pps: number;
        duration_seconds: number;
        remaining_seconds: number;
        status: string;
        expires_at?: string | null;
      } | null;
      host_ip?: string;
      hostname?: string;
      is_deployed?: boolean;
      environment?: string;
      dns_gateways?: string[];
      protected_gateways?: string[];
      rate_limit_bounds?: {
        min_pps: number;
        max_pps: number;
      };
      duration_bounds?: {
        min_seconds: number;
        max_seconds: number;
      };
      cooldown_ticks?: number;
    }>("/api/v1/mitigations/status"),

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

  // 15. Simulations (Phase 11)
  createSimulation: (payload: CreateSimulationRequest) =>
    fetchJson<SimulationRunResponse>("/api/v1/simulations", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listSimulations: (params?: { status?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.offset) q.set("offset", String(params.offset));
    const qs = q.toString() ? `?${q.toString()}` : "";
    return fetchJson<SimulationListResponse>(`/api/v1/simulations${qs}`);
  },
  getSimulation: (runId: string) =>
    fetchJson<SimulationRunResponse>(`/api/v1/simulations/${encodeURIComponent(runId)}`),
  controlSimulation: (runId: string, action: string) =>
    fetchJson<SimulationControlResponse>(`/api/v1/simulations/${encodeURIComponent(runId)}/control`, {
      method: "POST",
      body: JSON.stringify({ action }),
    }),
  getSimulationTicks: (runId: string, params?: { limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.offset) q.set("offset", String(params.offset));
    const qs = q.toString() ? `?${q.toString()}` : "";
    return fetchJson<SimulationTicksResponse>(`/api/v1/simulations/${encodeURIComponent(runId)}/ticks${qs}`);
  },
  compareSimulations: (runIds: string[]) =>
    fetchJson<Record<string, unknown>>("/api/v1/simulations/compare", {
      method: "POST",
      body: JSON.stringify({ run_ids: runIds }),
    }),
  getSimulationExportUrl: (runId: string, format: "json" | "markdown" | "csv" = "json") =>
    `${API_BASE_URL}/api/v1/simulations/${encodeURIComponent(runId)}/export?format=${format}&token=${encodeURIComponent(currentToken)}`,
  downloadSimulationExport: async (runId: string, format: "csv" | "json" = "csv") => {
    const url = `${API_BASE_URL}/api/v1/simulations/${encodeURIComponent(runId)}/export?format=${format}`;
    const res = await fetch(url, {
      headers: {
        Authorization: `Bearer ${currentToken}`,
      },
    });
    if (!res.ok) {
      throw new Error(`Export download failed: ${res.statusText}`);
    }
    const blob = await res.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = `sentrix_sim_${runId}.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(blobUrl);
  },
  getAuthToken: () => currentToken,
};
