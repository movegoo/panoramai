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
  Building2,
  Info,
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

const TYPE_LABELS: Record<string, string> = {
  branding: "Branding",
  performance: "Performance",
  dts: "Drive-to-Store",
  unknown: "Non classifie",
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

function formatBudget(min: number, max: number): string {
  if (min === 0 && max === 0) return "N/A";
  const lo = Math.min(min, max);
  const hi = Math.max(min, max);
  if (lo === hi) return `~${formatNumber(lo)} \u20ac`;
  return `${formatNumber(lo)} \u2013 ${formatNumber(hi)} \u20ac`;
}

export default function AdsOverviewPage() {
  const [periodDays, setPeriodDays] = useState<PeriodDays>(90);
  const [sovMetric, setSovMetric] = useState<"ads" | "spend">("ads");

  const { start, end } = periodToDates(periodDays);
  const { data, isLoading, error } = useAPI<any>(
    `/ads/overview?start_date=${start}&end_date=${end}`
  );

  const advertisers = data?.advertisers || [];
  const timeline = data?.timeline || [];
  const totals = data?.totals || {};

  // Top 10 for charts, rest grouped as "Autres"
  const top10 = useMemo(() => advertisers.slice(0, 10), [advertisers]);

  // Donut data
  const donutData = useMemo(() => {
    const top = top10.map((a: any, i: number) => ({
      name: a.name,
      value: sovMetric === "ads" ? a.total_ads : Math.min(a.spend_min, a.spend_max) || a.spend_min,
      color: COLORS[i % COLORS.length],
    }));
    if (advertisers.length > 10) {
      const rest = advertisers.slice(10);
      const value = sovMetric === "ads"
        ? rest.reduce((s: number, a: any) => s + a.total_ads, 0)
        : rest.reduce((s: number, a: any) => s + (a.spend_min || 0), 0);
      top.push({ name: "Autres", value, color: "#d1d5db" });
    }
    return top;
  }, [top10, advertisers, sovMetric]);

  // Platform stacked data (top 10 only)
  const platformData = useMemo(() => {
    const allPlatforms = new Set<string>();
    top10.forEach((a: any) => {
      Object.keys(a.by_platform || {}).forEach((p) => allPlatforms.add(p));
    });
    return top10.map((a: any) => {
      const total = a.total_ads || 1;
      const entry: any = { name: a.name };
      allPlatforms.forEach((p) => {
        entry[p] = Math.round(((a.by_platform?.[p]?.ads || 0) / total) * 100);
      });
      return entry;
    });
  }, [top10]);

  const allPlatforms = useMemo(() => {
    const s = new Set<string>();
    top10.forEach((a: any) => {
      Object.keys(a.by_platform || {}).forEach((p) => s.add(p));
    });
    return Array.from(s);
  }, [top10]);

  // Timeline: only use top 10 names
  const advNames = useMemo(() => top10.map((a: any) => a.name), [top10]);

  // Ad type data (top 10 only)
  const typeData = useMemo(() => {
    const types = new Set<string>();
    top10.forEach((a: any) => {
      Object.keys(a.by_type || {}).forEach((t) => types.add(t));
    });
    return top10.map((a: any) => {
      const entry: any = { name: a.name };
      types.forEach((t) => {
        entry[t] = a.by_type?.[t] || 0;
      });
      return entry;
    });
  }, [top10]);

  const allTypes = useMemo(() => {
    const s = new Set<string>();
    top10.forEach((a: any) => {
      Object.keys(a.by_type || {}).forEach((t) => s.add(t));
    });
    return Array.from(s);
  }, [top10]);

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
              Qui communique le plus, sur quel r&eacute;seau, &agrave; quel moment &mdash; par b&eacute;n&eacute;ficiaire
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
          {/* ── KPI Cards ── */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            <KPICard
              icon={Building2}
              iconBg="bg-indigo-100 text-indigo-600"
              label="B&eacute;n&eacute;ficiaires"
              value={String(totals.advertisers_count || 0)}
              sub="marques distinctes"
            />
            <KPICard
              icon={Megaphone}
              iconBg="bg-violet-100 text-violet-600"
              label="Total pubs"
              value={formatNumber(totals.total_ads || 0)}
              sub="sur la p\u00e9riode"
            />
            <KPICard
              icon={Zap}
              iconBg="bg-emerald-100 text-emerald-600"
              label="Pubs actives"
              value={formatNumber(totals.active_ads || 0)}
              sub="en cours de diffusion"
            />
            <KPICard
              icon={Euro}
              iconBg="bg-amber-100 text-amber-600"
              label="Budget estim\u00e9 total"
              value={formatBudget(totals.spend_min || 0, totals.spend_max || 0)}
              sub="estimation CPM 3\u20ac"
            />
            <KPICard
              icon={Users}
              iconBg="bg-blue-100 text-blue-600"
              label="Couverture EU"
              value={formatNumber(totals.reach || 0)}
              sub="personnes atteintes"
            />
          </div>

          {/* ── Info banner ── */}
          <div className="flex items-start gap-3 rounded-xl bg-indigo-50 border border-indigo-100 p-4">
            <Info className="h-4 w-4 text-indigo-500 mt-0.5 shrink-0" />
            <p className="text-xs text-indigo-700 leading-relaxed">
              La part de voix est calcul&eacute;e par <strong>b&eacute;n&eacute;ficiaire</strong> (la marque qui profite de la pub), pas par payeur (l&rsquo;agence m&eacute;dia). Par exemple, Mobsuccess peut payer pour Carrefour &mdash; c&rsquo;est Carrefour qui appara&icirc;t ici. Un m&ecirc;me concurrent peut avoir plusieurs b&eacute;n&eacute;ficiaires (ex: Carrefour, Carrefour City, Carrefour Voyages).
            </p>
          </div>

          {/* ── Part de voix donut + classement ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Donut */}
            <div className="rounded-2xl border bg-card p-6">
              <div className="flex items-center justify-between mb-2">
                <SectionHeader
                  icon={PieChartIcon}
                  color="bg-violet-100 text-violet-600"
                  title="Part de voix"
                />
                <div className="flex items-center gap-1 p-0.5 rounded-full bg-muted border">
                  <button
                    onClick={() => setSovMetric("ads")}
                    className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                      sovMetric === "ads" ? "bg-foreground text-background shadow-sm" : "text-muted-foreground"
                    }`}
                  >
                    Nombre
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
              <p className="text-xs text-muted-foreground mb-4">
                {sovMetric === "ads"
                  ? "Proportion du nombre de pubs par b\u00e9n\u00e9ficiaire"
                  : "Proportion du budget estim\u00e9 par b\u00e9n\u00e9ficiaire"}
              </p>
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={donutData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={2}
                      dataKey="value"
                      nameKey="name"
                    >
                      {donutData.map((d: any, i: number) => (
                        <Cell key={i} fill={d.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number, name: string) => [
                        sovMetric === "spend" ? `${formatNumber(value)} \u20ac` : `${formatNumber(value)} pubs`,
                        name,
                      ]}
                    />
                    <Legend
                      layout="vertical"
                      align="right"
                      verticalAlign="middle"
                      iconType="circle"
                      iconSize={8}
                      formatter={(value: string) => (
                        <span className="text-xs text-foreground">{value.length > 20 ? value.slice(0, 18) + "\u2026" : value}</span>
                      )}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Ranking */}
            <div className="rounded-2xl border bg-card p-6">
              <SectionHeader icon={Trophy} color="bg-amber-100 text-amber-600" title="Top b&eacute;n&eacute;ficiaires" />
              <p className="text-xs text-muted-foreground mt-1 mb-4">
                Les marques qui diffusent le plus de publicit&eacute;s sur la p&eacute;riode
              </p>
              <div className="space-y-3 max-h-[320px] overflow-y-auto pr-1">
                {advertisers.slice(0, 15).map((a: any, i: number) => {
                  const maxAds = advertisers[0]?.total_ads || 1;
                  const pct = (a.total_ads / maxAds) * 100;
                  const medal = i === 0 ? "\ud83e\uddc1" : i === 1 ? "\ud83e\uddc2" : i === 2 ? "\ud83e\uddc3" : null;
                  return (
                    <div key={a.name} className="flex items-center gap-3">
                      <span className="text-sm font-semibold w-6 text-center text-muted-foreground shrink-0">
                        {medal || `${i + 1}`}
                      </span>
                      {a.logo_url ? (
                        <img src={a.logo_url} alt="" className="h-6 w-6 rounded-full object-cover shrink-0" />
                      ) : (
                        <div className="h-6 w-6 rounded-full bg-muted flex items-center justify-center shrink-0">
                          <span className="text-[10px] font-bold text-muted-foreground">
                            {a.name.charAt(0)}
                          </span>
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-1.5 min-w-0">
                            <span className="text-sm font-medium truncate">{a.name}</span>
                            {a.parent_competitor && a.parent_competitor !== a.name && (
                              <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded shrink-0">
                                {a.parent_competitor}
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-muted-foreground ml-2 shrink-0">
                            {a.total_ads} &middot; {a.sov_pct}%
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

          {/* ── R&eacute;partition par plateforme ── */}
          <div className="rounded-2xl border bg-card p-6">
            <SectionHeader icon={BarChart3} color="bg-blue-100 text-blue-600" title="Mix plateforme par b&eacute;n&eacute;ficiaire" />
            <p className="text-xs text-muted-foreground mt-1 mb-4">
              Sur quels r&eacute;seaux chaque b&eacute;n&eacute;ficiaire diffuse ses publicit&eacute;s (% du volume)
            </p>
            <div style={{ height: Math.max(250, top10.length * 40 + 60) }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={platformData} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={120} />
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

          {/* ── Timeline ── */}
          <div className="rounded-2xl border bg-card p-6">
            <SectionHeader icon={TrendingUp} color="bg-emerald-100 text-emerald-600" title="Pression publicitaire dans le temps" />
            <p className="text-xs text-muted-foreground mt-1 mb-4">
              Nombre de nouvelles publicit&eacute;s lanc&eacute;es par semaine, par b&eacute;n&eacute;ficiaire (top 10)
            </p>
            <div className="h-[320px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeline}>
                  <defs>
                    {advNames.map((name: string, i: number) => (
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
                  {advNames.map((name: string, i: number) => (
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

          {/* ── R&eacute;partition par type ── */}
          <div className="rounded-2xl border bg-card p-6">
            <SectionHeader icon={Layers} color="bg-pink-100 text-pink-600" title="Objectif publicitaire" />
            <p className="text-xs text-muted-foreground mt-1 mb-4">
              Branding (notori&eacute;t&eacute;), Performance (conversion) ou Drive-to-Store pour chaque b&eacute;n&eacute;ficiaire
            </p>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={typeData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-20} textAnchor="end" height={50} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  {allTypes.map((t) => (
                    <Bar
                      key={t}
                      dataKey={t}
                      fill={typeColors[t] || "#9ca3af"}
                      name={TYPE_LABELS[t] || t}
                      radius={[4, 4, 0, 0]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ── Tableau d&eacute;taill&eacute; ── */}
          <div className="rounded-2xl border bg-card p-6">
            <SectionHeader icon={BarChart3} color="bg-indigo-100 text-indigo-600" title="Tous les b&eacute;n&eacute;ficiaires" />
            <p className="text-xs text-muted-foreground mt-1 mb-4">
              D&eacute;tail complet de chaque b&eacute;n&eacute;ficiaire d&eacute;tect&eacute; sur la p&eacute;riode
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-3 pr-4 font-medium text-muted-foreground">#</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground">B&eacute;n&eacute;ficiaire</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground">Concurrent</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground text-right">Pubs</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground text-right">Actives</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground text-right">Part de voix</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground text-right">Budget estim&eacute;</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground text-right">Couverture</th>
                    <th className="pb-3 font-medium text-muted-foreground">Plateformes</th>
                  </tr>
                </thead>
                <tbody>
                  {advertisers.map((a: any, i: number) => {
                    const medal = i === 0 ? "\ud83e\uddc1" : i === 1 ? "\ud83e\uddc2" : i === 2 ? "\ud83e\uddc3" : null;
                    const platforms = Object.keys(a.by_platform || {});
                    return (
                      <tr key={a.name} className="border-b last:border-0 hover:bg-muted/30 transition-colors">
                        <td className="py-3 pr-4 text-sm font-semibold text-muted-foreground">
                          {medal || i + 1}
                        </td>
                        <td className="py-3 pr-4">
                          <div className="flex items-center gap-2">
                            {a.logo_url ? (
                              <img src={a.logo_url} alt="" className="h-6 w-6 rounded-full object-cover" />
                            ) : (
                              <div className="h-6 w-6 rounded-full bg-muted flex items-center justify-center">
                                <span className="text-[10px] font-bold text-muted-foreground">
                                  {a.name.charAt(0)}
                                </span>
                              </div>
                            )}
                            <span className="font-medium">{a.name}</span>
                          </div>
                        </td>
                        <td className="py-3 pr-4 text-xs text-muted-foreground">
                          {a.parent_competitor || "\u2014"}
                        </td>
                        <td className="py-3 pr-4 text-right font-medium">{a.total_ads}</td>
                        <td className="py-3 pr-4 text-right">{a.active_ads}</td>
                        <td className="py-3 pr-4 text-right">
                          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-violet-50 text-violet-700">
                            {a.sov_pct}%
                          </span>
                        </td>
                        <td className="py-3 pr-4 text-right text-xs">
                          {formatBudget(a.spend_min, a.spend_max)}
                        </td>
                        <td className="py-3 pr-4 text-right">{formatNumber(a.reach)}</td>
                        <td className="py-3">
                          <div className="flex gap-1 flex-wrap">
                            {platforms.map((p) => (
                              <span
                                key={p}
                                className="px-2 py-0.5 rounded-full text-[10px] font-medium"
                                style={{
                                  backgroundColor: `${PLATFORM_COLORS[p] || "#9ca3af"}18`,
                                  color: PLATFORM_COLORS[p] || "#9ca3af",
                                }}
                              >
                                {p.charAt(0).toUpperCase() + p.slice(1)}
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
  sub,
}: {
  icon: any;
  iconBg: string;
  label: string;
  value: string;
  sub?: string;
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
      {sub && (
        <p className="text-[11px] text-muted-foreground mt-1">{sub}</p>
      )}
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
