import { Newspaper } from "lucide-react";

import { ArticleCard } from "../components/content/ArticleCard";
import { FeedFilters } from "../components/content/FeedFilters";
import { ArticleListSkeleton } from "../components/content/Skeletons";
import { PageHeader } from "../components/ui/PageHeader";
import { Pagination } from "../components/ui/Pagination";
import { EmptyState, ErrorState } from "../components/ui/States";
import { formatNumber } from "../lib/format";
import { useFeedPage } from "./useFeedPage";

export const NEWS_PAGE_SIZE = 20;

export function NewsPage() {
  const { feed, pastEnd, sources, values, page, setFilter, setPage, clear, filtered } = useFeedPage(
    "article",
    NEWS_PAGE_SIZE,
  );
  return (
    <>
      <PageHeader
        title="News Feed"
        description={
          feed.data
            ? `${formatNumber(feed.data.total)} ${filtered ? "matching " : ""}articles, newest first`
            : "Articles from RSS and GitHub sources, newest first"
        }
      />
      <FeedFilters
        values={values}
        sources={sources}
        onChange={setFilter}
        onClear={clear}
        searchPlaceholder="Search all articles by title or summary"
      />
      {feed.isPending || pastEnd ? (
        <ArticleListSkeleton />
      ) : feed.isError ? (
        <ErrorState error={feed.error} onRetry={() => feed.refetch()} />
      ) : feed.data.items.length === 0 ? (
        <EmptyState
          icon={<Newspaper className="size-7" aria-hidden />}
          title={filtered ? "No articles match these filters" : "No articles yet"}
          description={
            filtered
              ? "Try a different search term, source or date range."
              : "Articles appear here once the scheduler and workers have ingested your sources."
          }
          action={
            filtered ? (
              <button type="button" onClick={clear} className="text-sm font-medium text-accent hover:underline">
                Clear filters
              </button>
            ) : undefined
          }
        />
      ) : (
        <div className={feed.isPlaceholderData ? "opacity-60 transition-opacity" : undefined}>
          <div className="mb-5 flex flex-col gap-3">
            {feed.data.items.map((item) => (
              <ArticleCard key={item.id} item={item} />
            ))}
          </div>
          <Pagination
            page={page}
            pageSize={NEWS_PAGE_SIZE}
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
