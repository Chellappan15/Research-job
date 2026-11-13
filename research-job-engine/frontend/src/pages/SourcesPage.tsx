import { AlertCircle, Rss } from "lucide-react";

import type { Source } from "../api/types";
import { TableSkeleton } from "../components/content/Skeletons";
import { Badge, SourceTypeBadge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState, ErrorState } from "../components/ui/States";
import { RelativeTime } from "../components/ui/Time";
import { useSources } from "../hooks/queries";
import { formatInterval, formatNumber } from "../lib/format";

function locator(s: Source): string {
  return s.source_type === "youtube" ? (s.channel_id ?? "—") : (s.feed_url ?? "—");
}

function EnabledBadge({ enabled }: { enabled: boolean }) {
  return enabled ? <Badge tone="ok">enabled</Badge> : <Badge>disabled</Badge>;
}

export function SourcesPage() {
  const sources = useSources();
  const data = sources.data ?? [];
  const enabled = data.filter((s) => s.enabled).length;
  return (
    <>
      <PageHeader
        title="Sources"
        description={
          sources.data
            ? `${enabled} of ${data.length} sources enabled`
            : "Configured RSS, GitHub and YouTube sources"
        }
      />
      <Card className="overflow-hidden">
        {sources.isPending ? (
          <TableSkeleton label="Loading sources" />
        ) : sources.isError ? (
          <ErrorState compact error={sources.error} onRetry={() => sources.refetch()} />
        ) : data.length === 0 ? (
          <div className="p-4">
            <EmptyState
              icon={<Rss className="size-7" aria-hidden />}
              title="No sources registered"
              description="Register sources with: python -m app.sources.sync sources.example.json"
            />
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden overflow-x-auto xl:block">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Content sources</caption>
                <thead className="border-b border-line text-xs font-medium tracking-wide text-fg-muted uppercase">
                  <tr>
                    <th scope="col" className="px-4 py-2.5">Name</th>
                    <th scope="col" className="px-4 py-2.5">Type</th>
                    <th scope="col" className="px-4 py-2.5">Status</th>
                    <th scope="col" className="px-4 py-2.5">Last success</th>
                    <th scope="col" className="px-4 py-2.5">Interval</th>
                    <th scope="col" className="px-4 py-2.5 text-right">Items</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {data.map((s) => (
                    <tr key={s.id} className="align-top hover:bg-elevated/40">
                      <td className="max-w-xs px-4 py-3">
                        <div className="font-medium text-fg">{s.name}</div>
                        <div className="truncate font-mono text-xs text-fg-subtle" title={locator(s)}>
                          {locator(s)}
                        </div>
                        {s.last_error && (
                          <div className="mt-1 flex items-start gap-1 text-xs text-bad">
                            <AlertCircle className="mt-0.5 size-3 shrink-0" aria-hidden />
                            <span className="line-clamp-2" title={s.last_error}>{s.last_error}</span>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3"><SourceTypeBadge type={s.source_type} /></td>
                      <td className="px-4 py-3"><EnabledBadge enabled={s.enabled} /></td>
                      <td className="px-4 py-3 text-fg-muted"><RelativeTime iso={s.last_success_at} /></td>
                      <td className="px-4 py-3 font-mono text-xs text-fg-muted">
                        {formatInterval(s.fetch_interval_seconds)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular">{formatNumber(s.item_count)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {/* Mobile cards */}
            <ul className="divide-y divide-line xl:hidden">
              {data.map((s) => (
                <li key={s.id} className="flex flex-col gap-2 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium">{s.name}</span>
                    <EnabledBadge enabled={s.enabled} />
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-fg-muted">
                    <SourceTypeBadge type={s.source_type} />
                    <span>{formatInterval(s.fetch_interval_seconds)}</span>
                    <span aria-hidden>·</span>
                    <span>{formatNumber(s.item_count)} items</span>
                    <span aria-hidden>·</span>
                    <span>last success <RelativeTime iso={s.last_success_at} /></span>
                  </div>
                  {s.last_error && <p className="text-xs text-bad">{s.last_error}</p>}
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
    </>
  );
}
