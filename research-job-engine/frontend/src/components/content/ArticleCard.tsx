import { ExternalLink } from "lucide-react";

import type { FeedItem } from "../../api/types";
import { hostname } from "../../lib/format";
import { RelativeTime } from "../ui/Time";
import { Thumbnail } from "./Thumbnail";

export function ArticleCard({ item }: { item: FeedItem }) {
  return (
    <article className="group relative flex gap-4 rounded-lg border border-line bg-surface p-4 hover:border-line-strong hover:bg-elevated/40">
      <div className="min-w-0 flex-1">
        <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-muted">
          <span className="font-medium text-accent">{item.source_name}</span>
          <span aria-hidden>·</span>
          <span className="font-mono">{hostname(item.url)}</span>
          <span aria-hidden>·</span>
          {item.published_at ? (
            <RelativeTime iso={item.published_at} />
          ) : (
            <span title="The feed did not provide a publication date">
              fetched <RelativeTime iso={item.fetched_at} />
            </span>
          )}
        </div>
        <h3 className="text-[15px] leading-snug font-semibold text-fg">
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="after:absolute after:inset-0 after:rounded-lg hover:text-accent focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-accent"
          >
            {item.title}
            <ExternalLink
              className="ml-1.5 inline size-3.5 align-baseline text-fg-subtle opacity-0 group-hover:opacity-100"
              aria-hidden
            />
            <span className="sr-only"> (opens original article in a new tab)</span>
          </a>
        </h3>
        {item.summary ? (
          <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-fg-muted">
            {item.summary}
          </p>
        ) : (
          <p className="mt-1.5 text-sm text-fg-subtle italic">No summary provided by the source.</p>
        )}
      </div>
      {item.thumbnail_url && (
        <Thumbnail
          src={item.thumbnail_url}
          kind="article"
          className="hidden h-20 w-32 shrink-0 rounded-md border border-line sm:block"
        />
      )}
    </article>
  );
}
