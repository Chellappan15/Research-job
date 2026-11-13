import { ExternalLink, PlayCircle } from "lucide-react";

import type { FeedItem } from "../../api/types";
import { cn } from "../../lib/cn";
import { hostname } from "../../lib/format";
import { RelativeTime } from "../ui/Time";
import { Thumbnail } from "./Thumbnail";

/** Reader-facing card for one item. `featured` renders the large lead story on the home page. */
export function ArticleCard({ item, featured = false }: { item: FeedItem; featured?: boolean }) {
  const isVideo = item.type === "video";
  return (
    <article
      className={cn(
        "group relative flex gap-4 rounded-xl border border-line bg-surface hover:border-line-strong hover:bg-elevated/40",
        featured ? "flex-col p-0 md:flex-row-reverse" : "p-4",
      )}
    >
      {featured && item.thumbnail_url && (
        <Thumbnail
          src={item.thumbnail_url}
          kind={isVideo ? "video" : "article"}
          className="aspect-video w-full shrink-0 rounded-t-xl md:aspect-auto md:min-h-56 md:w-2/5 md:rounded-t-none md:rounded-r-xl"
        />
      )}
      <div className={cn("min-w-0 flex-1", featured && "p-5 md:p-6")}>
        <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-muted">
          {isVideo && (
            <span className="inline-flex items-center gap-1 font-medium text-bad">
              <PlayCircle className="size-3.5" aria-hidden /> Video
            </span>
          )}
          <span className="font-medium text-accent">{item.source_name}</span>
          <span aria-hidden>·</span>
          <span>{hostname(item.url)}</span>
          <span aria-hidden>·</span>
          {item.published_at ? (
            <RelativeTime iso={item.published_at} />
          ) : (
            <span>
              added <RelativeTime iso={item.fetched_at} />
            </span>
          )}
        </div>
        <h3
          className={cn(
            "leading-snug font-semibold text-fg",
            featured ? "text-xl md:text-2xl" : "text-[15px]",
          )}
        >
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="after:absolute after:inset-0 after:rounded-xl hover:text-accent focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-accent"
          >
            {item.title}
            <ExternalLink
              className="ml-1.5 inline size-3.5 align-baseline text-fg-subtle opacity-0 group-hover:opacity-100"
              aria-hidden
            />
            <span className="sr-only">
              {isVideo ? " (opens on YouTube in a new tab)" : " (opens original article in a new tab)"}
            </span>
          </a>
        </h3>
        {item.summary && (
          <p
            className={cn(
              "mt-1.5 leading-relaxed text-fg-muted",
              featured ? "line-clamp-4 text-[15px]" : "line-clamp-2 text-sm",
            )}
          >
            {item.summary}
          </p>
        )}
      </div>
      {!featured && item.thumbnail_url && (
        <Thumbnail
          src={item.thumbnail_url}
          kind={isVideo ? "video" : "article"}
          className="hidden h-20 w-32 shrink-0 rounded-md border border-line sm:block"
        />
      )}
    </article>
  );
}
