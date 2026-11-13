import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { ArticleCard } from "../components/content/ArticleCard";
import { ArticleListSkeleton, VideoGridSkeleton } from "../components/content/Skeletons";
import { VideoCard } from "../components/content/VideoCard";
import { EmptyState, ErrorState } from "../components/ui/States";
import { useFeed } from "../hooks/queries";

export const HOME_ARTICLES = 7; // 1 featured + 6 more
export const HOME_VIDEOS = 4;

function Section({ title, to, children }: { title: string; to: string; children: ReactNode }) {
  return (
    <section className="mb-12" aria-labelledby={`h-${to}`}>
      <div className="mb-4 flex items-end justify-between">
        <h2 id={`h-${to}`} className="text-lg font-semibold tracking-tight">
          {title}
        </h2>
        <Link
          to={to}
          className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline"
        >
          See all <ArrowRight className="size-3.5" aria-hidden />
        </Link>
      </div>
      {children}
    </section>
  );
}

export function HomePage() {
  const articles = useFeed({ type: "article", limit: HOME_ARTICLES, offset: 0 });
  const videos = useFeed({ type: "video", limit: HOME_VIDEOS, offset: 0 });

  return (
    <>
      <div className="mb-10">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">What’s new in AI</h1>
        <p className="mt-2 max-w-2xl text-fg-muted">
          The latest articles, releases and videos from across the AI world, collected in one
          place and updated throughout the day.
        </p>
      </div>

      <Section title="Latest news" to="/news">
        {articles.isPending ? (
          <ArticleListSkeleton rows={4} />
        ) : articles.isError ? (
          <ErrorState error={articles.error} onRetry={() => articles.refetch()} />
        ) : articles.data.items.length === 0 ? (
          <EmptyState title="No articles yet" description="Check back soon." />
        ) : (
          <div className="flex flex-col gap-3">
            <ArticleCard item={articles.data.items[0]!} featured />
            <div className="grid gap-3 md:grid-cols-2">
              {articles.data.items.slice(1).map((item) => (
                <ArticleCard key={item.id} item={item} />
              ))}
            </div>
          </div>
        )}
      </Section>

      <Section title="New videos" to="/videos">
        {videos.isPending ? (
          <VideoGridSkeleton count={HOME_VIDEOS} />
        ) : videos.isError ? (
          <ErrorState error={videos.error} onRetry={() => videos.refetch()} />
        ) : videos.data.items.length === 0 ? (
          <EmptyState title="No videos yet" description="Check back soon." />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {videos.data.items.map((item) => (
              <VideoCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </Section>
    </>
  );
}
