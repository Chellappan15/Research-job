import { useEffect } from "react";

import type { ContentType, FeedParams } from "../api/types";
import { useFeed, useSources } from "../hooks/queries";
import { dayEndExclusiveIso, dayStartIso } from "../lib/format";
import { useUrlState } from "../lib/useUrlState";

const KEYS = ["q", "source", "from", "to"] as const;

/** Shared state for feed-backed pages: URL filters -> backend query params. */
export function useFeedPage(type: ContentType, pageSize: number) {
  const url = useUrlState(KEYS);
  const { q, source, from, to } = url.values;
  const params: FeedParams = {
    type,
    limit: pageSize,
    offset: (url.page - 1) * pageSize,
    q: q || undefined,
    source_id: source ? [source] : undefined,
    since: from ? dayStartIso(from) : undefined,
    until: to ? dayEndExclusiveIso(to) : undefined,
  };
  const feed = useFeed(params);

  // A shared/stale URL can point past the last page (e.g. ?page=9 after narrowing a search):
  // jump to the real last page instead of showing a misleading "no results" state.
  const { setPage } = url;
  const total = feed.data?.total ?? 0;
  const pastEnd = !!feed.data && !feed.isPlaceholderData && feed.data.items.length === 0 && total > 0 && url.page > 1;
  useEffect(() => {
    if (pastEnd) setPage(Math.ceil(total / pageSize));
  }, [pastEnd, total, pageSize, setPage]);

  const sources = useSources();
  const relevantSources = (sources.data ?? []).filter((s) =>
    type === "video" ? s.source_type === "youtube" : s.source_type !== "youtube",
  );
  return { ...url, feed, pastEnd, sources: relevantSources, filtered: KEYS.some((k) => url.values[k]) };
}
