import type { IngestionRun } from "../../api/types";
import { formatDateTime, formatDuration } from "../../lib/format";
import { StatusBadge } from "../ui/Badge";
import { RelativeTime } from "../ui/Time";

function Items({ run }: { run: IngestionRun }) {
  if (run.items_inserted === null) return <span className="text-fg-subtle">—</span>;
  return (
    <span title={`${run.items_inserted} new of ${run.items_seen ?? "?"} seen`}>
      <span className="text-fg">+{run.items_inserted}</span>
      <span className="text-fg-subtle"> / {run.items_seen ?? "?"}</span>
    </span>
  );
}

function ErrorText({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <details className="mt-1 text-xs text-bad">
      <summary className="cursor-pointer truncate marker:text-bad">{error}</summary>
      <pre className="mt-1 font-mono break-words whitespace-pre-wrap text-bad/90">{error}</pre>
    </details>
  );
}

/** Responsive list of ingestion runs (table on md+, stacked rows on mobile). */
export function RunsTable({ runs, compact = false }: { runs: IngestionRun[]; compact?: boolean }) {
  return (
    <>
      <div className="hidden overflow-x-auto xl:block">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Ingestion runs</caption>
          <thead className="border-b border-line text-xs font-medium tracking-wide text-fg-muted uppercase">
            <tr>
              <th scope="col" className="px-4 py-2.5">Status</th>
              <th scope="col" className="px-4 py-2.5">Source</th>
              {!compact && <th scope="col" className="hidden px-4 py-2.5 2xl:table-cell">Scheduled</th>}
              {!compact && <th scope="col" className="px-4 py-2.5">Started</th>}
              <th scope="col" className="px-4 py-2.5">{compact ? "Finished" : "Completed"}</th>
              {!compact && <th scope="col" className="hidden px-4 py-2.5 2xl:table-cell">Duration</th>}
              {!compact && <th scope="col" className="px-4 py-2.5">Attempts</th>}
              <th scope="col" className="px-4 py-2.5 text-right">Items</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {runs.map((run) => (
              <tr key={run.id} className="align-top hover:bg-elevated/40">
                <td className="px-4 py-3"><StatusBadge status={run.status} /></td>
                <td className="max-w-xs px-4 py-3">
                  <div className="font-medium text-fg">{run.source_name}</div>
                  <ErrorText error={run.last_error} />
                  {run.status === "pending" && run.attempt_count > 0 && (
                    <div className="mt-1 text-xs text-warn">
                      retry <RelativeTime iso={run.next_attempt_at} />
                    </div>
                  )}
                </td>
                {!compact && (
                  <td className="hidden px-4 py-3 whitespace-nowrap text-fg-muted 2xl:table-cell" title={formatDateTime(run.scheduled_for)}>
                    <RelativeTime iso={run.scheduled_for} />
                  </td>
                )}
                {!compact && (
                  <td className="px-4 py-3 whitespace-nowrap text-fg-muted"><RelativeTime iso={run.started_at} fallback="—" /></td>
                )}
                <td className="px-4 py-3 whitespace-nowrap text-fg-muted"><RelativeTime iso={run.completed_at} fallback="—" /></td>
                {!compact && (
                  <td className="hidden px-4 py-3 font-mono text-xs text-fg-muted 2xl:table-cell">
                    {formatDuration(run.started_at, run.completed_at)}
                  </td>
                )}
                {!compact && (
                  <td className="px-4 py-3 font-mono text-xs text-fg-muted tabular">
                    {run.attempt_count}/{run.max_attempts}
                  </td>
                )}
                <td className="px-4 py-3 text-right font-mono text-xs whitespace-nowrap tabular"><Items run={run} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="divide-y divide-line xl:hidden">
        {runs.map((run) => (
          <li key={run.id} className="flex flex-col gap-1.5 p-4">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-medium">{run.source_name}</span>
              <StatusBadge status={run.status} />
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-fg-muted">
              <span>started <RelativeTime iso={run.started_at} fallback="—" /></span>
              <span>done <RelativeTime iso={run.completed_at} fallback="—" /></span>
              {!compact && <span className="font-mono">{formatDuration(run.started_at, run.completed_at)}</span>}
              <span className="font-mono">try {run.attempt_count}/{run.max_attempts}</span>
              <span className="font-mono"><Items run={run} /></span>
            </div>
            <ErrorText error={run.last_error} />
          </li>
        ))}
      </ul>
    </>
  );
}
