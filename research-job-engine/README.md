# TechPulse

Automated AI news and video aggregation. A **scheduler** queues ingestion jobs for due sources, **workers** fetch RSS/Atom feeds, GitHub release feeds and YouTube channel feeds, normalize and deduplicate the items into PostgreSQL, and the **API** serves the feed.

No LLMs, agents or AI-generated content. Everything runs on the durable PostgreSQL job queue from Milestone 1 (atomic `SKIP LOCKED` claiming, leases, heartbeats, fencing tokens, retries, recovery). No Redis/Celery/Kafka.

## Processes

| Process | Command | Role |
|---|---|---|
| API | `uvicorn app.api.main:app` | REST API |
| Frontend | `cd frontend && npm run dev` | React dashboard (see [`frontend/README.md`](frontend/README.md)) |
| Scheduler | `python -m app.scheduler.main` | enqueues due ingestion jobs; never fetches. Safe to run several. |
| Worker | `python -m app.worker.main` | claims jobs, fetches, stores items. Scale horizontally. |

## Quick start (Docker)

```bash
cp .env.example .env        # set POSTGRES_PASSWORD; keep DATABASE_URL in sync
docker compose up --build   # db -> migrate -> api + worker + scheduler
docker compose run --rm api python -m app.sources.sync sources.example.json
```

Then open http://localhost:8000/docs. Items appear after the first scheduler pass (≤ `SCHEDULER_POLL_SECONDS`) plus fetch time.

## Local

```bash
python -m venv .venv && source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
python -m app.sources.sync sources.example.json
uvicorn app.api.main:app --reload      # terminal 1
python -m app.worker.main              # terminal 2
python -m app.scheduler.main           # terminal 3

export TEST_DATABASE_URL=postgresql+asyncpg://research:change-me@localhost:5432/research_test
pytest -q                              # DISPOSABLE database: schema is dropped/recreated
ruff check . && ruff format --check .
```

## Sources

Registered from JSON with `python -m app.sources.sync <file>` (upsert by `name`; validated):

```json
{"name": "Hugging Face Blog", "source_type": "rss", "feed_url": "https://huggingface.co/blog/feed.xml", "fetch_interval_seconds": 3600}
{"name": "transformers releases", "source_type": "github", "feed_url": "https://github.com/huggingface/transformers/releases.atom"}
{"name": "Two Minute Papers", "source_type": "youtube", "channel_id": "UCbfYPyITQ-7l4upoX8nvctg"}
```

- `rss`: any RSS/Atom URL. `github`: a repo's `releases.atom` / `tags.atom` (parsed as Atom, stored as articles).
- `youtube`: channel ID (`UC…`); fetched from YouTube's public channel feed `https://www.youtube.com/feeds/videos.xml?channel_id=…` (no API key, latest ~15 videos).
- `fetch_interval_seconds` ≥ 60; `enabled: false` pauses a source.
- `sources.example.json` is a starting list: only the GitHub feed was reachability-checked; confirm the others once.

## API

| Endpoint | Notes |
|---|---|
| `GET /api/v1/feed` | `limit` (1–100, default 20), `offset`, `type=article\|video`, `source_id` (repeatable), `since`, `until` (timezone-aware ISO 8601; filters on `published_at`, falling back to `fetched_at`), `q` (full-text search over title + summary across the whole table; supports `"phrases"`, `OR`, `-exclude`; max 200 chars). Newest first. Returns `{items, total, limit, offset}`. |
| `GET /api/v1/feed/{id}` | single item, 404 if unknown |
| `GET /api/v1/sources` | all sources with `item_count`, `last_success_at`, `last_error`; `?enabled=true\|false` |
| `GET /api/v1/ingestion-runs` | ingest jobs (newest first) with status, attempts, `started_at` (latest attempt, from the `claimed` event), `completed_at`, `items_seen`/`items_inserted`, `last_error`; `?status=`, `?source_id=`, pagination |
| `GET /api/v1/stats` | totals by type, last-24h fetch count, source health, runs by status |
| `GET /health` | liveness (no DB access) |
| `GET /health/ready` | readiness: 200 if PostgreSQL is reachable, 503 otherwise |

The Milestone 1 `/api/v1/jobs` endpoints (mock research executor, no AI) are **disabled by default** because `POST` is unauthenticated. Set `ENABLE_LEGACY_JOBS_API=true` to turn them on; the test suite does this to keep exercising the reliability tests.

## Data model (migrations `0002`, `0003`)

- **sources** — `name` (unique), `source_type` (rss/youtube/github), `feed_url` or `channel_id` (DB check per type), `enabled`, `fetch_interval_seconds`, `last_success_at`, `last_error`.
- **content_items** — `source_id`, `content_type` (article/video), `title`, `url`, `canonical_url`, `summary`, `thumbnail_url`, `published_at` (NULL when the feed has none — never invented), `fetched_at`, `external_id`.
  - `search_vector` (migration `0003`): generated `tsvector` (title weight A, summary weight B, English config) with a GIN index, backing `?q=`.
  - Dedup is enforced by the database: `UNIQUE(source_id, external_id)` and `UNIQUE(canonical_url)` (catches the same article syndicated by several feeds). Inserts use `ON CONFLICT DO NOTHING`; first writer wins.
- **research_jobs** (the generic job queue) gains `kind` (`research`|`ingest`), `source_id`, `scheduled_for`, with a partial unique index `(source_id, scheduled_for) WHERE kind='ingest'`.

Canonical URL: lowercase host, `www.` dropped, `https` scheme, default port/fragment/trailing slash removed, `utm_*`/`fbclid`/`gclid`/… removed, query sorted. YouTube items use `https://www.youtube.com/watch?v=<id>` and `external_id = yt:<id>`.

## How it works

**Scheduler.** Every poll runs one statement: for each enabled source with no pending/running ingest job, insert a job for slot `floor(now / interval) * interval` with `ON CONFLICT DO NOTHING`. The unique slot key makes this idempotent across passes and across concurrent scheduler instances; the pending/running check prevents a backlog while workers are down. Uses the database clock.

**Worker.** Unchanged claim/lease/heartbeat/fencing loop. For `kind='ingest'` it calls the ingestor: load source → fetch feed (shared `httpx` client: timeouts, 5 MB cap, content-type check, ≤2 concurrent requests per host) → parse with `feedparser` (in a thread) → normalize → in-batch dedup. Completion is **one fenced transaction**: lock job with fence check → insert items → update `sources.last_success_at` → mark job completed with `{items_seen, items_inserted}` → `ingested` event. A stale worker gets `LeaseLost` and writes nothing.

**Errors and retries.**

| Failure | Behaviour |
|---|---|
| timeout, connection error, 5xx, 408 | retried with exponential backoff up to `INGEST_MAX_ATTEMPTS` |
| 429 / 503 | retried no earlier than `Retry-After` (capped at 1 h) |
| other 4xx, unparseable feed, oversized/binary response, deleted/disabled source | permanent: job `failed` immediately |
| worker crash | lease expires → recovery requeues (counts as an attempt) |

Every failure is stored in the job's `last_error` and the source's `last_error`; one failing source never affects others. Fetches are read-only, so at-least-once re-execution is harmless.

## Configuration

See `.env.example`. Ingestion knobs: `SCHEDULER_POLL_SECONDS` (30), `INGEST_MAX_ATTEMPTS` (3), `FETCH_TIMEOUT_SECONDS` (15), `FETCH_MAX_BYTES`, `FETCH_PER_HOST_CONCURRENCY` (2), `HTTP_USER_AGENT`, `ENABLE_LEGACY_JOBS_API` (default `false`), `DOMAIN` (production compose only), `CORS_ORIGINS` (comma-separated origins for a separately hosted frontend; not needed with the Vite dev proxy), plus the worker settings (`WORKER_CONCURRENCY`, `LEASE_SECONDS`, `HEARTBEAT_SECONDS`, `RETRY_BASE_SECONDS`, `RETRY_MAX_SECONDS`).

## Deploying (production)

`docker-compose.prod.yml` runs the full stack behind **Caddy**, which serves the built dashboard and forwards `/api`, `/health` to FastAPI on the same domain (no CORS needed) with **automatic HTTPS**. Only ports 80/443 are exposed; PostgreSQL and the API stay on the internal Docker network.

```
Internet ──443──▶ web (Caddy: React build + reverse proxy) ──▶ api:8000 ──▶ db
                                                worker ──────┘     scheduler ──▶ db
```

On a Linux server with Docker installed:

```bash
git clone <your repo> techpulse && cd techpulse
cp .env.example .env
#   POSTGRES_PASSWORD=<long random letters+digits>   (also inside DATABASE_URL)
#   DOMAIN=techpulse.yourdomain.com                   (DNS A record → this server)
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml run --rm api python -m app.sources.sync sources.example.json
docker compose -f docker-compose.prod.yml ps          # api should be "healthy"
docker compose -f docker-compose.prod.yml logs -f worker
```

Trial on your own machine: `DOMAIN=localhost` (browser warns about the local certificate) or `DOMAIN=:80` (plain HTTP at http://localhost).

Updating: `git pull && docker compose -f docker-compose.prod.yml up -d --build` (migrations run automatically).
Backups: `docker compose -f docker-compose.prod.yml exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup.sql`.

Hosting the API and frontend on different domains instead: build the frontend with `VITE_API_BASE_URL=https://api.example.com` and set `CORS_ORIGINS=https://example.com` on the backend.

## Known limitations

- No conditional GET (ETag / Last-Modified) yet; every run downloads the full feed.
- Items are never updated after first insert (title edits upstream are not reflected).
- YouTube's public feed only exposes recent uploads; no back-fill.
- Offset pagination (fine at this scale; switch to keyset if the table grows large).
- No retention/cleanup for `content_items` or `job_events`.
- Docker images and compose files are config-validated and the Caddy routing was tested locally, but the full `docker compose` stack has not been run end-to-end in CI.
