"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiError } from "./api";

export interface PollingState<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
  isStale: boolean;
  isDisconnected: boolean;
  lastUpdated: Date | null;
  refresh: (force?: boolean) => Promise<void>;
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

  // Keep latest fetcher in ref to avoid rebuilding interval timers when caller passes inline closures
  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  const isMountedRef = useRef(true);
  const inFlightRef = useRef(false);
  const sequenceRef = useRef(0);

  const runFetch = useCallback(async (force: boolean = false): Promise<void> => {
    if (!force && inFlightRef.current) {
      // Avoid stacking duplicate concurrent network calls
      return;
    }

    inFlightRef.current = true;
    const currentSeq = ++sequenceRef.current;

    try {
      const result = await fetcherRef.current();
      // Drop response if unmounted or if a newer fetch was started in the meantime
      if (!isMountedRef.current || currentSeq !== sequenceRef.current) return;

      setData(result);
      setError(null);
      setFailureCount(0);
      setLastUpdated(new Date());
      setIsStale(false);
    } catch (err: unknown) {
      if (!isMountedRef.current || currentSeq !== sequenceRef.current) return;

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
      if (currentSeq === sequenceRef.current) {
        inFlightRef.current = false;
        if (isMountedRef.current) {
          setLoading(false);
        }
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    if (!enabled) return;

    // Run initial fetch
    void runFetch(true);

    let timer: NodeJS.Timeout | null = null;

    const startTimer = () => {
      if (timer) clearInterval(timer);
      timer = setInterval(() => {
        // Only poll if window/document is active and visible
        if (typeof document !== "undefined" && document.visibilityState === "hidden") {
          return;
        }
        void runFetch(false);
      }, intervalMs);
    };

    startTimer();

    // Listen for tab focus/visibility change to immediately refresh when user returns
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void runFetch(true);
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      isMountedRef.current = false;
      inFlightRef.current = false;
      if (timer) clearInterval(timer);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [intervalMs, enabled, runFetch]);

  const isDisconnected = failureCount >= 2;

  return {
    data,
    loading,
    error,
    isStale,
    isDisconnected,
    lastUpdated,
    refresh: runFetch,
  };
}
