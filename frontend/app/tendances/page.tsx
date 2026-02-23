"use client";

import { useState, useMemo } from "react";
import { useAPI } from "@/lib/use-api";
import { formatNumber } from "@/lib/utils";
import { exportCSV, exportXLSX, ExportColumn } from "@/lib/export";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, Area, AreaChart,
} from "recharts";
import {
  TrendingUp, TrendingDown, Minus, Calendar, Filter,
  Instagram, Youtube, Music, Smartphone, Megaphone,
  Star, Users, Eye, Heart, BarChart3, Globe, ArrowUpRight,
  ArrowDownRight, ChevronDown, Sparkles, Activity,
  MessageCircle, ThumbsUp, Download, Target, Zap,
  Search, Newspaper, RefreshCw, ExternalLink,
} from "lucide-react";
import { API_BASE, getCurrentAdvertiserId } from "@/lib/api";

/* ─── Types ─────────────────────────────────────── */

interface DataPoint { date: string; value: number | null }

interface MetricSeries {
  [metric: string]: DataPoint[];
}

interface CompetitorTrends {
  name: string;
  is_brand: boolean;
  logo_url: string | null;
  instagram: MetricSeries;
  tiktok: MetricSeries;
  youtube: MetricSeries;
  playstore: MetricSeries;
  appstore: MetricSeries;
  ads: MetricSeries;
  snapchat: MetricSeries;
  google_trends: MetricSeries;
}

interface TimeseriesResponse {
  date_from: string;
  date_to: string;
  competitors: Record<string, CompetitorTrends>;
}

interface DeltaValue {
  value: number | null;
  previous: number | null;
  delta: number | null;
  delta_pct: number | null;
}

interface CompetitorSummary {
  competitor_id: number;
  name: string;
  is_brand: boolean;
  logo_url: string | null;
  metrics: Record<string, DeltaValue>;
}

interface SummaryResponse {
  date_from: string;
  date_to: string;
  competitors: CompetitorSummary[];
}

interface NewsArticle {
  id: number;
  competitor_id: number;
  competitor_name: string;
  title: string;
  link: string;
  source: string;
  date: string;
  snippet: string;
  thumbnail: string;
  collected_at: string | null;
}

interface TrendsInterestResponse {
  competitors: Record<string, { name: string; data: DataPoint[] }>;
  source: string;
}

interface TrendsRelatedResponse {
  competitor_id: number;
  name: string;
  rising: { query: string; value: number }[];
  top: { query: string; value: number }[];
}

function SnapIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12.2 2c-3.3 0-5.8 1.6-6.8 4.4-.3.9-.4 1.9-.4 3v1.5c-.5-.1-1.1-.2-1.5 0-.5.2-.7.7-.5 1.2.2.4.5.6.9.7.2.1.5.1.7.1.1.1.2.3.2.5-.2.8-.5 1.5-1 2.1-.6.8-1.3 1.4-2.1 1.8-.5.2-.8.7-.7 1.2.1.5.4.8.9 1 .7.2 1.4.3 2.1.5.1.3.3.8.5 1.1.2.3.5.5.9.5.3 0 .7-.1 1.2-.3.7-.2 1.5-.5 2.7-.5s2 .3 2.7.5c.4.2.8.3 1.2.3.4 0 .7-.2.9-.5.2-.3.3-.7.5-1.1.7-.1 1.4-.3 2.1-.5.5-.2.8-.5.9-1 .1-.5-.2-1-.7-1.2-.8-.4-1.6-1-2.1-1.8-.5-.6-.8-1.3-1-2.1 0-.2.1-.4.2-.5.2 0 .5 0 .7-.1.4-.1.7-.3.9-.7.2-.5 0-1-.5-1.2-.4-.2-1-.1-1.5 0V9.4c0-1.1-.1-2.1-.4-3C18 3.6 15.5 2 12.2 2z" />
    </svg>
  );
}

/* ─── Constants ─────────────────────────────────── */

const COLORS = [
  "#6366f1", "#ec4899", "#f59e0b", "#10b981", "#3b82f6",
  "#8b5cf6", "#ef4444", "#14b8a6", "#f97316", "#06b6d4",
  "#a855f7", "#84cc16", "#e11d48", "#0ea5e9", "#d946ef",
];

const DATE_PRESETS = [
  { label: "7j", days: 7 },
  { label: "14j", days: 14 },
  { label: "30j", days: 30 },
  { label: "90j", days: 90 },
];

const METRIC_CATEGORIES = [
  {
    id: "social",
    label: "Reseaux sociaux",
    icon: <Activity className="h-4 w-4" />,
    metrics: [
      { key: "ig_followers", label: "Abonnes Instagram", icon: <Instagram className="h-3.5 w-3.5" />, source: "instagram", field: "followers", format: "number" },
      { key: "ig_engagement", label: "Engagement Instagram", icon: <Heart className="h-3.5 w-3.5" />, source: "instagram", field: "engagement_rate", format: "percent" },
      { key: "ig_posts", label: "Posts Instagram", icon: <MessageCircle className="h-3.5 w-3.5" />, source: "instagram", field: "posts_count", format: "number" },
      { key: "tt_followers", label: "Abonnes TikTok", icon: <Music className="h-3.5 w-3.5" />, source: "tiktok", field: "followers", format: "number" },
      { key: "tt_likes", label: "Likes TikTok", icon: <ThumbsUp className="h-3.5 w-3.5" />, source: "tiktok", field: "likes", format: "number" },
      { key: "yt_subscribers", label: "Abonnes YouTube", icon: <Youtube className="h-3.5 w-3.5" />, source: "youtube", field: "subscribers", format: "number" },
      { key: "yt_views", label: "Vues YouTube", icon: <Eye className="h-3.5 w-3.5" />, source: "youtube", field: "total_views", format: "number" },
      { key: "yt_engagement", label: "Engagement YouTube", icon: <Heart className="h-3.5 w-3.5" />, source: "youtube", field: "engagement_rate", format: "percent" },
      { key: "snap_subscribers", label: "Abonnes Snapchat", icon: <SnapIcon className="h-3.5 w-3.5" />, source: "snapchat", field: "subscribers", format: "number" },
      { key: "snap_engagement", label: "Engagement Snapchat", icon: <SnapIcon className="h-3.5 w-3.5" />, source: "snapchat", field: "engagement_rate", format: "percent" },
      { key: "snap_ads", label: "Pubs Snapchat", icon: <SnapIcon className="h-3.5 w-3.5" />, source: "snapchat", field: "ads_count", format: "number" },
      { key: "snap_impressions", label: "Impressions Snapchat", icon: <SnapIcon className="h-3.5 w-3.5" />, source: "snapchat", field: "impressions", format: "number" },
    ],
  },
  {
    id: "apps",
    label: "Applications",
    icon: <Smartphone className="h-4 w-4" />,
    metrics: [
      { key: "ps_rating", label: "Note Play Store", icon: <Star className="h-3.5 w-3.5" />, source: "playstore", field: "rating", format: "decimal" },
      { key: "ps_reviews", label: "Avis Play Store", icon: <MessageCircle className="h-3.5 w-3.5" />, source: "playstore", field: "reviews_count", format: "number" },
      { key: "ps_downloads", label: "Telechargements Play Store", icon: <Download className="h-3.5 w-3.5" />, source: "playstore", field: "downloads", format: "number" },
      { key: "as_rating", label: "Note App Store", icon: <Star className="h-3.5 w-3.5" />, source: "appstore", field: "rating", format: "decimal" },
      { key: "as_reviews", label: "Avis App Store", icon: <MessageCircle className="h-3.5 w-3.5" />, source: "appstore", field: "reviews_count", format: "number" },
    ],
  },
  {
    id: "ads",
    label: "Publicites",
    icon: <Megaphone className="h-4 w-4" />,
    metrics: [
      { key: "ads_active", label: "Pubs actives", icon: <Target className="h-3.5 w-3.5" />, source: "ads", field: "active_count", format: "number" },
      { key: "ads_spend", label: "Budget pub (max)", icon: <BarChart3 className="h-3.5 w-3.5" />, source: "ads", field: "spend_max", format: "euro" },
      { key: "ads_reach", label: "Couverture EU", icon: <Globe className="h-3.5 w-3.5" />, source: "ads", field: "total_reach", format: "number" },
    ],
  },
  {
    id: "google_trends",
    label: "Recherche Google",
    icon: <Search className="h-4 w-4" />,
    metrics: [
      { key: "gt_interest", label: "Interet de recherche", icon: <TrendingUp className="h-3.5 w-3.5" />, source: "google_trends", field: "interest", format: "number" },
    ],
  },
  {
    id: "presse",
    label: "Presse",
    icon: <Newspaper className="h-4 w-4" />,
    metrics: [],  // Custom rendering, no sparkline metrics
  },
];

const ALL_METRICS = METRIC_CATEGORIES.flatMap((c) => c.metrics);

/* ─── Helpers ───────────────────────────────────── */

function fmt(value: number | null | undefined, format: string): string {
  if (value == null) return "—";
  switch (format) {
    case "percent": return `${value.toFixed(2)}%`;
    case "decimal": return value.toFixed(2);
    case "euro": return `${formatNumber(Math.round(value))} €`;
    default: return formatNumber(value);
  }
}

function DeltaBadge({ delta, pct }: { delta: number | null; pct: number | null }) {
  if (delta == null || pct == null) return <span className="text-[10px] text-muted-foreground">—</span>;
  const isUp = delta > 0;
  const isFlat = Math.abs(pct) < 0.5;
  if (isFlat) return (
    <span className="inline-flex items-center gap-0.5 text-[11px] text-muted-foreground font-medium">
      <Minus className="h-3 w-3" /> stable
    </span>
  );
  return (
    <span className={`inline-flex items-center gap-0.5 text-[11px] font-semibold ${isUp ? "text-emerald-600" : "text-red-500"}`}>
      {isUp ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
      {isUp ? "+" : ""}{pct.toFixed(1)}%
    </span>
  );
}

function Sparkline({ data, color = "#6366f1", height = 32 }: { data: DataPoint[]; color?: string; height?: number }) {
  if (!data || data.length < 2) return <div className="h-8 w-full" />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <defs>
          <linearGradient id={`sparkGrad-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey="value" stroke={color} strokeWidth={1.5} fill={`url(#sparkGrad-${color.replace("#", "")})`} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function ExportMenu({ onCSV, onXLSX }: { onCSV: () => void; onXLSX: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border bg-white hover:bg-muted/50 transition-colors text-muted-foreground hover:text-foreground"
      >
        <Download className="h-3.5 w-3.5" />
        Exporter
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 bg-white rounded-lg border shadow-lg z-50 py-1 min-w-[120px]">
          <button onClick={() => { onCSV(); setOpen(false); }} className="w-full text-left px-3 py-1.5 text-xs hover:bg-muted/50 transition-colors">
            CSV
          </button>
          <button onClick={() => { onXLSX(); setOpen(false); }} className="w-full text-left px-3 py-1.5 text-xs hover:bg-muted/50 transition-colors">
            Excel (XLSX)
          </button>
        </div>
      )}
    </div>
  );
}

function formatDateLabel(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
  } catch { return iso; }
}

/* ─── Main Page ─────────────────────────────────── */

export default function TendancesPage() {
  const [days, setDays] = useState(14);
  const [selectedCategory, setSelectedCategory] = useState("social");
  const [expandedChart, setExpandedChart] = useState<string | null>(null);
  const [hiddenCompetitors, setHiddenCompetitors] = useState<Set<string>>(new Set());

  const dateFrom = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() - days);
    return d.toISOString().split("T")[0];
  }, [days]);
  const dateTo = useMemo(() => new Date().toISOString().split("T")[0], []);

  const { data: tsData, isLoading: tsLoading } = useAPI<TimeseriesResponse>(
    `/trends/timeseries?date_from=${dateFrom}&date_to=${dateTo}`
  );
  const { data: summaryData, isLoading: sumLoading } = useAPI<SummaryResponse>(
    `/trends/summary?date_from=${dateFrom}&date_to=${dateTo}`
  );

  const competitors = tsData?.competitors || {};
  const compEntries = Object.entries(competitors);
  const summaries = summaryData?.competitors || [];

  // Sort: brand first, then by name
  const sortedSummaries = useMemo(
    () => [...summaries].sort((a, b) => (b.is_brand ? 1 : 0) - (a.is_brand ? 1 : 0) || a.name.localeCompare(b.name)),
    [summaries]
  );

  const selectedCat = METRIC_CATEGORIES.find((c) => c.id === selectedCategory)!;

  // Google News data
  const { data: newsData, isLoading: newsLoading } = useAPI<{ articles: NewsArticle[]; total: number }>(
    selectedCategory === "presse" ? `/google/news` : null
  );
  const [newsRefreshing, setNewsRefreshing] = useState(false);
  const [newsFilter, setNewsFilter] = useState<number | null>(null);

  async function refreshNews() {
    setNewsRefreshing(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const advId = getCurrentAdvertiserId();
      if (advId) headers["X-Advertiser-Id"] = advId;
      await fetch(`${API_BASE}/google/news/refresh`, { method: "POST", headers });
    } catch (e) {
      // ignore
    } finally {
      setNewsRefreshing(false);
    }
  }

  const filteredNews = useMemo(() => {
    const articles = newsData?.articles || [];
    if (!newsFilter) return articles;
    return articles.filter((a) => a.competitor_id === newsFilter);
  }, [newsData, newsFilter]);

  // Unique competitor names from news
  const newsCompetitors = useMemo(() => {
    const articles = newsData?.articles || [];
    const map = new Map<number, string>();
    for (const a of articles) {
      if (!map.has(a.competitor_id)) map.set(a.competitor_id, a.competitor_name);
    }
    return Array.from(map.entries());
  }, [newsData]);

  // Build chart data: merge all competitors' timeseries into unified date rows
  function buildChartData(source: string, field: string) {
    const dateMap: Record<string, Record<string, number | null>> = {};
    for (const [compId, comp] of compEntries) {
      if (hiddenCompetitors.has(compId)) continue;
      const series = (comp as any)[source]?.[field] as DataPoint[] | undefined;
      if (!series) continue;
      for (const pt of series) {
        const day = pt.date.split("T")[0];
        if (!dateMap[day]) dateMap[day] = {};
        dateMap[day][comp.name] = pt.value;
      }
    }
    return Object.entries(dateMap)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, vals]) => ({ date, ...vals }));
  }

  // Smart insights: detect biggest movers
  const insights = useMemo(() => {
    if (!summaries.length) return [];
    const results: { text: string; severity: "up" | "down" | "info" }[] = [];

    for (const comp of summaries) {
      for (const [key, val] of Object.entries(comp.metrics)) {
        if (!val.delta_pct) continue;
        const meta = ALL_METRICS.find((m) => m.key === key);
        if (!meta) continue;

        if (val.delta_pct > 5) {
          results.push({
            text: `${comp.name} : ${meta.label} en hausse de +${val.delta_pct.toFixed(1)}%`,
            severity: "up",
          });
        } else if (val.delta_pct < -5) {
          results.push({
            text: `${comp.name} : ${meta.label} en baisse de ${val.delta_pct.toFixed(1)}%`,
            severity: "down",
          });
        }
      }
    }

    // Sort by absolute delta
    results.sort((a, b) => {
      const aNum = parseFloat(a.text.match(/[+-]?\d+\.?\d*/)?.[0] || "0");
      const bNum = parseFloat(b.text.match(/[+-]?\d+\.?\d*/)?.[0] || "0");
      return Math.abs(bNum) - Math.abs(aNum);
    });

    return results.slice(0, 8);
  }, [summaries]);

  // ─── Export helpers ───
  function exportRankingTable(format: "csv" | "xlsx") {
    const columns: ExportColumn[] = [
      { key: "name", label: "Concurrent" },
      ...selectedCat.metrics.map((m) => ({
        key: m.key,
        label: m.label,
        format: (v: any) => (v?.value != null ? v.value : ""),
      })),
      ...selectedCat.metrics.map((m) => ({
        key: `${m.key}_delta`,
        label: `${m.label} (variation %)`,
        format: (v: any) => (v?.delta_pct != null ? `${v.delta_pct}%` : ""),
      })),
    ];
    const rows = sortedSummaries.map((comp) => {
      const row: Record<string, any> = { name: comp.name };
      for (const m of selectedCat.metrics) {
        row[m.key] = comp.metrics[m.key];
        row[`${m.key}_delta`] = comp.metrics[m.key];
      }
      return row;
    });
    const fn = `tendances_${selectedCat.id}_${dateFrom}_${dateTo}`;
    format === "csv" ? exportCSV(rows, columns, fn) : exportXLSX(rows, columns, fn);
  }

  function exportChartData(metricKey: string, source: string, field: string, label: string, format: "csv" | "xlsx") {
    const chartData = buildChartData(source, field);
    const compNames = compEntries.filter(([id]) => !hiddenCompetitors.has(id)).map(([, c]) => c.name);
    const columns: ExportColumn[] = [
      { key: "date", label: "Date" },
      ...compNames.map((n) => ({ key: n, label: n })),
    ];
    const fn = `tendances_${metricKey}_${dateFrom}_${dateTo}`;
    format === "csv" ? exportCSV(chartData, columns, fn) : exportXLSX(chartData, columns, fn);
  }

  const isLoading = tsLoading || sumLoading;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-indigo-500" />
            Tendances
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Evolution de tous les indicateurs dans le temps
          </p>
        </div>

        {/* Date range selector */}
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          <div className="flex bg-muted rounded-lg p-0.5">
            {DATE_PRESETS.map((p) => (
              <button
                key={p.days}
                onClick={() => setDays(p.days)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                  days === p.days
                    ? "bg-white shadow-sm text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Smart Insights */}
      {insights.length > 0 && (
        <div className="rounded-2xl border bg-gradient-to-br from-indigo-50/50 to-violet-50/50 p-4">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="h-4 w-4 text-indigo-500" />
            <span className="text-sm font-semibold">Mouvements notables</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {insights.map((ins, i) => (
              <div key={i} className={`flex items-start gap-2 text-[12px] px-3 py-2 rounded-xl ${
                ins.severity === "up" ? "bg-emerald-50 text-emerald-800" :
                ins.severity === "down" ? "bg-red-50 text-red-800" :
                "bg-slate-50 text-slate-700"
              }`}>
                {ins.severity === "up" ? <TrendingUp className="h-3.5 w-3.5 mt-0.5 shrink-0" /> :
                 ins.severity === "down" ? <TrendingDown className="h-3.5 w-3.5 mt-0.5 shrink-0" /> :
                 <Minus className="h-3.5 w-3.5 mt-0.5 shrink-0" />}
                <span>{ins.text}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Competitor toggle chips */}
      {compEntries.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {compEntries.map(([compId, comp], i) => {
            const hidden = hiddenCompetitors.has(compId);
            return (
              <button
                key={compId}
                onClick={() => {
                  const next = new Set(hiddenCompetitors);
                  hidden ? next.delete(compId) : next.add(compId);
                  setHiddenCompetitors(next);
                }}
                className={`inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border transition-all ${
                  hidden
                    ? "bg-muted/50 text-muted-foreground border-transparent opacity-50"
                    : "bg-white shadow-sm border-gray-200"
                }`}
              >
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                {comp.name}
                {comp.is_brand && <span className="text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full font-bold">Vous</span>}
              </button>
            );
          })}
        </div>
      )}

      {/* Category tabs */}
      <div className="flex gap-2 border-b pb-2">
        {METRIC_CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setSelectedCategory(cat.id)}
            className={`inline-flex items-center gap-1.5 text-sm font-medium px-4 py-2 rounded-t-lg transition-all border-b-2 ${
              selectedCategory === cat.id
                ? "border-indigo-500 text-indigo-600 bg-indigo-50/50"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {cat.icon}
            {cat.label}
          </button>
        ))}
      </div>

      {/* ─── Presse tab (custom rendering) ─── */}
      {selectedCategory === "presse" ? (
        <div className="space-y-4">
          {/* Toolbar: filter + refresh */}
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setNewsFilter(null)}
                className={`text-xs px-3 py-1.5 rounded-full border transition-all ${
                  !newsFilter ? "bg-indigo-50 border-indigo-200 text-indigo-700" : "bg-white text-muted-foreground"
                }`}
              >
                Tous
              </button>
              {newsCompetitors.map(([id, name]) => (
                <button
                  key={id}
                  onClick={() => setNewsFilter(newsFilter === id ? null : id)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-all ${
                    newsFilter === id ? "bg-indigo-50 border-indigo-200 text-indigo-700" : "bg-white text-muted-foreground"
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
            <button
              onClick={refreshNews}
              disabled={newsRefreshing}
              className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border bg-white hover:bg-muted/50 transition-colors text-muted-foreground hover:text-foreground disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${newsRefreshing ? "animate-spin" : ""}`} />
              {newsRefreshing ? "Collecte..." : "Actualiser"}
            </button>
          </div>

          {newsLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="rounded-2xl border bg-card p-4 animate-pulse">
                  <div className="h-4 bg-muted rounded w-3/4 mb-2" />
                  <div className="h-3 bg-muted rounded w-1/2" />
                </div>
              ))}
            </div>
          ) : filteredNews.length === 0 ? (
            <div className="rounded-2xl border bg-card p-8 text-center">
              <Newspaper className="h-10 w-10 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground mb-2">Aucun article collecte</p>
              <p className="text-xs text-muted-foreground/70 mb-4">
                Cliquez sur Actualiser pour collecter les dernieres actualites presse.
              </p>
              <button
                onClick={refreshNews}
                disabled={newsRefreshing}
                className="inline-flex items-center gap-1.5 text-xs font-medium px-4 py-2 rounded-lg bg-indigo-500 text-white hover:bg-indigo-600 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${newsRefreshing ? "animate-spin" : ""}`} />
                Collecter les actualites
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredNews.map((article) => (
                <a
                  key={article.id}
                  href={article.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block rounded-2xl border bg-card p-4 hover:bg-muted/30 transition-colors group"
                >
                  <div className="flex gap-4">
                    {article.thumbnail && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={article.thumbnail}
                        alt=""
                        className="h-20 w-28 rounded-lg object-cover shrink-0"
                      />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="text-sm font-semibold leading-snug line-clamp-2 group-hover:text-indigo-600 transition-colors">
                          {article.title}
                        </h3>
                        <ExternalLink className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                      {article.snippet && (
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{article.snippet}</p>
                      )}
                      <div className="flex items-center gap-3 mt-2">
                        <span className="text-[11px] font-medium text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">
                          {article.competitor_name}
                        </span>
                        {article.source && (
                          <span className="text-[11px] text-muted-foreground">{article.source}</span>
                        )}
                        {article.date && (
                          <span className="text-[11px] text-muted-foreground">{article.date}</span>
                        )}
                      </div>
                    </div>
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>
      ) : isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-2xl border bg-card p-4 animate-pulse">
              <div className="h-4 bg-muted rounded w-1/2 mb-4" />
              <div className="h-32 bg-muted rounded" />
            </div>
          ))}
        </div>
      ) : (
        <>
          {/* ─── Summary Cards Grid ─── */}
          <div className="space-y-6">
            {selectedCat.metrics.map((metric) => {
              const chartData = buildChartData(metric.source, metric.field);
              const isExpanded = expandedChart === metric.key;

              return (
                <div key={metric.key} className="rounded-2xl border bg-card overflow-hidden">
                  {/* Metric header + competitor values */}
                  <button
                    onClick={() => setExpandedChart(isExpanded ? null : metric.key)}
                    className="w-full text-left p-4 hover:bg-muted/30 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="p-1.5 rounded-lg bg-indigo-50 text-indigo-600">{metric.icon}</span>
                        <span className="font-semibold text-sm">{metric.label}</span>
                      </div>
                      <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                    </div>

                    {/* Competitor values row */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5 gap-3">
                      {sortedSummaries.map((comp, i) => {
                        const val = comp.metrics[metric.key];
                        const compId = String(comp.competitor_id);
                        const compData = competitors[compId];
                        const series = compData ? (compData as any)[metric.source]?.[metric.field] as DataPoint[] : [];
                        const color = COLORS[compEntries.findIndex(([id]) => id === compId) % COLORS.length];

                        return (
                          <div key={comp.competitor_id} className={`rounded-xl p-2.5 border ${comp.is_brand ? "bg-violet-50/50 border-violet-200" : "bg-muted/30 border-transparent"}`}>
                            <div className="flex items-center gap-1.5 mb-1">
                              {comp.logo_url && (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img src={comp.logo_url} alt="" className="h-4 w-4 rounded-full object-cover" />
                              )}
                              <span className="text-[10px] font-medium text-muted-foreground truncate">{comp.name}</span>
                              {comp.is_brand && <span className="text-[8px] bg-violet-100 text-violet-600 px-1 rounded font-bold">Vous</span>}
                            </div>
                            <div className="text-base font-bold tabular-nums">
                              {val ? fmt(val.value, metric.format) : "—"}
                            </div>
                            <div className="flex items-center justify-between">
                              <DeltaBadge delta={val?.delta ?? null} pct={val?.delta_pct ?? null} />
                            </div>
                            <div className="mt-1">
                              <Sparkline data={series || []} color={color} height={24} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </button>

                  {/* Expanded: full chart */}
                  {isExpanded && chartData.length > 0 && (
                    <div className="px-4 pb-4 border-t">
                      <div className="flex justify-end mt-3 mb-1">
                        <ExportMenu
                          onCSV={() => exportChartData(metric.key, metric.source, metric.field, metric.label, "csv")}
                          onXLSX={() => exportChartData(metric.key, metric.source, metric.field, metric.label, "xlsx")}
                        />
                      </div>
                      <div className="h-72">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                            <XAxis
                              dataKey="date"
                              tickFormatter={formatDateLabel}
                              tick={{ fontSize: 11 }}
                              axisLine={false}
                              tickLine={false}
                            />
                            <YAxis
                              tick={{ fontSize: 11 }}
                              axisLine={false}
                              tickLine={false}
                              tickFormatter={(v) => {
                                if (metric.format === "percent") return `${v}%`;
                                if (metric.format === "euro") return `${formatNumber(v)}€`;
                                return formatNumber(v);
                              }}
                            />
                            <Tooltip
                              labelFormatter={formatDateLabel}
                              formatter={(value: number) => [fmt(value, metric.format), ""]}
                              contentStyle={{
                                borderRadius: "12px",
                                border: "1px solid #e5e7eb",
                                boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                                fontSize: "12px",
                              }}
                            />
                            <Legend
                              wrapperStyle={{ fontSize: "11px" }}
                            />
                            {compEntries.map(([compId, comp], i) => {
                              if (hiddenCompetitors.has(compId)) return null;
                              return (
                                <Line
                                  key={compId}
                                  type="monotone"
                                  dataKey={comp.name}
                                  stroke={COLORS[i % COLORS.length]}
                                  strokeWidth={comp.is_brand ? 3 : 1.5}
                                  dot={false}
                                  activeDot={{ r: 4 }}
                                  strokeDasharray={comp.is_brand ? undefined : undefined}
                                />
                              );
                            })}
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* ─── Ranking tables ─── */}
          <div className="rounded-2xl border bg-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-sm flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-indigo-500" />
                Classement par metrique
              </h2>
              <ExportMenu
                onCSV={() => exportRankingTable("csv")}
                onXLSX={() => exportRankingTable("xlsx")}
              />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-2 font-medium text-muted-foreground">Concurrent</th>
                    {selectedCat.metrics.map((m) => (
                      <th key={m.key} className="text-right py-2 px-2 font-medium text-muted-foreground whitespace-nowrap">
                        <span className="inline-flex items-center gap-1">{m.icon}{m.label.split(" ").slice(-1)}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedSummaries.map((comp) => (
                    <tr key={comp.competitor_id} className={`border-b last:border-0 ${comp.is_brand ? "bg-violet-50/30" : ""}`}>
                      <td className="py-2.5 px-2">
                        <div className="flex items-center gap-2">
                          {comp.logo_url && (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={comp.logo_url} alt="" className="h-5 w-5 rounded-full object-cover" />
                          )}
                          <span className="font-medium">{comp.name}</span>
                          {comp.is_brand && <span className="text-[8px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full font-bold">Vous</span>}
                        </div>
                      </td>
                      {selectedCat.metrics.map((m) => {
                        const val = comp.metrics[m.key];
                        return (
                          <td key={m.key} className="text-right py-2.5 px-2">
                            <div className="font-semibold tabular-nums">{val ? fmt(val.value, m.format) : "—"}</div>
                            <DeltaBadge delta={val?.delta ?? null} pct={val?.delta_pct ?? null} />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* ─── News Dashboard Widget ─── */}
      <LatestNewsWidget />
    </div>
  );
}


/* ─── Latest News Widget ──────────────────────── */

function LatestNewsWidget() {
  const { data, isLoading } = useAPI<{ articles: NewsArticle[] }>("/google/news/latest");
  const articles = data?.articles || [];

  if (isLoading || articles.length === 0) return null;

  return (
    <div className="rounded-2xl border bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-sm flex items-center gap-2">
          <Newspaper className="h-4 w-4 text-indigo-500" />
          Actualites presse
        </h2>
      </div>
      <div className="space-y-3">
        {articles.slice(0, 5).map((article) => (
          <a
            key={article.id}
            href={article.link}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start gap-3 group"
          >
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium leading-snug line-clamp-1 group-hover:text-indigo-600 transition-colors">
                {article.title}
              </p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[10px] text-indigo-500 font-medium">{article.competitor_name}</span>
                {article.source && <span className="text-[10px] text-muted-foreground">{article.source}</span>}
                {article.date && <span className="text-[10px] text-muted-foreground">{article.date}</span>}
              </div>
            </div>
            <ExternalLink className="h-3 w-3 text-muted-foreground shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
          </a>
        ))}
      </div>
    </div>
  );
}
