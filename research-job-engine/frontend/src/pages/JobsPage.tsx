import { Activity, RefreshCw } from "lucide-react";

import type { JobStatus } from "../api/types";
import { RunsTable } from "../components/content/RunsTable";
import { TableSkeleton } from "../components/content/Skeletons";
import { Card } from "../components/ui/Card";
import { SegmentedControl, SourceSelect } from "../components/ui/Controls";
import { PageHeader } from "../components/ui/PageHeader";
import { Pagination } from "../components/ui/Pagination";
import { EmptyState, ErrorState } from "../components/ui/States";
import { JOBS_POLL_MS, useRuns, useSources, useStats } from "../hooks/queries";
import { cn } from "../lib/cn";
import { formatRelative } from "../lib/format";
import { useUrlState } from "../lib/useUrlState";

export const JOBS_PAGE_SIZE = 25;
const STATUSES: ("" | JobStatus)[] = ["", "running", "pending", "completed", "failed"];

export function JobsPage() {
  const { values, page, setFilter, setPage } = useUrlState(["status", "source"] as const);
  const status = (STATUSES as string[]).includes(values.status) ? (values.status as JobStatus | "") : "";
  const runs = useRuns(
    {
      limit: JOBS_PAGE_SIZE,
      offset: (page - 1) * JOBS_PAGE_SIZE,
      status: status || undefined,
      source_id: values.source || undefined,
    },
    JOBS_POLL_MS,
  );
  const stats = useStats(JOBS_POLL_MS);
  const sources = useSources();
  const counts = stats.data?.ingestion_runs_by_status;
  const total = counts ? Object.values(counts).reduce((a, b) => a + (b ?? 0), 0) : undefined;

  return (
    <>
      <PageHeader
        title="Job Monitor"
        description={`Ingestion runs, refreshed every ${JOBS_POLL_MS / 1000}s`}
        actions={
          <div className="flex items-center gap-2 text-xs text-fg-muted" aria-live="polite">
            <RefreshCw
              className={cn("size-3.5", runs.isFetching && "animate-spin text-accent")}
              aria-hidden
            />
            {runs.dataUpdatedAt
              ? `Updated ${formatRelative(new Date(runs.dataUpdatedAt).toISOString())}`
              : "Loading…"}
          </div>
        }
      />
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <SegmentedControl
          label="Filter by status"
          value={status}
          onChange={(v) => setFilter("status", v)}
          options={STATUSES.map((s) => ({
            value: s,
            label: s ? s[0]!.toUpperCase() + s.slice(1) : "All",
            count: s ? counts?.[s] : total,
          }))}
        />
        <div className="w-full sm:w-64">
          <SourceSelect
            sources={sources.data ?? []}
            value={values.source}
            onChange={(v) => setFilter("source", v)}
          />
        </div>
      </div>
      <Card className="mb-5 overflow-hidden">
        {runs.isPending ? (
          <TableSkeleton label="Loading ingestion runs" rows={8} />
        ) : runs.isError ? (
          <ErrorState compact error={runs.error} onRetry={() => runs.refetch()} />
        ) : runs.data.items.length === 0 ? (
          <div className="p-4">
            <EmptyState
              icon={<Activity className="size-7" aria-hidden />}
              title={status || values.source ? "No runs match these filters" : "No ingestion runs yet"}
              description="Runs appear once the scheduler queues jobs for enabled sources."
            />
          </div>
        ) : (
          <RunsTable runs={runs.data.items} />
        )}
      </Card>
      {runs.data && (
        <Pagination
          page={page}
          pageSize={JOBS_PAGE_SIZE}
          total={runs.data.total}
          onPageChange={setPage}
          busy={runs.isPlaceholderData}
        />
      )}
    </>
  );
}
