"use client";

import { X } from "lucide-react";

export const PERIOD_PRESETS = [
  { label: "7j", days: 7 },
  { label: "30j", days: 30 },
  { label: "90j", days: 90 },
  { label: "12 mois", days: 365 },
] as const;

export type PeriodDays = 7 | 30 | 90 | 365;

export function periodLabel(days: PeriodDays): string {
  return days === 365 ? "12m" : `${days}j`;
}

/* ── Preset pills (Dashboard, Social, Apps) ── */

interface PeriodFilterProps {
  selectedDays: PeriodDays;
  onDaysChange: (days: PeriodDays) => void;
  variant?: "default" | "dark";
}

export function PeriodFilter({ selectedDays, onDaysChange, variant = "default" }: PeriodFilterProps) {
  const dark = variant === "dark";
  return (
    <div
      className={`flex items-center gap-1 p-1 rounded-full w-fit ${
        dark ? "bg-white/[0.08] border border-white/[0.1]" : "bg-card border border-border"
      }`}
    >
      {PERIOD_PRESETS.map((preset) => (
        <button
          key={preset.days}
          onClick={() => onDaysChange(preset.days as PeriodDays)}
          className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all ${
            selectedDays === preset.days
              ? dark
                ? "bg-white text-indigo-950 shadow-sm"
                : "bg-foreground text-background shadow-sm"
              : dark
                ? "text-white/50 hover:text-white/80"
                : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {preset.label}
        </button>
      ))}
    </div>
  );
}

/* ── Date range with preset quick-fill (Ads) ── */

interface DateRangeFilterProps {
  dateFrom: string;
  dateTo: string;
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
}

export function DateRangeFilter({ dateFrom, dateTo, onDateFromChange, onDateToChange }: DateRangeFilterProps) {
  function applyPreset(days: number) {
    const to = new Date();
    const from = new Date();
    from.setDate(from.getDate() - days);
    onDateFromChange(from.toISOString().split("T")[0]);
    onDateToChange(to.toISOString().split("T")[0]);
  }

  function clearDates() {
    onDateFromChange("");
    onDateToChange("");
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 flex-wrap">
        {PERIOD_PRESETS.map((preset) => (
          <button
            key={preset.days}
            onClick={() => applyPreset(preset.days)}
            className="px-2.5 py-1 rounded-full text-[11px] font-medium bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-all"
          >
            {preset.label}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => onDateFromChange(e.target.value)}
          className="flex-1 min-w-0 px-3 py-1.5 rounded-lg border bg-background text-xs focus:outline-none focus:ring-2 focus:ring-violet-500/20"
        />
        <span className="text-xs text-muted-foreground shrink-0">&agrave;</span>
        <input
          type="date"
          value={dateTo}
          onChange={(e) => onDateToChange(e.target.value)}
          className="flex-1 min-w-0 px-3 py-1.5 rounded-lg border bg-background text-xs focus:outline-none focus:ring-2 focus:ring-violet-500/20"
        />
        {(dateFrom || dateTo) && (
          <button onClick={clearDates} className="text-muted-foreground hover:text-foreground shrink-0">
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
