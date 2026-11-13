import type {
  FeedItem,
  FeedParams,
  IngestionRun,
  Page,
  RunParams,
  Source,
  Stats,
} from "./types";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type QueryValue = string | number | boolean | undefined | null | readonly string[];

export function buildUrl(path: string, params?: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, v));
    else search.append(key, String(value));
  }
  const qs = search.toString();
  return `${BASE_URL}${path}${qs ? `?${qs}` : ""}`;
}

/** FastAPI returns `detail` as a string or a list of validation errors. */
function describe(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) =>
        [d.loc?.slice(1).join("."), d.msg].filter(Boolean).join(": "),
      )
      .join("; ");
  }
  return status >= 500 ? `Server error (HTTP ${status})` : `Request failed (HTTP ${status})`;
}

export async function apiGet<T>(
  path: string,
  params?: Record<string, QueryValue>,
  signal?: AbortSignal,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(buildUrl(path, params), { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(0, "Cannot reach the TechPulse API. Is the backend running?");
  }
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, describe(res.status, body));
  return body as T;
}

export const api = {
  feed: (p: FeedParams, signal?: AbortSignal) =>
    apiGet<Page<FeedItem>>("/api/v1/feed", { ...p }, signal),
  feedItem: (id: string, signal?: AbortSignal) =>
    apiGet<FeedItem>(`/api/v1/feed/${encodeURIComponent(id)}`, undefined, signal),
  sources: (signal?: AbortSignal) => apiGet<Source[]>("/api/v1/sources", undefined, signal),
  runs: (p: RunParams, signal?: AbortSignal) =>
    apiGet<Page<IngestionRun>>("/api/v1/ingestion-runs", { ...p }, signal),
  stats: (signal?: AbortSignal) => apiGet<Stats>("/api/v1/stats", undefined, signal),
  health: (signal?: AbortSignal) => apiGet<{ status: string }>("/health", undefined, signal),
};
