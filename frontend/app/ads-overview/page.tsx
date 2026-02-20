"use client";

import { useState, useMemo } from "react";
import { useAPI } from "@/lib/use-api";
import { formatNumber } from "@/lib/utils";
import { PeriodFilter, PeriodDays } from "@/components/period-filter";
import {
  Megaphone,
  Zap,
  Euro,
  Users,
  Trophy,
  BarChart3,
  Layers,
  TrendingUp,
  PieChart as PieChartIcon,
  Loader2,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
  AreaChart,
  Area,
} from "recharts";

const COLORS = ["#6366f1", "#ec4899", "#f59e0b", "#10b981", "#3b82f6", "#8b5cf6", "#ef4444", "#14b8a6"];
const PLATFORM_COLORS: Record<string, string> = {
  facebook: "#1877F2",
  instagram: "#E4405F",
  tiktok: "#000000",
  google: "#4285F4",
  unknown: "#9ca3af",
};

function periodToDates(days: PeriodDays): { start: string; end: string } {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - days);
  return {
    start: start.toISOString().split("T")[0],
    end: end.toISOString().split("T")[0],
  };
}

export default function AdsOverviewPage() {
  const [periodDays, setPeriodDays] = useState<PeriodDays>(90);
  const [sovMetric, setSovMetric] = useState<"ads" | "spend">("ads");

  const { start, end } = periodToDates(periodDays);
  const { data, isLoading, error } = useAPI<any>(
    `/ads/overview?start_date=${start}&end_date=${end}`
  );

  const competitors = data?.competitors || [];
  const timeline = data?.timeline || [];
  const totals = data?.totals || {};

  // Donut data
  const donutData = useMemo(() => {
    return competitors.map((c: any, i: number) => ({
      name: c.name,
      value: sovMetric === "ads" ? c.total_ads : c.spend_min,
      color: COLORS[i % COLORS.length],
    }));
  }, [competitors, sovMetric]);

  // Platform stacked data
  const platformData = useMemo(() => {
    const allPlatforms = new Set<string>();
    competitors.forEach((c: any) => {
      Object.keys(c.by_platform || {}).forEach((p) => allPlatforms.add(p));
    });
    return competitors.map((c: any) => {
      const total = c.total_ads || 1;
      const entry: any = { name: c.name };
      allPlatforms.forEach((p) => {
        entry[p] = Math.round(((c.by_platform?.[p]?.ads || 0) / total) * 100);
      });
      return entry;
    });
  }, [competitors]);

  const allPlatforms = useMemo(() => {
    const s = new Set<string>();
    competitors.forEach((c: any) => {
      Object.keys(c.by_platform || {}).forEach((p) => s.add(p));
    });
    return Array.from(s);
  }, [competitors]);

  // Timeline competitor names
  const compNames = useMemo(() => competitors.map((c: any) => c.name), [competitors]);

  // Ad type data
  const typeData = useMemo(() => {
    const types = new Set<string>();
    competitors.forEach((c: any) => {
      Object.keys(c.by_type || {}).forEach((t) => types.add(t));
    });
    return competitors.map((c: any) => {
      const entry: any = { name: c.name };
      types.forEach((t) => {
        entry[t] = c.by_type?.[t] || 0;
      });
      return entry;
    });
  }, [competitors]);

  const allTypes = useMemo(() => {
    const s = new Set<string>();
    competitors.forEach((c: any) => {
      Object.keys(c.by_type || {}).forEach((t) => s.add(t));
    });
    return Array.from(s);
  }, [competitors]);

  const typeColors: Record<string, string> = {
    branding: "#6366f1",
    performance: "#ec4899",
    dts: "#f59e0b",
    unknown: "#9ca3af",
  };

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-red-500">Erreur : {(error as Error).message}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* ── Hero ── */}
      <div className="bg-gradient-to-r from-indigo-950 via-[#1e1b4b] to-violet-950 px-6 py-8">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Part de Voix Publicitaire
            </h1>
            <p className="text-indigo-200/70 text-sm mt-1">
              Qui communique le plus, sur quel r&eacute;seau, &agrave; quel moment
            </p>
          </div>
          <PeriodFilter
            selectedDays={periodDays}
            onDaysChange={setPeriodDays}
            variant="dark"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-32">
          <Loader2 className="h-8 w-8 animate-spin text-violet-500" />
        </div>
      ) : (
        <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
          {/* ── 5.2 KPI Cards ── */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard
              icon={Megaphone}
              iconBg="bg-violet-100 text-violet-600"
              label="Total pubs"
              value={formatNumber(totals.total_ads || 0)}
            />
            <KPICard
              icon={Zap}
              iconBg="bg-emerald-100 text-emerald-600"
              label="Pubs actives"
              value={formatNumber(totals.active_ads || 0)}
            />
            <KPICard
              icon={Euro}
              iconBg="bg-amber-100 text-amber-600"
              label="Budget estim&eacute;"
              value={`${formatNumber(totals.spend_min || 0)} – ${formatNumber(totals.spend_max || 0)} €`}
            />
            <KPICard
              icon={Users}
              iconBg="bg-blue-100 text-blue-600"
              label="Couverture EU"
              value={formatNumber(totals.reach || 0)}
            />
          </div>

          {/* ── 5.3 Part de voix donut + classement ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Donut */}
            <div className="rounded-2xl border bg-card p-6">
              <div className="flex items-center justify-between mb-4">
                <SectionHeader icon={PieChartIcon} color="bg-violet-100 text-violet-600" title="Part de voix" />
                <div className="flex items-center gap-1 p-0.5 rounded-full bg-muted border">
                  <button
                    onClick={() => setSovMetric("ads")}
                    className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                      sovMetric === "ads" ? "bg-foreground text-background shadow-sm" : "text-muted-foreground"
                    }`}
                  >
                    Pubs
                  </button>
                  <button
                    onClick={() => setSovMetric("spend")}
                    className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                      sovMetric === "spend" ? "bg-foreground text-background shadow-sm" : "text-muted-foreground"
                    }`}
                  >
                    Budget
                  </button>
                </div>
              </div>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={donutData}
                      cx="50%"
                      cy="50%"
                      innerRadius={70}
                      outerRadius={110}
                      paddingAngle={2}
                      dataKey="value"
                      nameKey="name"
                    >
                      {donutData.map((d: any, i: number) => (
                        <Cell key={i} fill={d.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number) =>
                        sovMetric === "spend" ? `${formatNumber(value)} €` : formatNumber(value)
                      }
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Ranking */}
            <div className="rounded-2xl border bg-card p-6">
              <SectionHeader icon={Trophy} color="bg-amber-100 text-amber-600" title="Classement" />
              <div className="mt-4 space-y-3">
                {competitors.map((c: any, i: number) => {
                  const maxAds = competitors[0]?.total_ads || 1;
                  const pct = (c.total_ads / maxAds) * 100;
                  const medal = i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : null;
                  return (
                    <div key={c.id} className="flex items-center gap-3">
                      <span className="text-sm font-semibold w-6 text-center text-muted-foreground">
                        {medal || `#${i + 1}`}
                      </span>
                      {c.logo_url && (
                        <img src={c.logo_url} alt="" className="h-6 w-6 rounded-full object-cover" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium truncate">{c.name}</span>
                          <span className="text-xs text-muted-foreground ml-2 shrink-0">
                            {c.total_ads} pubs &middot; {c.sov_pct}%
                          </span>
                        </div>
                        <div className="h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${pct}%`,
                              backgroundColor: COLORS[i % COLORS.length],
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* ── 5.4 Répartition par plateforme ── */}
          <div className="rounded-2xl border bg-card p-6">
            <SectionHeader icon={BarChart3} color="bg-blue-100 text-blue-600" title="R&eacute;partition par plateforme" />
            <div className="h-[300px] mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={platformData} layout="vertical" margin={{ left: 80 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={80} />
                  <Tooltip formatter={(v: number) => `${v}%`} />
                  <Legend />
                  {allPlatforms.map((p) => (
                    <Bar
                      key={p}
                      dataKey={p}
                      stackId="a"
                      fill={PLATFORM_COLORS[p] || "#9ca3af"}
                      name={p.charAt(0).toUpperCase() + p.slice(1)}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ── 5.5 Timeline ── */}
          <div className="rounded-2xl border bg-card p-6">
            <SectionHeader icon={TrendingUp} color="bg-emerald-100 text-emerald-600" title="Timeline hebdomadaire" />
            <div className="h-[320px] mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeline}>
                  <defs>
                    {compNames.map((name: string, i: number) => (
                      <linearGradient key={name} id={`grad-${i}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.4} />
                        <stop offset="100%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.05} />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  {compNames.map((name: string, i: number) => (
                    <Area
                      key={name}
                      type="monotone"
                      dataKey={name}
                      stackId="1"
                      stroke={COLORS[i % COLORS.length]}
                      fill={`url(#grad-${i})`}
                      name={name}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ── 5.6 Répartition par type ── */}
          <div className="rounded-2xl border bg-card p-6">
            <SectionHeader icon={Layers} color="bg-pink-100 text-pink-600" title="R&eacute;partition par type" />
            <div className="h-[300px] mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={typeData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  {allTypes.map((t) => (
                    <Bar
                      key={t}
                      dataKey={t}
                      fill={typeColors[t] || "#9ca3af"}
                      name={t.charAt(0).toUpperCase() + t.slice(1)}
                      radius={[4, 4, 0, 0]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ── 5.7 Tableau détaillé ── */}
          <div className="rounded-2xl border bg-card p-6">
            <SectionHeader icon={BarChart3} color="bg-indigo-100 text-indigo-600" title="Classement d&eacute;taill&eacute;" />
            <div className="overflow-x-auto mt-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-3 pr-4 font-medium text-muted-foreground">#</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground">Enseigne</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground text-right">Pubs</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground text-right">Actives</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground text-right">Budget estim&eacute;</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground text-right">Couverture</th>
                    <th className="pb-3 font-medium text-muted-foreground">Plateformes</th>
                  </tr>
                </thead>
                <tbody>
                  {competitors.map((c: any, i: number) => {
                    const medal = i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : null;
                    const platforms = Object.keys(c.by_platform || {});
                    return (
                      <tr key={c.id} className="border-b last:border-0 hover:bg-muted/30 transition-colors">
                        <td className="py-3 pr-4 text-sm font-semibold text-muted-foreground">
                          {medal || i + 1}
                        </td>
                        <td className="py-3 pr-4">
                          <div className="flex items-center gap-2">
                            {c.logo_url && (
                              <img src={c.logo_url} alt="" className="h-6 w-6 rounded-full object-cover" />
                            )}
                            <span className="font-medium">{c.name}</span>
                          </div>
                        </td>
                        <td className="py-3 pr-4 text-right font-medium">{c.total_ads}</td>
                        <td className="py-3 pr-4 text-right">{c.active_ads}</td>
                        <td className="py-3 pr-4 text-right text-xs">
                          {formatNumber(c.spend_min)} – {formatNumber(c.spend_max)} €
                        </td>
                        <td className="py-3 pr-4 text-right">{formatNumber(c.reach)}</td>
                        <td className="py-3">
                          <div className="flex gap-1 flex-wrap">
                            {platforms.map((p) => (
                              <span
                                key={p}
                                className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-muted text-muted-foreground"
                              >
                                {p}
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Helper components ── */

function KPICard({
  icon: Icon,
  iconBg,
  label,
  value,
}: {
  icon: any;
  iconBg: string;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border bg-card p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${iconBg}`}>
          <Icon className="h-4 w-4" />
        </div>
        <span className="text-[13px] font-semibold text-muted-foreground">{label}</span>
      </div>
      <p className="text-xl font-bold tracking-tight">{value}</p>
    </div>
  );
}

function SectionHeader({
  icon: Icon,
  color,
  title,
}: {
  icon: any;
  color: string;
  title: string;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${color}`}>
        <Icon className="h-4 w-4" />
      </div>
      <h2 className="text-[13px] font-semibold">{title}</h2>
    </div>
  );
}
