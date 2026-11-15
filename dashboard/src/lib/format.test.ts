import { describe, expect, it } from "vitest";
import { formatDateOnly, formatWhen, safeHref } from "./format";

describe("formatWhen", () => {
  it("formats ISO timestamps", () => {
    const text = formatWhen("2026-11-15T21:00:00Z");
    expect(text).not.toBe("—");
    expect(text.toLowerCase()).toMatch(/nov|15|2026|pm|am|gmt|est|edt|utc/i);
  });

  it("handles missing values", () => {
    expect(formatWhen(null)).toBe("—");
  });
});

describe("formatDateOnly", () => {
  it("returns a calendar date", () => {
    expect(formatDateOnly("2026-11-15T12:00:00Z")).toMatch(/2026/);
  });
});

describe("safeHref", () => {
  it("allows https", () => {
    expect(safeHref("https://example.com/x")).toBe("https://example.com/x");
  });

  it("rejects javascript and file URLs", () => {
    expect(safeHref("javascript:alert(1)")).toBeNull();
    expect(safeHref("file:///etc/passwd")).toBeNull();
  });
});
