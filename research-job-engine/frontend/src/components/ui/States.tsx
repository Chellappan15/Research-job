import { AlertTriangle, Inbox, RotateCw } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError } from "../../api/client";
import { cn } from "../../lib/cn";

export function ErrorState({
  error,
  onRetry,
  compact = false,
}: {
  error: unknown;
  onRetry?: () => void;
  compact?: boolean;
}) {
  const message =
    error instanceof ApiError || error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center gap-3 text-center",
        compact ? "px-4 py-6" : "rounded-lg border border-bad/30 bg-bad-soft px-6 py-10",
      )}
    >
      <AlertTriangle className="size-6 text-bad" aria-hidden />
      <div>
        <p className="text-sm font-medium text-fg">Couldn’t load data</p>
        <p className="mt-1 max-w-md text-sm text-fg-muted">{message}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-md border border-line-strong bg-elevated px-3 py-1.5 text-sm font-medium text-fg hover:bg-hover"
        >
          <RotateCw className="size-3.5" aria-hidden /> Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-line px-6 py-12 text-center">
      <div className="text-fg-subtle">{icon ?? <Inbox className="size-7" aria-hidden />}</div>
      <div>
        <p className="text-sm font-medium text-fg">{title}</p>
        {description && <p className="mt-1 max-w-md text-sm text-fg-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}
