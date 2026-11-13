import { LoadingRegion, Skeleton } from "../ui/Skeleton";

export function ArticleListSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <LoadingRegion label="Loading articles">
      <div className="flex flex-col gap-3">
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="rounded-lg border border-line bg-surface p-4">
            <Skeleton className="mb-2 h-3 w-48" />
            <Skeleton className="mb-2 h-4 w-3/4" />
            <Skeleton className="h-3 w-full" />
          </div>
        ))}
      </div>
    </LoadingRegion>
  );
}

export function VideoGridSkeleton({ count = 8 }: { count?: number }) {
  return (
    <LoadingRegion label="Loading videos">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: count }, (_, i) => (
          <div key={i} className="overflow-hidden rounded-lg border border-line bg-surface">
            <Skeleton className="aspect-video w-full rounded-none" />
            <div className="p-3">
              <Skeleton className="mb-2 h-4 w-5/6" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          </div>
        ))}
      </div>
    </LoadingRegion>
  );
}

export function TableSkeleton({ rows = 6, label }: { rows?: number; label: string }) {
  return (
    <LoadingRegion label={label}>
      <div className="divide-y divide-line">
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="flex items-center gap-4 px-4 py-3">
            <Skeleton className="h-5 w-20" />
            <Skeleton className="h-4 flex-1" />
            <Skeleton className="h-4 w-24" />
          </div>
        ))}
      </div>
    </LoadingRegion>
  );
}
