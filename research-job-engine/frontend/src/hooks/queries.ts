import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import type { FeedParams, RunParams } from "../api/types";

/** Monitoring views refresh on an interval; TanStack Query pauses it in background tabs. */
export const POLL_MS = 10_000;
export const JOBS_POLL_MS = 5_000;

export const queryKeys = {
  feed: (p: FeedParams) => ["feed", p] as const,
  sources: ["sources"] as const,
  runs: (p: RunParams) => ["runs", p] as const,
  stats: ["stats"] as const,
  health: ["health"] as const,
};

export function useFeed(params: FeedParams) {
  return useQuery({
    queryKey: queryKeys.feed(params),
    queryFn: ({ signal }) => api.feed(params, signal),
    placeholderData: keepPreviousData,
  });
}

export function useSources() {
  return useQuery({
    queryKey: queryKeys.sources,
    queryFn: ({ signal }) => api.sources(signal),
    staleTime: 60_000,
  });
}

export function useRuns(params: RunParams, pollMs: number | false = JOBS_POLL_MS) {
  return useQuery({
    queryKey: queryKeys.runs(params),
    queryFn: ({ signal }) => api.runs(params, signal),
    placeholderData: keepPreviousData,
    refetchInterval: pollMs,
  });
}

export function useStats(pollMs: number | false = POLL_MS) {
  return useQuery({
    queryKey: queryKeys.stats,
    queryFn: ({ signal }) => api.stats(signal),
    refetchInterval: pollMs,
  });
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => api.health(signal),
    refetchInterval: 30_000,
    retry: false,
  });
}
