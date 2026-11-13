import { Play } from "lucide-react";

import type { FeedItem } from "../../api/types";
import { formatDate } from "../../lib/format";
import { RelativeTime } from "../ui/Time";
import { Thumbnail } from "./Thumbnail";

export function VideoCard({ item }: { item: FeedItem }) {
  return (
    <article className="group relative flex flex-col overflow-hidden rounded-lg border border-line bg-surface hover:border-line-strong">
      <div className="relative aspect-video w-full">
        <Thumbnail src={item.thumbnail_url} kind="video" className="absolute inset-0 size-full" />
        <span className="absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition group-hover:bg-black/40 group-hover:opacity-100">
          <span className="rounded-full bg-black/70 p-3">
            <Play className="size-5 fill-white text-white" aria-hidden />
          </span>
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-1.5 p-3">
        <h3 className="line-clamp-2 text-sm leading-snug font-semibold text-fg">
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="after:absolute after:inset-0 hover:text-accent focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:-outline-offset-2 focus-visible:after:outline-accent"
          >
            {item.title}
            <span className="sr-only"> (opens on YouTube in a new tab)</span>
          </a>
        </h3>
        <div className="mt-auto flex items-center justify-between gap-2 text-xs text-fg-muted">
          <span className="truncate font-medium">{item.source_name}</span>
          {item.published_at ? (
            <span title={formatDate(item.published_at)} className="shrink-0">
              <RelativeTime iso={item.published_at} />
            </span>
          ) : (
            <span className="shrink-0 text-fg-subtle">date unknown</span>
          )}
        </div>
      </div>
    </article>
  );
}
