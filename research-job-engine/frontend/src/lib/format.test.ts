import { describe, expect, it } from "vitest";

import {
  dayEndExclusiveIso,
  dayStartIso,
  formatDuration,
  formatInterval,
  formatRelative,
  hostname,
} from "./format";

const NOW = Date.parse("2026-11-13T12:00:00Z");

describe("format helpers", () => {
  it("formats relative times", () => {
    expect(formatRelative(null, NOW)).toBe("never");
    expect(formatRelative("2026-11-13T11:59:50Z", NOW)).toBe("just now");
    expect(formatRelative("2026-11-13T11:55:00Z", NOW)).toBe("5 minutes ago");
    expect(formatRelative("2026-11-13T09:00:00Z", NOW)).toBe("3 hours ago");
    expect(formatRelative("2026-11-12T12:00:00Z", NOW)).toBe("yesterday");
  });

  it("formats intervals and durations", () => {
    expect(formatInterval(3600)).toBe("every 1h");
    expect(formatInterval(21600)).toBe("every 6h");
    expect(formatInterval(90)).toBe("every 90s");
    expect(formatInterval(86400)).toBe("every 1d");
    expect(formatDuration("2026-11-13T00:00:00Z", "2026-11-13T00:00:00.250Z")).toBe("250 ms");
    expect(formatDuration("2026-11-13T00:00:00Z", null)).toBe("—");
  });

  it("converts date inputs into a tz-aware, inclusive day range", () => {
    const start = dayStartIso("2026-11-01")!;
    const end = dayEndExclusiveIso("2026-11-01")!;
    expect(start).toMatch(/Z$/);
    expect(Date.parse(end) - Date.parse(start)).toBe(24 * 3600 * 1000);
    expect(dayStartIso("not-a-date")).toBeUndefined();
  });

  it("extracts hostnames safely", () => {
    expect(hostname("https://www.example.com/a")).toBe("example.com");
    expect(hostname("not a url")).toBe("not a url");
  });
});
