// Mirrors app/api/feed_schemas.py (backend Pydantic models). Keep in sync.

export type ContentType = "article" | "video";
export type SourceType = "rss" | "youtube" | "github";
export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface FeedItem {
  id: string;
  source_id: string;
  source_name: string;
  type: ContentType;
  title: string;
  url: string;
  summary: string | null;
  thumbnail_url: string | null;
  published_at: string | null;
  fetched_at: string;
  external_id: string;
}

export interface Source {
  id: string;
  name: string;
  source_type: SourceType;
  feed_url: string | null;
  channel_id: string | null;
  enabled: boolean;
  fetch_interval_seconds: number;
  last_success_at: string | null;
  last_error: string | null;
  item_count: number;
}

export interface IngestionRun {
  id: string;
  source_id: string;
  source_name: string;
  status: JobStatus;
  scheduled_for: string;
  attempt_count: number;
  max_attempts: number;
  items_seen: number | null;
  items_inserted: number | null;
  last_error: string | null;
  next_attempt_at: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface Stats {
  total_items: number;
  items_by_type: Partial<Record<ContentType, number>>;
  items_fetched_last_24h: number;
  newest_item_at: string | null;
  sources_total: number;
  sources_enabled: number;
  sources_with_errors: number;
  ingestion_runs_by_status: Partial<Record<JobStatus, number>>;
}

export interface FeedParams {
  limit: number;
  offset: number;
  type?: ContentType;
  source_id?: string[];
  since?: string;
  until?: string;
  q?: string;
}

export interface RunParams {
  limit: number;
  offset: number;
  status?: JobStatus;
  source_id?: string;
}
