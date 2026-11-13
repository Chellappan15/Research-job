import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  SOURCES,
  STATS,
  feedPage,
  makeItem,
  makeRun,
  mockApi,
  renderWithProviders,
  requestedUrls,
} from "../test/utils";
import { JobsPage } from "./JobsPage";
import { OverviewPage } from "./OverviewPage";
import { SourcesPage } from "./SourcesPage";
import { VideosPage } from "./VideosPage";

describe("OverviewPage", () => {
  it("renders metrics exactly as returned by /stats", async () => {
    mockApi((url) => {
      if (url.pathname === "/api/v1/stats") return { body: STATS };
      if (url.pathname === "/api/v1/feed") return { body: feedPage(url, 3) };
      return { body: { items: [makeRun(1)], total: 1, limit: 6, offset: 0 } };
    });
    renderWithProviders(<OverviewPage />);
    expect(await screen.findByText("2,319")).toBeInTheDocument();
    expect(screen.getByText("2,000")).toBeInTheDocument();
    expect(screen.getByText("319")).toBeInTheDocument();
    expect(screen.getByText("1 with errors")).toBeInTheDocument();
    expect(screen.getByText("+57 in last 24h")).toBeInTheDocument();
  });
});

describe("VideosPage", () => {
  it("requests videos only and links to YouTube", async () => {
    const fetchMock = mockApi((url) => {
      if (url.pathname === "/api/v1/sources") return { body: SOURCES };
      return {
        body: feedPage(url, 2, (n) =>
          makeItem(n, { type: "video", url: `https://www.youtube.com/watch?v=v${n}`, source_name: "Channel" }),
        ),
      };
    });
    renderWithProviders(<VideosPage />);
    const link = await screen.findByRole("link", { name: /Item 1\b/ });
    expect(link).toHaveAttribute("href", "https://www.youtube.com/watch?v=v1");
    const req = requestedUrls(fetchMock, "/api/v1/feed")[0]!;
    expect(req.searchParams.get("type")).toBe("video");
    expect(req.searchParams.get("limit")).toBe("24");
  });
});

describe("SourcesPage", () => {
  it("lists sources with type, status, interval and errors", async () => {
    mockApi(() => ({ body: SOURCES }));
    renderWithProviders(<SourcesPage />);
    expect((await screen.findAllByText("Source Two")).length).toBeGreaterThan(0);
    expect(screen.getByText("2 of 3 sources enabled")).toBeInTheDocument();
    expect(screen.getAllByText("every 6h").length).toBeGreaterThan(0);
    expect(screen.getAllByText("FetchError: client error (HTTP 404)").length).toBeGreaterThan(0);
  });

  it("shows an empty state when no sources exist", async () => {
    mockApi(() => ({ body: [] }));
    renderWithProviders(<SourcesPage />);
    expect(await screen.findByText("No sources registered")).toBeInTheDocument();
  });
});

describe("JobsPage", () => {
  it("shows runs and filters by status via the backend", async () => {
    const fetchMock = mockApi((url) => {
      if (url.pathname === "/api/v1/stats") return { body: STATS };
      if (url.pathname === "/api/v1/sources") return { body: SOURCES };
      return {
        body: {
          items: [makeRun(1, { status: "failed", last_error: "FetchError: timeout", completed_at: null })],
          total: 1,
          limit: 25,
          offset: 0,
        },
      };
    });
    const user = userEvent.setup();
    renderWithProviders(<JobsPage />);
    expect((await screen.findAllByText("FetchError: timeout")).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("radio", { name: /Failed/ }));
    await waitFor(() => {
      const last = requestedUrls(fetchMock, "/api/v1/ingestion-runs").at(-1)!;
      expect(last.searchParams.get("status")).toBe("failed");
    });
  });
});
