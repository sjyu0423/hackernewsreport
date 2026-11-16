import { describe, expect, it } from "vitest";
import {
  demoSnapshot,
  filterAndSortStories,
  filterStories,
  isSafePublicUrl,
  safeSourceHref,
  sortStories,
} from "./demo";

describe("demoSnapshot", () => {
  it("is a fixed public snapshot with opaque ids", () => {
    expect(demoSnapshot.kind).toBe("static_demo_briefing");
    expect(demoSnapshot.items.length).toBeGreaterThanOrEqual(5);
    expect(demoSnapshot.items.length).toBeLessThanOrEqual(8);
    for (const item of demoSnapshot.items) {
      expect(item.id).toMatch(/^demo-\d{2}$/);
      expect(item.source_url).toMatch(/^https?:\/\//);
      expect(item.summary.length).toBeGreaterThan(20);
      expect(item.why_it_matters.length).toBeGreaterThan(10);
      expect(["sufficient", "partial", "insufficient"]).toContain(
        item.evidence_sufficiency,
      );
    }
  });

  it("covers multiple source names", () => {
    const sources = new Set(demoSnapshot.items.map((item) => item.source_name));
    expect(sources.size).toBeGreaterThanOrEqual(4);
  });
});

describe("filterAndSortStories", () => {
  const stories = demoSnapshot.items;

  it("filters by category", () => {
    const category = stories[0]?.category ?? "AI Models";
    const filtered = filterStories(stories, category);
    expect(filtered.length).toBeGreaterThan(0);
    expect(filtered.every((story) => story.category === category)).toBe(true);
  });

  it("sorts by significance descending", () => {
    const sorted = sortStories(stories, "significance");
    for (let i = 1; i < sorted.length; i += 1) {
      expect(sorted[i - 1].significance_score).toBeGreaterThanOrEqual(
        sorted[i].significance_score,
      );
    }
  });

  it("sorts by relevance descending", () => {
    const sorted = sortStories(stories, "relevance");
    for (let i = 1; i < sorted.length; i += 1) {
      expect(sorted[i - 1].relevance_score).toBeGreaterThanOrEqual(
        sorted[i].relevance_score,
      );
    }
  });

  it("combines filter and sort", () => {
    const result = filterAndSortStories(stories, "all", "significance");
    expect(result).toHaveLength(stories.length);
  });
});

describe("safeSourceHref", () => {
  it("allows http and https", () => {
    expect(isSafePublicUrl("https://example.com/a")).toBe(true);
    expect(isSafePublicUrl("http://example.com/a")).toBe(true);
    expect(safeSourceHref("https://example.com/a")).toBe(
      "https://example.com/a",
    );
  });

  it("rejects unsafe schemes and invalid URLs", () => {
    expect(isSafePublicUrl("javascript:alert(1)")).toBe(false);
    expect(isSafePublicUrl("file:///etc/passwd")).toBe(false);
    expect(isSafePublicUrl("not a url")).toBe(false);
    expect(safeSourceHref("javascript:alert(1)")).toBeNull();
  });
});
