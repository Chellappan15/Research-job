import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Clock,
  FileText,
  Layers,
  Rss,
  Video,
} from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import type { JobStatus } from "../api/types";
import { RunsTable } from "../components/content/RunsTable";
import { TableSkeleton } from "../components/content/Skeletons";
import { Card, CardHeader } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { LoadingRegion, Skeleton } from "../components/ui/Skeleton";
import { EmptyState, ErrorState } from "../components/ui/States";
import { RelativeTime } from "../components/ui/Time";
import { POLL_MS, useFeed, useRuns, useStats } from "../hooks/queries";
import { formatNumber, hostname } from "../lib/format";

function StatTile({
  label,
  value,
  icon,
  hint,
}: {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between text-xs font-medium text-fg-muted">
        {label}
        <span className="text-fg-subtle">{icon}</span>
      </div>
      <div className="mt-2 font-mono text-2xl font-semibold tracking-tight text-fg tabular">
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-fg-muted">{hint}</div>}
    </Card>
  );
}

const STATUS_ORDER: JobStatus[] = ["completed", "running", "pending", "failed"];
const STATUS_COLOR: Record<JobStatus, string> = {
  completed: "bg-ok",
  running: "bg-accent",
  pending: "bg-warn",
  failed: "bg-bad",
};

function RunStatusBar({ counts }: { counts: Partial<Record<JobStatus, number>> }) {
  const total = STATUS_ORDER.reduce((a, s) => a + (counts[s] ?? 0), 0);
  if (total === 0) return <p className="text-sm text-fg-muted">No ingestion runs yet.</p>;
  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full bg-elevated" aria-hidden>
        {STATUS_ORDER.map((s) =>
          counts[s] ? (
            <div key={s} className={STATUS_COLOR[s]} style={{ width: `${((counts[s] ?? 0) / total) * 100}%` }} />
          ) : null,
        )}
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        {STATUS_ORDER.map((s) => (
          <li key={s} className="flex items-center gap-2">
            <span aria-hidden className={`size-2 rounded-full ${STATUS_COLOR[s]}`} />
            <span className="text-fg-muted capitalize">{s}</span>
            <span className="ml-auto font-mono tabular sm:ml-0">{formatNumber(counts[s] ?? 0)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function OverviewPage() {
  const stats = useStats(POLL_MS);
  const latest = useFeed({ limit: 8, offset: 0 });
  const runs = useRuns({ limit: 6, offset: 0 }, POLL_MS);
  const s = stats.data;

  return (
    <>
      <PageHeader
        title="System status"
        description={
          s?.newest_item_at ? (
            <>Newest item <RelativeTime iso={s.newest_item_at} /></>
          ) : (
            "Live ingestion status and latest content"
          )
        }
      />

      {stats.isPending ? (
        <LoadingRegion label="Loading statistics">
          <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <Card key={i} className="p-4">
                <Skeleton className="mb-3 h-3 w-24" />
                <Skeleton className="h-7 w-16" />
              </Card>
            ))}
          </div>
        </LoadingRegion>
      ) : stats.isError ? (
        <div className="mb-6">
          <ErrorState error={stats.error} onRetry={() => stats.refetch()} />
        </div>
      ) : (
        <>
          <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile
              label="Total content"
              value={formatNumber(s!.total_items)}
              icon={<Layers className="size-4" aria-hidden />}
              hint={`+${formatNumber(s!.items_fetched_last_24h)} in last 24h`}
            />
            <StatTile
              label="Articles"
              value={formatNumber(s!.items_by_type.article ?? 0)}
              icon={<FileText className="size-4" aria-hidden />}
            />
            <StatTile
              label="Videos"
              value={formatNumber(s!.items_by_type.video ?? 0)}
              icon={<Video className="size-4" aria-hidden />}
            />
            <StatTile
              label="Active sources"
              value={
                <>
                  {formatNumber(s!.sources_enabled)}
                  <span className="text-base text-fg-subtle"> / {formatNumber(s!.sources_total)}</span>
                </>
              }
              icon={<Rss className="size-4" aria-hidden />}
              hint={
                s!.sources_with_errors > 0 ? (
                  <span className="inline-flex items-center gap-1 text-bad">
                    <AlertTriangle className="size-3" aria-hidden />
                    {s!.sources_with_errors} with errors
                  </span>
                ) : (
                  "no source errors"
                )
              }
            />
          </div>
          <Card className="mb-6">
            <CardHeader title="Ingestion status" icon={<Activity className="size-4 text-fg-muted" aria-hidden />} />
            <div className="p-4">
              <RunStatusBar counts={s!.ingestion_runs_by_status} />
            </div>
          </Card>
        </>
      )}

      <div className="grid gap-6 2xl:grid-cols-5">
        <Card className="2xl:col-span-2">
          <CardHeader
            title="Latest content"
            icon={<Clock className="size-4 text-fg-muted" aria-hidden />}
            action={
              <Link to="/news" className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline">
                All news <ArrowRight className="size-3" aria-hidden />
              </Link>
            }
          />
          {latest.isPending ? (
            <TableSkeleton label="Loading latest content" rows={6} />
          ) : latest.isError ? (
            <ErrorState compact error={latest.error} onRetry={() => latest.refetch()} />
          ) : latest.data.items.length === 0 ? (
            <div className="p-4">
              <EmptyState title="No content yet" description="Nothing has been ingested so far." />
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {latest.data.items.map((item) => (
                <li key={item.id} className="relative px-4 py-3 hover:bg-elevated/40">
                  <div className="mb-0.5 flex items-center gap-2 text-xs text-fg-muted">
                    {item.type === "video" ? (
                      <Video className="size-3 text-bad" aria-label="Video" />
                    ) : (
                      <FileText className="size-3 text-accent" aria-label="Article" />
                    )}
                    <span className="truncate">{item.source_name}</span>
                    <span aria-hidden>·</span>
                    <RelativeTime iso={item.published_at ?? item.fetched_at} className="shrink-0" />
                  </div>
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="line-clamp-2 text-sm font-medium text-fg after:absolute after:inset-0 hover:text-accent"
                    title={hostname(item.url)}
                  >
                    {item.title}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="overflow-hidden 2xl:col-span-3">
          <CardHeader
            title="Recent ingestion runs"
            icon={<Activity className="size-4 text-fg-muted" aria-hidden />}
            action={
              <Link to="/admin/jobs" className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline">
                Job monitor <ArrowRight className="size-3" aria-hidden />
              </Link>
            }
          />
          {runs.isPending ? (
            <TableSkeleton label="Loading recent runs" rows={6} />
          ) : runs.isError ? (
            <ErrorState compact error={runs.error} onRetry={() => runs.refetch()} />
          ) : runs.data.items.length === 0 ? (
            <div className="p-4">
              <EmptyState title="No runs yet" description="The scheduler hasn’t queued any jobs." />
            </div>
          ) : (
            <RunsTable runs={runs.data.items} compact />
          )}
        </Card>
      </div>
    </>
  );
}
