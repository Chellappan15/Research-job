import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { makeItem } from "../../test/utils";
import { ArticleCard } from "./ArticleCard";
import { VideoCard } from "./VideoCard";

describe("content cards with missing optional fields", () => {
  it("renders an article without summary, thumbnail or publication date", () => {
    render(
      <ArticleCard item={makeItem(1, { summary: null, thumbnail_url: null, published_at: null })} />,
    );
    const link = screen.getByRole("link", { name: /Item 1/ });
    expect(link).toHaveAttribute("href", "https://example.com/1");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    expect(screen.getByText("No summary provided by the source.")).toBeInTheDocument();
    expect(screen.getByText(/fetched/)).toBeInTheDocument(); // falls back to fetch time
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("shows a placeholder for videos without thumbnails and on image errors", () => {
    const { container, rerender } = render(
      <VideoCard item={makeItem(2, { type: "video", thumbnail_url: null, published_at: null })} />,
    );
    expect(screen.getByTestId("thumbnail-placeholder")).toBeInTheDocument();
    expect(screen.getByText("date unknown")).toBeInTheDocument();

    rerender(
      <VideoCard item={makeItem(3, { type: "video", thumbnail_url: "https://img.example/x.jpg" })} />,
    );
    const img = container.querySelector("img")!;
    expect(img).toHaveAttribute("src", "https://img.example/x.jpg");
    fireEvent.error(img);
    expect(screen.getByTestId("thumbnail-placeholder")).toBeInTheDocument();
  });
});
