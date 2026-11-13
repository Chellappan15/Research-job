import { MonitorPlay } from "lucide-react";

import { FeedFilters } from "../components/content/FeedFilters";
import { VideoGridSkeleton } from "../components/content/Skeletons";
import { VideoCard } from "../components/content/VideoCard";
import { PageHeader } from "../components/ui/PageHeader";
import { Pagination } from "../components/ui/Pagination";
import { EmptyState, ErrorState } from "../components/ui/States";
import { formatNumber } from "../lib/format";
import { useFeedPage } from "./useFeedPage";

export const VIDEOS_PAGE_SIZE = 24;

export function VideosPage() {
  const { feed, pastEnd, sources, values, page, setFilter, setPage, clear, filtered } = useFeedPage(
    "video",
    VIDEOS_PAGE_SIZE,
  );
  return (
    <>
      <PageHeader
        title="YouTube Videos"
        description={
          feed.data
            ? `${formatNumber(feed.data.total)} ${filtered ? "matching " : ""}videos, newest first`
            : "Latest uploads from tracked channels"
        }
      />
      <FeedFilters
        values={values}
        sources={sources}
        onChange={setFilter}
        onClear={clear}
        searchPlaceholder="Search all videos by title or description"
      />
      {feed.isPending || pastEnd ? (
        <VideoGridSkeleton />
      ) : feed.isError ? (
        <ErrorState error={feed.error} onRetry={() => feed.refetch()} />
      ) : feed.data.items.length === 0 ? (
        <EmptyState
          icon={<MonitorPlay className="size-7" aria-hidden />}
          title={filtered ? "No videos match these filters" : "No videos yet"}
          description={
            filtered
              ? "Try a different search term, channel or date range."
              : "Add a YouTube source to start collecting videos."
          }
        />
      ) : (
        <div className={feed.isPlaceholderData ? "opacity-60 transition-opacity" : undefined}>
          <div className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {feed.data.items.map((item) => (
              <VideoCard key={item.id} item={item} />
            ))}
          </div>
          <Pagination
            page={page}
            pageSize={VIDEOS_PAGE_SIZE}
            total={feed.data.total}
            onPageChange={(p) => {
              setPage(p);
              window.scrollTo?.({ top: 0 });
            }}
            busy={feed.isPlaceholderData}
          />
        </div>
      )}
    </>
  );
}
