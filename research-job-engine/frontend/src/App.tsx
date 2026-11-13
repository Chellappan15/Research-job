import { Navigate, Route, Routes } from "react-router";

import { AdminLayout } from "./components/layout/AdminLayout";
import { SiteLayout } from "./components/layout/SiteLayout";
import { AboutPage } from "./pages/AboutPage";
import { HomePage } from "./pages/HomePage";
import { JobsPage } from "./pages/JobsPage";
import { NewsPage } from "./pages/NewsPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { OverviewPage } from "./pages/OverviewPage";
import { SearchPage } from "./pages/SearchPage";
import { SourcesPage } from "./pages/SourcesPage";
import { VideosPage } from "./pages/VideosPage";

export function App() {
  return (
    <Routes>
      {/* Public, reader-facing site */}
      <Route element={<SiteLayout />}>
        <Route index element={<HomePage />} />
        <Route path="news" element={<NewsPage />} />
        <Route path="videos" element={<VideosPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="about" element={<AboutPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      {/* Operator / system status area (read-only, linked from the footer) */}
      <Route path="admin" element={<AdminLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="sources" element={<SourcesPage />} />
        <Route path="jobs" element={<JobsPage />} />
      </Route>

      {/* Old dashboard URLs */}
      <Route path="sources" element={<Navigate to="/admin/sources" replace />} />
      <Route path="jobs" element={<Navigate to="/admin/jobs" replace />} />
    </Routes>
  );
}
