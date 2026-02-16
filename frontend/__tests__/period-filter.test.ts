import { describe, it, expect } from "vitest";
import { PERIOD_PRESETS, periodLabel, type PeriodDays } from "../components/period-filter";

describe("PERIOD_PRESETS", () => {
  it("has 4 presets", () => {
    expect(PERIOD_PRESETS).toHaveLength(4);
  });

  it("has correct days values", () => {
    const days = PERIOD_PRESETS.map((p) => p.days);
    expect(days).toEqual([7, 30, 90, 365]);
  });

  it("has French labels", () => {
    const labels = PERIOD_PRESETS.map((p) => p.label);
    expect(labels).toEqual(["7j", "30j", "90j", "12 mois"]);
  });
});

describe("periodLabel", () => {
  it("returns '7j' for 7 days", () => {
    expect(periodLabel(7)).toBe("7j");
  });

  it("returns '30j' for 30 days", () => {
    expect(periodLabel(30)).toBe("30j");
  });

  it("returns '90j' for 90 days", () => {
    expect(periodLabel(90)).toBe("90j");
  });

  it("returns '12m' for 365 days", () => {
    expect(periodLabel(365)).toBe("12m");
  });
});
