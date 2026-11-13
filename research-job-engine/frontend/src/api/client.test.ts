import { describe, expect, it, vi } from "vitest";

import { mockApi } from "../test/utils";
import { ApiError, api, buildUrl } from "./client";

describe("buildUrl", () => {
  it("serialises params, repeats arrays and drops empty values", () => {
    const url = buildUrl("/api/v1/feed", {
      limit: 20,
      offset: 0,
      source_id: ["a", "b"],
      q: "",
      type: undefined,
    });
    expect(url).toBe("/api/v1/feed?limit=20&offset=0&source_id=a&source_id=b");
  });
});

describe("apiGet", () => {
  it("returns parsed JSON for successful responses", async () => {
    mockApi(() => ({ body: { items: [], total: 0, limit: 20, offset: 0 } }));
    await expect(api.feed({ limit: 20, offset: 0 })).resolves.toEqual({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    });
  });

  it("surfaces FastAPI string detail", async () => {
    mockApi(() => ({ status: 404, body: { detail: "item not found" } }));
    const err = await api.feedItem("x").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 404, message: "item not found" });
  });

  it("formats FastAPI validation errors", async () => {
    mockApi(() => ({
      status: 422,
      body: { detail: [{ loc: ["query", "limit"], msg: "Input should be less than or equal to 100" }] },
    }));
    await expect(api.feed({ limit: 500, offset: 0 })).rejects.toThrow(
      "limit: Input should be less than or equal to 100",
    );
  });

  it("handles non-JSON server errors", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>bad gateway</html>", { status: 502 })));
    await expect(api.stats()).rejects.toMatchObject({ status: 502, message: "Server error (HTTP 502)" });
  });

  it("reports network failures clearly", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    await expect(api.sources()).rejects.toMatchObject({
      status: 0,
      message: expect.stringContaining("Cannot reach the TechPulse API"),
    });
  });
});
