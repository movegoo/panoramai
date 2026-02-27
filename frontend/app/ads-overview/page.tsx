"use client";

import { useState, useMemo } from "react";
import { useAPI } from "@/lib/use-api";
import { formatNumber } from "@/lib/utils";
import { PeriodFilter, PeriodDays } from "@/components/period-filter";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { SectionCard } from "@/components/section-card";
import { LoadingState } from "@/components/loading-state";
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
import { PageGate } from "@/components/page-gate";

const COLORS = ["#6366f1", "#ec4899", "#f59e0b", "#10b981", "#3b82f6", "#8b5cf6", "#ef4444", "#14b8a6"];
const PLATFORM_COLORS: Record<string, string> = {
  facebook: "#1877F2",
  instagram: "#E4405F",
  tiktok: "#000000",
  google: "#4285F4",
  snapchat: "#FFFC00",
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

  const competitors = data?.competitors || [];
  const timeline = data?.timeline || [];
  const totals = data?.totals || {};

  const donutData = useMemo(() => {
    return competitors.map((c: any, i: number) => ({
      name: c.name,
      value: sovMetric === "ads" ? c.total_ads : Math.min(c.spend_min, c.spend_max) || c.spend_min,
      color: COLORS[i % COLORS.length],
    }));
  }, [competitors, sovMetric]);

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

  const compNames = useMemo(() => competitors.map((c: any) => c.name), [competitors]);

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
    <PageGate page="ads_overview"><div className="space-y-6">
      <PageHeader
        icon={PieChartIcon}
        title="Part de Voix Publicitaire"
        subtitle="Qui communique le plus, sur quel reseau, a quel moment"
        actions={
          <PeriodFilter
            selectedDays={periodDays}
            onDaysChange={setPeriodDays}
          />
        }
      />

      {isLoading ? (
        <LoadingState message="Chargement des donnees publicitaires..." />
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard icon={Megaphone} iconColor="bg-violet-100 text-violet-600" label="Total pubs" value={formatNumber(totals.total_ads || 0)} sub={`${totals.competitors_count || 0} concurrents`} />
            <StatCard icon={Zap} iconColor="bg-emerald-100 text-emerald-600" label="Pubs actives" value={formatNumber(totals.active_ads || 0)} sub="en cours de diffusion" />
            <StatCard icon={Euro} iconColor="bg-amber-100 text-amber-600" label="Budget estime total" value={formatBudget(totals.spend_min || 0, totals.spend_max || 0)} sub="estimation CPM 3€" />
            <StatCard icon={Users} iconColor="bg-blue-100 text-blue-600" label="Couverture EU" value={formatNumber(totals.reach || 0)} sub="personnes atteintes" />
          </div>

          {/* Part de voix donut + classement */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <SectionCard
              title="Part de voix"
              icon={PieChartIcon}
              iconColor="bg-violet-100 text-violet-600"
              action={
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
              }
            >
              <p className="text-xs text-muted-foreground mb-4">
                {sovMetric === "ads"
                  ? "Proportion du nombre de pubs par concurrent"
                  : "Proportion du budget estime par concurrent"}
              </p>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={donutData}
                      cx="50%"
                      cy="50%"
                      innerRadius={65}
                      outerRadius={105}
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
                        <span className="text-xs text-foreground">{value}</span>
                      )}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </SectionCard>

            <SectionCard title="Classement" icon={Trophy} iconColor="bg-amber-100 text-amber-600">
              <p className="text-xs text-muted-foreground mb-4">
                Les concurrents qui diffusent le plus de publicites sur la periode
              </p>
              <div className="space-y-3">
                {competitors.map((c: any, i: number) => {
                  const maxAds = competitors[0]?.total_ads || 1;
                  const pct = (c.total_ads / maxAds) * 100;
                  const medal = i === 0 ? "\ud83e\uddc1" : i === 1 ? "\ud83e\uddc2" : i === 2 ? "\ud83e\uddc3" : null;
                  return (
                    <div key={c.id} className="flex items-center gap-3">
                      <span className="text-sm font-semibold w-6 text-center text-muted-foreground shrink-0">
                        {medal || `${i + 1}`}
                      </span>
                      {c.logo_url ? (
                        <img src={c.logo_url} alt="" className="h-7 w-7 rounded-full object-cover shrink-0" />
                      ) : (
                        <div className="h-7 w-7 rounded-full bg-muted flex items-center justify-center shrink-0">
                          <span className="text-[11px] font-bold text-muted-foreground">
                            {c.name.charAt(0)}
                          </span>
                        </div>
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
                        {c.pages && c.pages.length > 1 && (
                          <p className="text-[10px] text-muted-foreground mt-1">
                            {c.pages.length} pages : {c.pages.slice(0, 3).join(", ")}{c.pages.length > 3 ? "\u2026" : ""}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </SectionCard>
          </div>

          {/* Repartition par plateforme */}
          <SectionCard title="Mix plateforme par concurrent" icon={BarChart3} iconColor="bg-blue-100 text-blue-600">
            <p className="text-xs text-muted-foreground mb-4">
              Sur quels reseaux chaque concurrent diffuse ses publicites (% du volume)
            </p>
            <div style={{ height: Math.max(250, competitors.length * 40 + 60) }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={platformData} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={100} />
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
          </SectionCard>

          {/* Timeline */}
          <SectionCard title="Pression publicitaire dans le temps" icon={TrendingUp} iconColor="bg-emerald-100 text-emerald-600">
            <p className="text-xs text-muted-foreground mb-4">
              Nombre de nouvelles publicites lancees par semaine, par concurrent
            </p>
            <div className="h-[320px]">
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
          </SectionCard>

          {/* Repartition par type */}
          <SectionCard title="Objectif publicitaire" icon={Layers} iconColor="bg-pink-100 text-pink-600">
            <p className="text-xs text-muted-foreground mb-4">
              Branding (notoriete), Performance (conversion) ou Drive-to-Store pour chaque concurrent
            </p>
            <div className="h-[300px]">
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
                      name={TYPE_LABELS[t] || t}
                      radius={[4, 4, 0, 0]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </SectionCard>

          {/* Tableau detaille */}
          <SectionCard title="Classement detaille" icon={BarChart3} iconColor="bg-indigo-100 text-indigo-600">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-3 pr-4 font-medium text-muted-foreground">#</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground">Concurrent</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground text-right">Pubs</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground text-right">Actives</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground text-right">Part de voix</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground text-right">Budget estime</th>
                    <th className="pb-3 pr-4 font-medium text-muted-foreground text-right">Couverture</th>
                    <th className="pb-3 font-medium text-muted-foreground">Plateformes</th>
                  </tr>
                </thead>
                <tbody>
                  {competitors.map((c: any, i: number) => {
                    const medal = i === 0 ? "\ud83e\uddc1" : i === 1 ? "\ud83e\uddc2" : i === 2 ? "\ud83e\uddc3" : null;
                    const platforms = Object.keys(c.by_platform || {});
                    return (
                      <tr key={c.id} className="border-b last:border-0 hover:bg-muted/30 transition-colors">
                        <td className="py-3 pr-4 text-sm font-semibold text-muted-foreground">
                          {medal || i + 1}
                        </td>
                        <td className="py-3 pr-4">
                          <div className="flex items-center gap-2">
                            {c.logo_url ? (
                              <img src={c.logo_url} alt="" className="h-6 w-6 rounded-full object-cover" />
                            ) : (
                              <div className="h-6 w-6 rounded-full bg-muted flex items-center justify-center">
                                <span className="text-[10px] font-bold text-muted-foreground">
                                  {c.name.charAt(0)}
                                </span>
                              </div>
                            )}
                            <div>
                              <span className="font-medium">{c.name}</span>
                              {c.pages && c.pages.length > 1 && (
                                <p className="text-[10px] text-muted-foreground">
                                  {c.pages.length} pages
                                </p>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="py-3 pr-4 text-right font-medium">{c.total_ads}</td>
                        <td className="py-3 pr-4 text-right">{c.active_ads}</td>
                        <td className="py-3 pr-4 text-right">
                          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-violet-50 text-violet-700">
                            {c.sov_pct}%
                          </span>
                        </td>
                        <td className="py-3 pr-4 text-right text-xs">
                          {formatBudget(c.spend_min, c.spend_max)}
                        </td>
                        <td className="py-3 pr-4 text-right">{formatNumber(c.reach)}</td>
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
          </SectionCard>
        </>
      )}
    </div></PageGate>
  );
}
