import { formatDateTime, formatRelative } from "../../lib/format";

/** Relative time with the absolute timestamp on hover / for screen readers. */
export function RelativeTime({
  iso,
  fallback = "never",
  className,
}: {
  iso: string | null | undefined;
  fallback?: string;
  className?: string;
}) {
  if (!iso) return <span className={className}>{fallback}</span>;
  return (
    <time dateTime={iso} title={formatDateTime(iso)} className={className}>
      {formatRelative(iso)}
    </time>
  );
}
