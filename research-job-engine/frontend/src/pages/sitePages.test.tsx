import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { App } from "../App";
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
import { HOME_ARTICLES, HOME_VIDEOS, HomePage } from "./HomePage";
import { SearchPage } from "./SearchPage";

function fullBackend() {
  return mockApi((url) => {
    switch (url.pathname) {
      case "/api/v1/sources":
        return { body: SOURCES };
      case "/api/v1/stats":
        return { body: STATS };
      case "/api/v1/ingestion-runs":
        return { body: { items: [makeRun(1)], total: 1, limit: 25, offset: 0 } };
      case "/health":
        return { body: { status: "ok" } };
      default:
        return {
          body: feedPage(url, 30, (n) =>
            makeItem(n, url.searchParams.get("type") === "video" ? { type: "video" } : {}),
          ),
        };
    }
  });
}

function renderApp(route: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("public site", () => {
  it("main navigation contains only reader pages; status is a footer link", async () => {
    fullBackend();
    renderApp("/");
    const main = screen.getByRole("navigation", { name: "Main" });
    expect(within(main).getAllByRole("link").map((a) => a.textContent)).toEqual([
      "Home",
      "News",
      "Videos",
    ]);
    const footer = screen.getByRole("navigation", { name: "Footer" });
    expect(within(footer).getByRole("link", { name: "System status" })).toHaveAttribute(
      "href",
      "/admin",
    );
    expect(screen.queryByText(/Job Monitor/)).not.toBeInTheDocument();
  });

  it("home shows a featured story, more articles and videos from the API", async () => {
    const fetchMock = fullBackend();
    renderWithProviders(<HomePage />);
    expect(await screen.findByRole("heading", { name: "Latest news" })).toBeInTheDocument();
    await screen.findAllByRole("link", { name: /Item 1\b/ });
    const feeds = requestedUrls(fetchMock, "/api/v1/feed");
    const article = feeds.find((u) => u.searchParams.get("type") === "article")!;
    const video = feeds.find((u) => u.searchParams.get("type") === "video")!;
    expect(article.searchParams.get("limit")).toBe(String(HOME_ARTICLES));
    expect(video.searchParams.get("limit")).toBe(String(HOME_VIDEOS));
    await waitFor(() => expect(screen.getAllByRole("article")).toHaveLength(HOME_ARTICLES + HOME_VIDEOS));
  });

  it("header search navigates to site-wide search across articles and videos", async () => {
    const fetchMock = fullBackend();
    const user = userEvent.setup();
    renderApp("/");
    await user.type(screen.getByRole("searchbox", { name: /Search articles and videos/ }), "diffusion{Enter}");
    expect(await screen.findByRole("heading", { name: "Results for “diffusion”" })).toBeInTheDocument();
    await waitFor(() => {
      const last = requestedUrls(fetchMock, "/api/v1/feed").at(-1)!;
      expect(last.searchParams.get("q")).toBe("diffusion");
      expect(last.searchParams.get("type")).toBeNull();
    });
  });

  it("search page without a query shows a prompt instead of results", () => {
    fullBackend();
    renderWithProviders(<SearchPage />, { route: "/search", path: "/search" });
    expect(screen.getByText("Search TechPulse")).toBeInTheDocument();
  });
});

describe("status area", () => {
  it("lives under /admin with its own navigation and a way back", async () => {
    fullBackend();
    renderApp("/admin");
    expect(await screen.findByRole("heading", { name: "System status" })).toBeInTheDocument();
    const nav = screen.getAllByRole("navigation", { name: "Status pages" })[0]!;
    expect(within(nav).getByRole("link", { name: /Job Monitor/ })).toHaveAttribute("href", "/admin/jobs");
    expect(screen.getAllByRole("link", { name: /Back to site/ })[0]).toHaveAttribute("href", "/");
  });

  it("old dashboard URLs redirect into /admin", async () => {
    fullBackend();
    renderApp("/jobs");
    expect(await screen.findByRole("heading", { name: "Job Monitor" })).toBeInTheDocument();
  });
});
