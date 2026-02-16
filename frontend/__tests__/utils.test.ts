import { describe, it, expect } from "vitest";
import { formatNumber, formatDate, getRelativeTime } from "../lib/utils";

describe("formatNumber", () => {
  it("formats millions", () => {
    expect(formatNumber(2_000_000)).toBe("2M");
  });

  it("formats millions with decimal", () => {
    expect(formatNumber(1_500_000)).toBe("1.5M");
  });

  it("formats large millions without decimal", () => {
    expect(formatNumber(15_000_000)).toBe("15M");
  });

  it("formats thousands", () => {
    expect(formatNumber(1_500)).toBe("1.5K");
  });

  it("formats large thousands", () => {
    expect(formatNumber(15_000)).toBe("15K");
  });

  it("keeps small numbers as-is", () => {
    // toLocaleString("fr-FR") output varies by environment
    const result = formatNumber(500);
    expect(result).toContain("500");
  });

  it("formats zero", () => {
    const result = formatNumber(0);
    expect(result).toContain("0");
  });
});

describe("formatDate", () => {
  it("formats valid date", () => {
    const result = formatDate("2025-01-15T12:00:00Z");
    expect(result).toBeTruthy();
    expect(result.length).toBeGreaterThan(0);
  });

  it("returns empty for empty string", () => {
    expect(formatDate("")).toBe("");
  });

  it("returns empty for invalid date", () => {
    expect(formatDate("not-a-date")).toBe("");
  });
});

describe("getRelativeTime", () => {
  it("returns 'Just now' for very recent dates", () => {
    const now = new Date().toISOString();
    expect(getRelativeTime(now)).toBe("Just now");
  });

  it("returns minutes ago", () => {
    const date = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(getRelativeTime(date)).toBe("5m ago");
  });

  it("returns hours ago", () => {
    const date = new Date(Date.now() - 3 * 3600 * 1000).toISOString();
    expect(getRelativeTime(date)).toBe("3h ago");
  });

  it("returns days ago", () => {
    const date = new Date(Date.now() - 2 * 86400 * 1000).toISOString();
    expect(getRelativeTime(date)).toBe("2d ago");
  });

  it("falls back to formatted date for old dates", () => {
    const date = new Date(Date.now() - 30 * 86400 * 1000).toISOString();
    const result = getRelativeTime(date);
    // Should not contain "ago" - it should be a formatted date
    expect(result).not.toContain("ago");
    expect(result.length).toBeGreaterThan(0);
  });
});
