import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { SOURCES, feedPage, mockApi, renderWithProviders, requestedUrls } from "../test/utils";
import { NewsPage } from "./NewsPage";

function backend(total = 45) {
  return mockApi((url) => {
    if (url.pathname === "/api/v1/sources") return { body: SOURCES };
    if (url.pathname === "/api/v1/feed") return { body: feedPage(url, total) };
    throw new Error(`unexpected ${url}`);
  });
}

describe("NewsPage", () => {
  it("shows a loading skeleton, then articles from the backend", async () => {
    backend();
    renderWithProviders(<NewsPage />, { route: "/news", path: "/news" });
    expect(screen.getByRole("status", { name: "Loading articles" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Item 1\b/ })).toBeInTheDocument();
    expect(screen.getByText("45 articles, newest first")).toBeInTheDocument();
  });

  it("paginates against the backend with limit/offset", async () => {
    const fetchMock = backend(45);
    const user = userEvent.setup();
    const { location } = renderWithProviders(<NewsPage />, { route: "/news", path: "/news" });
    await screen.findByRole("link", { name: /Item 1\b/ });

    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByRole("link", { name: /Item 21\b/ })).toBeInTheDocument();
    expect(screen.getByText("Page 2 of 3")).toBeInTheDocument();
    expect(location.current).toBe("/news?page=2");

    const last = requestedUrls(fetchMock, "/api/v1/feed").at(-1)!;
    expect(last.searchParams.get("offset")).toBe("20");
    expect(last.searchParams.get("limit")).toBe("20");
    expect(last.searchParams.get("type")).toBe("article");

    await user.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByRole("link", { name: /Item 41\b/ });
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  it("filters by source on the server and resets to page 1", async () => {
    const fetchMock = backend();
    const user = userEvent.setup();
    const { location } = renderWithProviders(<NewsPage />, {
      route: "/news?page=2",
      path: "/news",
    });
    await screen.findByRole("link", { name: /Item 21\b/ });

    const select = screen.getByLabelText("Source");
    // YouTube channels are not offered on the news page
    expect(within(select).queryByRole("option", { name: "Channel" })).not.toBeInTheDocument();
    await user.selectOptions(select, "src-2");

    await waitFor(() => {
      const last = requestedUrls(fetchMock, "/api/v1/feed").at(-1)!;
      expect(last.searchParams.getAll("source_id")).toEqual(["src-2"]);
      expect(last.searchParams.get("offset")).toBe("0");
    });
    expect(location.current).toBe("/news?source=src-2");
  });

  it("sends search and date filters to the backend", async () => {
    const fetchMock = backend();
    const user = userEvent.setup();
    renderWithProviders(<NewsPage />, { route: "/news?from=2026-11-01&to=2026-11-02", path: "/news" });
    await screen.findByRole("link", { name: /Item 1\b/ });
    await user.type(screen.getByRole("searchbox"), "diffusion{Enter}");
    await waitFor(() => {
      const last = requestedUrls(fetchMock, "/api/v1/feed").at(-1)!;
      expect(last.searchParams.get("q")).toBe("diffusion");
      const since = Date.parse(last.searchParams.get("since")!);
      const until = Date.parse(last.searchParams.get("until")!);
      expect(until - since).toBe(2 * 24 * 3600 * 1000); // both days inclusive
    });
  });

  it("shows an error with a working retry", async () => {
    let fail = true;
    mockApi((url) => {
      if (url.pathname === "/api/v1/sources") return { body: SOURCES };
      if (fail) return { status: 500, body: { detail: "database unavailable" } };
      return { body: feedPage(url, 3) };
    });
    const user = userEvent.setup();
    renderWithProviders(<NewsPage />, { route: "/news", path: "/news" });
    expect(await screen.findByRole("alert")).toHaveTextContent("database unavailable");
    fail = false;
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("link", { name: /Item 3\b/ })).toBeInTheDocument();
  });

  it("shows a filtered empty state", async () => {
    backend(0);
    renderWithProviders(<NewsPage />, { route: "/news?q=nothing", path: "/news" });
    expect(await screen.findByText("No articles match these filters")).toBeInTheDocument();
  });

  it("recovers from a page number past the end", async () => {
    backend(12);
    const { location } = renderWithProviders(<NewsPage />, {
      route: "/news?q=x&page=5",
      path: "/news",
    });
    expect(await screen.findByRole("link", { name: /Item 12\b/ })).toBeInTheDocument();
    expect(location.current).toBe("/news?q=x");
  });
});
