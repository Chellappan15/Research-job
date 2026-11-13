import { FileText, PlayCircle } from "lucide-react";
import { useState } from "react";

import { cn } from "../../lib/cn";

/** Image with a neutral placeholder when the URL is missing or fails to load. */
export function Thumbnail({
  src,
  kind,
  className,
}: {
  src: string | null;
  kind: "article" | "video";
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const Icon = kind === "video" ? PlayCircle : FileText;
  if (!src || failed) {
    return (
      <div
        data-testid="thumbnail-placeholder"
        className={cn("flex items-center justify-center bg-elevated text-fg-subtle", className)}
      >
        <Icon className="size-7" aria-hidden />
      </div>
    );
  }
  return (
    <img
      src={src}
      alt=""
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className={cn("bg-elevated object-cover", className)}
    />
  );
}
