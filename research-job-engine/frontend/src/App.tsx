import { Route, Routes } from "react-router";

import { AppLayout } from "./components/layout/AppLayout";
import { JobsPage } from "./pages/JobsPage";
import { NewsPage } from "./pages/NewsPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { OverviewPage } from "./pages/OverviewPage";
import { SourcesPage } from "./pages/SourcesPage";
import { VideosPage } from "./pages/VideosPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="news" element={<NewsPage />} />
        <Route path="videos" element={<VideosPage />} />
        <Route path="sources" element={<SourcesPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
