import type { ReactNode } from "react";

import type { JobStatus, SourceType } from "../../api/types";
import { cn } from "../../lib/cn";

type Tone = "neutral" | "accent" | "ok" | "warn" | "bad";

const TONES: Record<Tone, string> = {
  neutral: "border-line-strong bg-elevated text-fg-muted",
  accent: "border-accent/40 bg-accent-soft text-accent",
  ok: "border-ok/40 bg-ok-soft text-ok",
  warn: "border-warn/40 bg-warn-soft text-warn",
  bad: "border-bad/40 bg-bad-soft text-bad",
};

export function Badge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const STATUS_TONE: Record<JobStatus, Tone> = {
  pending: "warn",
  running: "accent",
  completed: "ok",
  failed: "bad",
};

export function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <Badge tone={STATUS_TONE[status]}>
      <span
        aria-hidden
        className={cn(
          "size-1.5 rounded-full bg-current",
          status === "running" && "animate-pulse",
        )}
      />
      {status}
    </Badge>
  );
}

const SOURCE_LABEL: Record<SourceType, string> = {
  rss: "RSS",
  youtube: "YouTube",
  github: "GitHub",
};

export function SourceTypeBadge({ type }: { type: SourceType }) {
  return <Badge tone={type === "youtube" ? "bad" : type === "github" ? "neutral" : "accent"}>{SOURCE_LABEL[type]}</Badge>;
}
