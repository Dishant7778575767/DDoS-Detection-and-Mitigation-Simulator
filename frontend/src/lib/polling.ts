"use client";

import { useCallback, useEffect, useState } from "react";
import type { ApiError } from "./api";

export interface PollingState<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
  isStale: boolean;
  isDisconnected: boolean;
  lastUpdated: Date | null;
  refresh: () => Promise<void>;
}

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number = 3000,
  enabled: boolean = true
): PollingState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [failureCount, setFailureCount] = useState<number>(0);
  const [isStale, setIsStale] = useState<boolean>(false);

  const execute = useCallback(async () => {
    try {
      const result = await fetcher();
      setData(result);
      setError(null);
      setFailureCount(0);
      setLastUpdated(new Date());
      setIsStale(false);
    } catch (err: unknown) {
      if (err && typeof err === "object" && "code" in err) {
        setError(err as ApiError);
      } else {
        setError({
          code: "UNKNOWN_ERROR",
          message: err instanceof Error ? err.message : "Polling failed",
        });
      }
      setFailureCount((prev) => prev + 1);
      setIsStale(true);
    } finally {
      setLoading(false);
    }
  }, [fetcher]);

  useEffect(() => {
    if (!enabled) return;

    let ignore = false;
    const fetchAsync = async () => {
      try {
        const result = await fetcher();
        if (!ignore) {
          setData(result);
          setError(null);
          setFailureCount(0);
          setLastUpdated(new Date());
          setIsStale(false);
          setLoading(false);
        }
      } catch (err: unknown) {
        if (!ignore) {
          if (err && typeof err === "object" && "code" in err) {
            setError(err as ApiError);
          } else {
            setError({
              code: "UNKNOWN_ERROR",
              message: err instanceof Error ? err.message : "Polling failed",
            });
          }
          setFailureCount((prev) => prev + 1);
          setIsStale(true);
          setLoading(false);
        }
      }
    };

    // Defer initial execution via microtask
    const timeout = setTimeout(() => {
      void fetchAsync();
    }, 0);

    const timer = setInterval(() => {
      void fetchAsync();
    }, intervalMs);

    return () => {
      ignore = true;
      clearTimeout(timeout);
      clearInterval(timer);
    };
  }, [fetcher, intervalMs, enabled]);

  const isDisconnected = failureCount >= 2;

  return {
    data,
    loading,
    error,
    isStale,
    isDisconnected,
    lastUpdated,
    refresh: execute,
  };
}
