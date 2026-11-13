import { SearchX } from "lucide-react";

import { ArticleCard } from "../components/content/ArticleCard";
import { ArticleListSkeleton } from "../components/content/Skeletons";
import { PageHeader } from "../components/ui/PageHeader";
import { Pagination } from "../components/ui/Pagination";
import { EmptyState, ErrorState } from "../components/ui/States";
import { useFeed } from "../hooks/queries";
import { formatNumber } from "../lib/format";
import { useUrlState } from "../lib/useUrlState";

export const SEARCH_PAGE_SIZE = 20;

/** Site-wide search over articles and videos (server-side full-text search). */
export function SearchPage() {
  const { values, page, setPage } = useUrlState(["q"] as const);
  const q = values.q.trim();
  const results = useFeed({
    q: q || undefined,
    limit: SEARCH_PAGE_SIZE,
    offset: (page - 1) * SEARCH_PAGE_SIZE,
  });

  if (!q) {
    return (
      <EmptyState
        icon={<SearchX className="size-7" aria-hidden />}
        title="Search TechPulse"
        description="Type a topic in the search box above, e.g. “diffusion models” or “open-weights”."
      />
    );
  }

  return (
    <>
      <PageHeader
        title={`Results for “${q}”`}
        description={
          results.data
            ? `${formatNumber(results.data.total)} ${results.data.total === 1 ? "result" : "results"}`
            : undefined
        }
      />
      {results.isPending ? (
        <ArticleListSkeleton />
      ) : results.isError ? (
        <ErrorState error={results.error} onRetry={() => results.refetch()} />
      ) : results.data.items.length === 0 ? (
        <EmptyState
          icon={<SearchX className="size-7" aria-hidden />}
          title="Nothing found"
          description="Try fewer or different words."
        />
      ) : (
        <div className={results.isPlaceholderData ? "opacity-60 transition-opacity" : undefined}>
          <div className="mb-5 flex flex-col gap-3">
            {results.data.items.map((item) => (
              <ArticleCard key={item.id} item={item} />
            ))}
          </div>
          <Pagination
            page={page}
            pageSize={SEARCH_PAGE_SIZE}
            total={results.data.total}
            onPageChange={setPage}
            busy={results.isPlaceholderData}
          />
        </div>
      )}
    </>
  );
}
