export * from "./models";
export * from "./traffic";
export * from "./alerts";
export * from "./mitigation";
export * from "./config";
export * from "./audit";

export interface HealthResponse {
  status: string;
}

export interface ApiError {
  code: string;
  message: string;
  requestId?: string;
  details?: unknown;
}

