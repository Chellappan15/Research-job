import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { vi } from "vitest";

import type { FeedItem, IngestionRun, Page, Source, Stats } from "../api/types";

export function renderWithProviders(ui: ReactElement, { route = "/", path = "/" } = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchInterval: false, staleTime: Infinity } },
  });
  const location: { current: string } = { current: route };
  function LocationProbe() {
    const loc = useLocation();
    location.current = loc.pathname + loc.search;
    return null;
  }
  const utils = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path={path} element={<>{ui}<LocationProbe /></>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...utils, client, location };
}

type Handler = (url: URL) => { status?: number; body: unknown } | Promise<never>;

/** Stub global fetch with a URL-based handler; returns the mock to inspect requests. */
export function mockApi(handler: Handler) {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), "http://localhost");
    const res = await handler(url);
    return new Response(JSON.stringify(res.body), {
      status: res.status ?? 200,
      headers: { "content-type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

export const requestedUrls = (fn: ReturnType<typeof mockApi>, path: string): URL[] =>
  fn.mock.calls
    .map(([input]) => new URL(String(input), "http://localhost"))
    .filter((u) => u.pathname === path);

export function makeItem(n: number, overrides: Partial<FeedItem> = {}): FeedItem {
  return {
    id: `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`,
    source_id: "src-1",
    source_name: "Source One",
    type: "article",
    title: `Item ${n}`,
    url: `https://example.com/${n}`,
    summary: `Summary ${n}`,
    thumbnail_url: null,
    published_at: "2026-11-12T20:00:00Z",
    fetched_at: "2026-11-13T04:19:39Z",
    external_id: `ext-${n}`,
    ...overrides,
  };
}

/** Feed page generated from the request's limit/offset, like the backend. */
export function feedPage(url: URL, total: number, make = makeItem): Page<FeedItem> {
  const limit = Number(url.searchParams.get("limit") ?? 20);
  const offset = Number(url.searchParams.get("offset") ?? 0);
  const count = Math.max(0, Math.min(limit, total - offset));
  return {
    items: Array.from({ length: count }, (_, i) => make(offset + i + 1)),
    total,
    limit,
    offset,
  };
}

export const SOURCES: Source[] = [
  {
    id: "src-1",
    name: "Source One",
    source_type: "rss",
    feed_url: "https://one.example/feed",
    channel_id: null,
    enabled: true,
    fetch_interval_seconds: 3600,
    last_success_at: "2026-11-13T04:00:00Z",
    last_error: null,
    item_count: 10,
  },
  {
    id: "src-2",
    name: "Source Two",
    source_type: "github",
    feed_url: "https://github.com/a/b/releases.atom",
    channel_id: null,
    enabled: false,
    fetch_interval_seconds: 21600,
    last_success_at: null,
    last_error: "FetchError: client error (HTTP 404)",
    item_count: 0,
  },
  {
    id: "src-yt",
    name: "Channel",
    source_type: "youtube",
    feed_url: null,
    channel_id: "UCaaaaaaaaaaaaaaaaaaaaaa",
    enabled: true,
    fetch_interval_seconds: 3600,
    last_success_at: null,
    last_error: null,
    item_count: 3,
  },
];

export const STATS: Stats = {
  total_items: 2319,
  items_by_type: { article: 2000, video: 319 },
  items_fetched_last_24h: 57,
  newest_item_at: "2026-11-13T04:19:39Z",
  sources_total: 9,
  sources_enabled: 8,
  sources_with_errors: 1,
  ingestion_runs_by_status: { pending: 1, running: 2, completed: 40, failed: 3 },
};

export function makeRun(n: number, overrides: Partial<IngestionRun> = {}): IngestionRun {
  return {
    id: `run-${n}`,
    source_id: "src-1",
    source_name: "Source One",
    status: "completed",
    scheduled_for: "2026-11-13T04:00:00Z",
    attempt_count: 1,
    max_attempts: 3,
    items_seen: 20,
    items_inserted: 5,
    last_error: null,
    next_attempt_at: "2026-11-13T04:00:00Z",
    created_at: "2026-11-13T04:00:00Z",
    started_at: "2026-11-13T04:00:01Z",
    completed_at: "2026-11-13T04:00:03Z",
    ...overrides,
  };
}
