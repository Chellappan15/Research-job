# TechPulse dashboard

Developer-focused dashboard for the TechPulse API: React 19 + TypeScript + Vite, Tailwind CSS v4, React Router, TanStack Query, Lucide icons. No other runtime dependencies.

## Run

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 — proxies /api and /health to http://localhost:8000
```

The backend (API, worker, scheduler) must be running; see the root README.

| Script | Purpose |
|---|---|
| `npm run dev` | dev server with API proxy |
| `npm test` | Vitest + Testing Library (fetch is mocked; no backend needed) |
| `npm run typecheck` | `tsc` strict type check |
| `npm run build` | type check + production build to `dist/` |

## Configuration (`frontend/.env`, see `.env.example`)

- `VITE_API_PROXY_TARGET` — where the dev server forwards `/api` and `/health` (default `http://localhost:8000`).
- `VITE_API_BASE_URL` — leave empty to call the API on the same origin. If the built app is hosted on a different origin than the API, set this to the API origin **and** add the frontend origin to the backend's `CORS_ORIGINS`.

## Pages

| Route | Data |
|---|---|
| `/` Overview | `/stats` (totals, article/video split, active sources, run status), latest 8 items, last 6 runs. Polls every 10 s. |
| `/news` News Feed | `/feed?type=article` with server-side search (`q`), source, date range, 20 per page. |
| `/videos` YouTube Videos | `/feed?type=video`, thumbnail grid, 24 per page. |
| `/sources` Sources | `/sources`: type, enabled, last success, interval, item count, last error. |
| `/jobs` Job Monitor | `/ingestion-runs` with status/source filters, started/completed/duration/attempts/items/errors. Polls every 5 s. |

Filters and page number live in the URL (shareable, survive refresh). Changing a filter resets to page 1; a URL pointing past the last page jumps to the last page. Polling pauses in background tabs (TanStack Query default).

## Structure

```
src/
  api/          client.ts (fetch wrapper, ApiError, FastAPI error parsing), types.ts (mirrors backend schemas)
  hooks/        queries.ts (TanStack Query hooks, poll intervals)
  components/
    layout/     AppLayout (sidebar, mobile drawer, skip link, API health dot)
    ui/         Card, Badge/StatusBadge, Skeleton, Error/Empty states, Pagination, form controls, RelativeTime
    content/    ArticleCard, VideoCard, Thumbnail, RunsTable, FeedFilters, skeletons
  pages/        Overview, News, Videos, Sources, Jobs (+ tests)
  lib/          formatting, URL state, debounce
```

## Design notes

- Dark charcoal palette (`--color-canvas #0d1117`, surfaces `#151b23`), 1px subtle borders, blue accent `#4493f8`; tokens in `src/index.css` (`@theme`).
- Inter for UI, JetBrains Mono for numbers/IDs (Google Fonts; falls back to system fonts offline).
- Accessibility: skip link, labelled landmarks, `aria-current` nav, visible focus rings, Escape closes the mobile drawer and returns focus, loading regions use `role="status"`, errors use `role="alert"` with a Retry button, `prefers-reduced-motion` respected.
- Missing data is shown honestly: no publication date → "fetched …"/"date unknown", no summary → explicit note, missing/broken thumbnails → neutral placeholder. All metrics come from the API.
