"use client";

import { useEffect, useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import {
  competitorsAPI,
  playstoreAPI,
  appstoreAPI,
  asoAPI,
  brandAPI,
  AppData,
  CompetitorListItem,
} from "@/lib/api";
import { formatNumber, formatDate } from "@/lib/utils";
import {
  RefreshCw,
  ExternalLink,
  Star,
  Smartphone,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  Crown,
  Trophy,
  Download,
  MessageSquare,
  Clock,
  ChevronRight,
  Sparkles,
  AlertTriangle,
  Search,
  Image,
  Shield,
  Zap,
  Eye,
  Target,
  CheckCircle2,
  XCircle,
  Info,
} from "lucide-react";
import { PeriodFilter, PeriodDays } from "@/components/period-filter";

type Store = "playstore" | "appstore";
type RankingView = "rating" | "reviews" | "downloads";

const STORE_CONFIG = {
  playstore: {
    label: "Play Store",
    gradient: "from-green-500 via-blue-500 to-red-500",
    accent: "text-green-600",
    lightBg: "bg-green-50 dark:bg-green-950/30",
    border: "border-green-200 dark:border-green-900",
    link: (id: string) => `https://play.google.com/store/apps/details?id=${id}`,
  },
  appstore: {
    label: "App Store",
    gradient: "from-blue-500 to-blue-600",
    accent: "text-blue-600",
    lightBg: "bg-blue-50 dark:bg-blue-950/30",
    border: "border-blue-200 dark:border-blue-900",
    link: (id: string) => `https://apps.apple.com/app/id${id}`,
  },
};

const RANKING_VIEWS: { key: RankingView; label: string; icon: React.ReactNode; storeOnly?: Store }[] = [
  { key: "rating", label: "Note", icon: <Star className="h-3 w-3" /> },
  { key: "reviews", label: "Avis", icon: <MessageSquare className="h-3 w-3" /> },
  { key: "downloads", label: "Downloads", icon: <Download className="h-3 w-3" />, storeOnly: "playstore" },
];

const MEDAL = ["bg-amber-400 text-amber-950", "bg-slate-300 text-slate-700", "bg-orange-300 text-orange-800"];

function getRankColor(rank: number, total: number) {
  if (total <= 1) return { bg: "bg-emerald-100", text: "text-emerald-700", border: "border-emerald-200" };
  const pct = rank / (total - 1);
  if (pct === 0) return { bg: "bg-emerald-100", text: "text-emerald-700", border: "border-emerald-200" };
  if (pct <= 0.33) return { bg: "bg-yellow-100", text: "text-yellow-700", border: "border-yellow-200" };
  if (pct <= 0.66) return { bg: "bg-orange-100", text: "text-orange-700", border: "border-orange-200" };
  return { bg: "bg-red-100", text: "text-red-600", border: "border-red-200" };
}

function StarRating({ rating, size = "md" }: { rating: number | null | undefined; size?: "sm" | "md" }) {
  if (!rating) return <span className="text-sm text-muted-foreground">&mdash;</span>;
  const full = Math.floor(rating);
  const partial = rating - full;
  const starSize = size === "sm" ? "h-3 w-3" : "h-4 w-4";
  return (
    <div className="flex items-center gap-1.5">
      <div className="flex items-center gap-0.5">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="relative">
            <Star className={`${starSize} text-muted-foreground/20`} />
            {i <= full && <Star className={`${starSize} text-amber-400 fill-amber-400 absolute inset-0`} />}
            {i === full + 1 && partial > 0 && (
              <div className="absolute inset-0 overflow-hidden" style={{ width: `${partial * 100}%` }}>
                <Star className={`${starSize} text-amber-400 fill-amber-400`} />
              </div>
            )}
          </div>
        ))}
      </div>
      <span className={`${size === "sm" ? "text-xs" : "text-sm"} font-bold tabular-nums`}>{rating.toFixed(1)}</span>
    </div>
  );
}

function GrowthBadge({ value }: { value?: number | null }) {
  if (value === undefined || value === null) return <span className="text-xs text-muted-foreground">&mdash;</span>;
  const isPositive = value > 0;
  const isNegative = value < 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-semibold tabular-nums ${
      isPositive ? "text-emerald-600" : isNegative ? "text-red-500" : "text-muted-foreground"
    }`}>
      {isPositive ? <TrendingUp className="h-3 w-3" /> : isNegative ? <TrendingDown className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
      {isPositive ? "+" : ""}{value.toFixed(1)}%
    </span>
  );
}

export default function AppsPage() {
  const [store, setStore] = useState<Store>("playstore");
  const [rankingView, setRankingView] = useState<RankingView>("rating");
  const [competitors, setCompetitors] = useState<CompetitorListItem[]>([]);
  const [selectedCompetitor, setSelectedCompetitor] = useState<number | null>(null);
  const [appData, setAppData] = useState<AppData[]>([]);
  const [psComparison, setPsComparison] = useState<any[]>([]);
  const [asComparison, setAsComparison] = useState<any[]>([]);
  const [trends, setTrends] = useState<Record<string, any>>({});
  const [brandName, setBrandName] = useState<string | null>(null);
  const [asoData, setAsoData] = useState<any>(null);
  const [asoLoading, setAsoLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [periodDays, setPeriodDays] = useState<PeriodDays>(7);
  const [initialLoad, setInitialLoad] = useState(true);

  useEffect(() => {
    async function loadAll() {
      try {
        const [comp, ps, as_, brand, aso] = await Promise.allSettled([
          competitorsAPI.list(),
          playstoreAPI.getComparison(periodDays),
          appstoreAPI.getComparison(periodDays),
          brandAPI.getProfile(),
          asoAPI.getAnalysis(),
        ]);
        const allComp = comp.status === "fulfilled" ? comp.value : [];
        const withApps = allComp.filter((c) => c.playstore_app_id || c.appstore_app_id);
        setCompetitors(withApps);
        if (ps.status === "fulfilled") setPsComparison(ps.value);
        if (as_.status === "fulfilled") setAsComparison(as_.value);
        if (brand.status === "fulfilled") setBrandName((brand.value as any).company_name || null);
        if (aso.status === "fulfilled") setAsoData(aso.value);
        setAsoLoading(false);
        if (withApps.length > 0 && !selectedCompetitor) setSelectedCompetitor(withApps[0].id);

        // Load trends for all competitors (only on first load)
        if (initialLoad) {
          const trendMap: Record<string, any> = {};
          await Promise.allSettled(
            withApps.map(async (c) => {
              try {
                if (c.playstore_app_id) {
                  const t = await playstoreAPI.getTrends(c.id);
                  trendMap[`ps_${c.id}`] = t;
                }
              } catch {}
              try {
                if (c.appstore_app_id) {
                  const t = await appstoreAPI.getTrends(c.id);
                  trendMap[`as_${c.id}`] = t;
                }
              } catch {}
            })
          );
          setTrends(trendMap);
        }
      } catch (err) {
        console.error("Failed to load:", err);
      } finally {
        if (initialLoad) { setLoading(false); setInitialLoad(false); }
      }
    }
    loadAll();
  }, [periodDays]);

  useEffect(() => {
    if (selectedCompetitor) {
      const api = store === "playstore" ? playstoreAPI : appstoreAPI;
      api.getData(selectedCompetitor).then(setAppData).catch(() => setAppData([]));
    }
  }, [selectedCompetitor, store]);

  const isBrand = (name: string) => brandName && name.toLowerCase() === brandName.toLowerCase();

  async function handleRefreshAll() {
    setFetching(true);
    try {
      const relevantCompetitors = competitors.filter((c) =>
        store === "playstore" ? c.playstore_app_id : c.appstore_app_id
      );
      const api = store === "playstore" ? playstoreAPI : appstoreAPI;
      for (const c of relevantCompetitors) {
        try { await api.fetch(c.id); } catch {}
      }
      const [ps, as_] = await Promise.allSettled([
        playstoreAPI.getComparison(),
        appstoreAPI.getComparison(),
      ]);
      if (ps.status === "fulfilled") setPsComparison(ps.value);
      if (as_.status === "fulfilled") setAsComparison(as_.value);
      if (selectedCompetitor) {
        const selApi = store === "playstore" ? playstoreAPI : appstoreAPI;
        selApi.getData(selectedCompetitor).then(setAppData).catch(() => {});
      }
    } catch (err) {
      console.error("Refresh failed:", err);
    } finally {
      setFetching(false);
    }
  }

  // Cross-store overview
  const crossStoreData = useMemo(() => {
    const map = new Map<number, { id: number; name: string; ps: any; as: any }>();
    psComparison.forEach(c => {
      if (!map.has(c.competitor_id)) map.set(c.competitor_id, { id: c.competitor_id, name: c.competitor_name, ps: null, as: null });
      map.get(c.competitor_id)!.ps = c;
    });
    asComparison.forEach(c => {
      if (!map.has(c.competitor_id)) map.set(c.competitor_id, { id: c.competitor_id, name: c.competitor_name, ps: null, as: null });
      map.get(c.competitor_id)!.as = c;
    });
    return Array.from(map.values())
      .map(c => ({
        ...c,
        avgRating: (() => {
          const ratings: number[] = [];
          if (c.ps?.rating) ratings.push(c.ps.rating);
          if (c.as?.rating) ratings.push(c.as.rating);
          return ratings.length > 0 ? ratings.reduce((a, b) => a + b, 0) / ratings.length : 0;
        })(),
        totalReviews: (c.ps?.reviews_count || 0) + (c.as?.reviews_count || 0),
        storeCount: (c.ps ? 1 : 0) + (c.as ? 1 : 0),
      }))
      .sort((a, b) => b.avgRating - a.avgRating);
  }, [psComparison, asComparison]);

  const currentComparison = store === "playstore" ? psComparison : asComparison;
  const config = STORE_CONFIG[store];

  function getRankingValue(c: any): number {
    if (rankingView === "rating") return c.rating || 0;
    if (rankingView === "reviews") return c.reviews_count || 0;
    if (rankingView === "downloads") return c.downloads_numeric || 0;
    return 0;
  }

  function getRankingLabel(): string {
    if (rankingView === "rating") return "note";
    if (rankingView === "reviews") return "avis";
    if (rankingView === "downloads") return "telechargements";
    return "";
  }

  function formatRankingValue(val: number): string {
    if (rankingView === "rating") return val.toFixed(1);
    return formatNumber(Math.round(val));
  }

  const sorted = [...currentComparison].sort((a, b) => getRankingValue(b) - getRankingValue(a));
  const maxRankingVal = sorted.length > 0 ? getRankingValue(sorted[0]) || 1 : 1;

  const latestData = appData[0];
  const selectedComp = competitors.find(c => c.id === selectedCompetitor);
  const hasStoreForSelected = selectedComp && (store === "playstore" ? selectedComp.playstore_app_id : selectedComp.appstore_app_id);

  const storeUrl = store === "playstore" && selectedComp?.playstore_app_id
    ? config.link(selectedComp.playstore_app_id)
    : store === "appstore" && selectedComp?.appstore_app_id
    ? config.link(selectedComp.appstore_app_id)
    : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-violet-200 border-t-violet-600 animate-spin" />
          <span className="text-sm text-muted-foreground">Chargement des applications...</span>
        </div>
      </div>
    );
  }

  if (competitors.length === 0) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 border border-violet-200/50">
            <Smartphone className="h-5 w-5 text-violet-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">Applications</h1>
            <p className="text-[13px] text-muted-foreground">Play Store & App Store</p>
          </div>
        </div>
        <div className="rounded-2xl border-2 border-dashed border-border bg-card/50 p-12 text-center">
          <div className="flex justify-center mb-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-50">
              <Smartphone className="h-7 w-7 text-violet-400" />
            </div>
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-1">Aucun concurrent configur&eacute;</h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">Ajoutez des concurrents avec des IDs Play Store ou App Store.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 border border-violet-200/50">
            <Smartphone className="h-5 w-5 text-violet-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">Applications</h1>
            <p className="text-[13px] text-muted-foreground">Comparaison multi-stores</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefreshAll} disabled={fetching} className="gap-2">
          <RefreshCw className={`h-3.5 w-3.5 ${fetching ? "animate-spin" : ""}`} />
          Rafra&icirc;chir
        </Button>
      </div>

      {/* Cross-Store Overview */}
      {crossStoreData.length > 0 && (
        <div className="rounded-2xl bg-gradient-to-br from-indigo-950 via-[#1e1b4b] to-violet-950 text-white p-5 sm:p-6 space-y-4 overflow-hidden">
          <div className="flex items-center gap-2.5">
            <Crown className="h-4.5 w-4.5 text-amber-400" />
            <h2 className="text-sm font-semibold">Vue d&apos;ensemble multi-stores</h2>
          </div>
          <div className="overflow-x-auto -mx-5 sm:-mx-6 px-5 sm:px-6">
            <table className="w-full min-w-[500px]">
              <thead>
                <tr className="text-[10px] uppercase tracking-widest text-white/40">
                  <th className="text-left pb-3 font-semibold">#</th>
                  <th className="text-left pb-3 font-semibold">Concurrent</th>
                  <th className="text-right pb-3 font-semibold">Play Store</th>
                  <th className="text-right pb-3 font-semibold">App Store</th>
                  <th className="text-right pb-3 font-semibold">Note moy.</th>
                  <th className="text-right pb-3 font-semibold">Total avis</th>
                </tr>
              </thead>
              <tbody>
                {crossStoreData.map((c, i) => {
                  const csRc = getRankColor(i, crossStoreData.length);
                  const rowHighlight = i === 0 ? "bg-emerald-500/15" : i === crossStoreData.length - 1 ? "bg-red-500/10" : "";
                  return (
                  <tr key={c.id} className={`border-t border-white/10 ${isBrand(c.name) ? "bg-violet-500/15" : rowHighlight}`}>
                    <td className="py-2.5 pr-2">
                      {i < 3 ? (
                        <span className={`inline-flex items-center justify-center h-5 w-5 rounded-full text-[10px] font-bold ${MEDAL[i]}`}>{i + 1}</span>
                      ) : (
                        <span className="text-xs text-white/40 tabular-nums pl-1">{i + 1}</span>
                      )}
                    </td>
                    <td className="py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{c.name}</span>
                        {isBrand(c.name) && (
                          <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-violet-500/30 text-violet-300">Vous</span>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 text-right text-sm tabular-nums">
                      {c.ps ? (
                        <div className="flex items-center justify-end gap-1">
                          <Star className="h-3 w-3 text-amber-400 fill-amber-400" />
                          <span className="text-green-300">{c.ps.rating?.toFixed(1) || "\u2014"}</span>
                        </div>
                      ) : <span className="text-white/20">&mdash;</span>}
                    </td>
                    <td className="py-2.5 text-right text-sm tabular-nums">
                      {c.as ? (
                        <div className="flex items-center justify-end gap-1">
                          <Star className="h-3 w-3 text-amber-400 fill-amber-400" />
                          <span className="text-blue-300">{c.as.rating?.toFixed(1) || "\u2014"}</span>
                        </div>
                      ) : <span className="text-white/20">&mdash;</span>}
                    </td>
                    <td className="py-2.5 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Star className="h-3 w-3 text-amber-400 fill-amber-400" />
                        <span className="text-sm font-bold tabular-nums">{c.avgRating > 0 ? c.avgRating.toFixed(1) : "\u2014"}</span>
                      </div>
                    </td>
                    <td className="py-2.5 text-right">
                      <span className="text-sm font-bold tabular-nums">{formatNumber(c.totalReviews)}</span>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ═══════════════ ASO Analysis Section ═══════════════ */}
      {asoLoading ? (
        <div className="rounded-2xl border bg-card p-6">
          <div className="flex items-center gap-3">
            <div className="h-5 w-5 rounded-full border-2 border-violet-200 border-t-violet-600 animate-spin" />
            <span className="text-sm text-muted-foreground">Analyse ASO en cours...</span>
          </div>
        </div>
      ) : asoData && asoData.competitors?.length > 0 && (
        <AsoSection data={asoData} brandName={brandName} />
      )}

      {/* Store selector */}
      <div className="flex items-center gap-1 p-1 rounded-full bg-card border border-border w-fit">
        {(["playstore", "appstore"] as Store[]).map((s) => {
          const sConfig = STORE_CONFIG[s];
          const sData = s === "playstore" ? psComparison : asComparison;
          const isActive = store === s;
          return (
            <button
              key={s}
              onClick={() => { setStore(s); if (rankingView === "downloads" && s === "appstore") setRankingView("rating"); }}
              className={`relative px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 ${
                isActive ? "text-white shadow-lg" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {isActive && <div className={`absolute inset-0 rounded-full bg-gradient-to-r ${sConfig.gradient}`} />}
              <span className="relative flex items-center gap-2">
                {sConfig.label}
                {sData.length > 0 && (
                  <span className={`text-[10px] tabular-nums ${isActive ? "text-white/70" : "text-muted-foreground"}`}>
                    {sData.length}
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>

      {currentComparison.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-border bg-card/50 p-12 text-center">
          <div className="flex justify-center mb-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-50">
              <Smartphone className="h-7 w-7 text-violet-400" />
            </div>
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-1">Aucune donn&eacute;e {config.label}</h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">Configurez des concurrents avec un ID {config.label}.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Ranking View Selector */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] text-muted-foreground uppercase tracking-widest font-semibold mr-1">Classer par</span>
            {RANKING_VIEWS.filter(rv => !rv.storeOnly || rv.storeOnly === store).map(rv => (
              <button
                key={rv.key}
                onClick={() => setRankingView(rv.key)}
                className={`inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border transition-all ${
                  rankingView === rv.key
                    ? `bg-gradient-to-r ${config.gradient} text-white border-transparent shadow-sm`
                    : "bg-card text-muted-foreground hover:text-foreground border-border hover:border-foreground/20"
                }`}
              >
                {rv.icon}{rv.label}
              </button>
            ))}
          </div>

          {/* Ranked Cards Grid */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {sorted.map((c, i) => {
              const primaryVal = getRankingValue(c);
              const pct = maxRankingVal > 0 ? (primaryVal / maxRankingVal) * 100 : 0;
              const brand = isBrand(c.competitor_name);
              const trendKey = `${store === "playstore" ? "ps" : "as"}_${c.competitor_id}`;
              const trendData = trends[trendKey];
              const isSelected = selectedCompetitor === c.competitor_id;

              const rc = getRankColor(i, sorted.length);

              return (
                <button
                  key={c.competitor_id}
                  onClick={() => setSelectedCompetitor(c.competitor_id)}
                  className={`rounded-xl border p-4 transition-all hover:shadow-md text-left ${rc.bg} ${rc.border} ${
                    brand ? "ring-2 ring-violet-500/40" : ""
                  } ${isSelected ? "ring-2 ring-foreground/20" : ""}`}
                >
                  {/* Header: rank + name */}
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`flex items-center justify-center h-6 w-6 rounded-full text-[10px] font-bold shrink-0 ${
                        i < 3 ? MEDAL[i] : "bg-muted text-muted-foreground"
                      }`}>
                        {i + 1}
                      </span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-semibold truncate">{c.app_name || c.competitor_name}</span>
                          {brand && <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-300 shrink-0">Vous</span>}
                        </div>
                        <span className="text-[11px] text-muted-foreground">{c.competitor_name}</span>
                      </div>
                    </div>
                    <ChevronRight className={`h-4 w-4 shrink-0 transition-colors ${isSelected ? "text-foreground" : "text-muted-foreground/30"}`} />
                  </div>

                  {/* Primary metric */}
                  <div className="mb-2">
                    {rankingView === "rating" ? (
                      <StarRating rating={primaryVal} />
                    ) : (
                      <div className="text-2xl font-bold tabular-nums">{formatRankingValue(primaryVal)}</div>
                    )}
                    <div className="text-[10px] text-muted-foreground uppercase tracking-widest mt-0.5">{getRankingLabel()}</div>
                  </div>
                  {rankingView !== "rating" && (
                    <div className="h-1.5 rounded-full bg-muted overflow-hidden mb-3">
                      <div className={`h-full rounded-full transition-all duration-700 ${
                        i === 0 ? "bg-emerald-500" : i === sorted.length - 1 ? "bg-red-400" : "bg-amber-400"
                      }`}
                        style={{ width: `${pct}%` }} />
                    </div>
                  )}

                  {/* Secondary metrics */}
                  <div className="flex items-center gap-2 flex-wrap mt-2">
                    {rankingView !== "rating" && (
                      <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                        <Star className="h-2.5 w-2.5 fill-amber-400 text-amber-400" />{c.rating?.toFixed(1) || "\u2014"}
                      </span>
                    )}
                    {rankingView !== "reviews" && (
                      <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                        <MessageSquare className="h-2.5 w-2.5" />{formatNumber(c.reviews_count || 0)} avis
                      </span>
                    )}
                    {store === "playstore" && rankingView !== "downloads" && c.downloads && (
                      <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                        <Download className="h-2.5 w-2.5" />{c.downloads}
                      </span>
                    )}
                    {c.version && (
                      <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                        v{c.version}
                      </span>
                    )}
                    {trendData?.trends?.rating && trendData.trends.rating !== "neutral" && (
                      <span className={`inline-flex items-center gap-0.5 text-[10px] font-semibold ${
                        trendData.trends.rating === "up" ? "text-emerald-600" : "text-red-500"
                      }`}>
                        {trendData.trends.rating === "up" ? <TrendingUp className="h-2.5 w-2.5" /> : <TrendingDown className="h-2.5 w-2.5" />}
                        note
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Detailed Table */}
          <div className="rounded-2xl border bg-card overflow-hidden">
            <div className="px-5 py-3 border-b bg-muted/20 flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-100 dark:bg-slate-800">
                <BarChart3 className="h-3.5 w-3.5 text-slate-600 dark:text-slate-400" />
              </div>
              <span className="text-[12px] font-semibold text-foreground">D&eacute;tails complets</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[600px]">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="text-left text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Concurrent</th>
                    <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Note</th>
                    <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Avis</th>
                    {store === "playstore" && (
                      <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Downloads</th>
                    )}
                    <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Version</th>
                    <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Tendance</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((c, i) => {
                    const brand = isBrand(c.competitor_name);
                    const trendKey = `${store === "playstore" ? "ps" : "as"}_${c.competitor_id}`;
                    const trendData = trends[trendKey];
                    const rowRc = getRankColor(i, sorted.length);
                    return (
                      <tr key={c.competitor_id} className={`border-t transition-colors hover:bg-muted/30 ${rowRc.bg} ${brand ? "ring-1 ring-inset ring-violet-300" : ""}`}>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span className={`flex items-center justify-center h-5 w-5 rounded-full text-[10px] font-bold ${i < 3 ? MEDAL[i] : "bg-muted text-muted-foreground"}`}>{i + 1}</span>
                            <div>
                              <div className="flex items-center gap-1.5">
                                <span className="text-sm font-medium">{c.app_name || c.competitor_name}</span>
                                {brand && <span className="text-[8px] font-bold uppercase px-1 py-0.5 rounded bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-300">Vous</span>}
                              </div>
                              <span className="text-[11px] text-muted-foreground">{c.competitor_name}</span>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Star className="h-3 w-3 text-amber-400 fill-amber-400" />
                            <span className="text-sm font-bold tabular-nums">{c.rating?.toFixed(1) || "\u2014"}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right text-sm tabular-nums">{formatNumber(c.reviews_count || 0)}</td>
                        {store === "playstore" && (
                          <td className="px-4 py-3 text-right text-sm tabular-nums">{c.downloads || "\u2014"}</td>
                        )}
                        <td className="px-4 py-3 text-right">
                          {c.version ? (
                            <span className="inline-block text-xs font-medium bg-muted px-2 py-0.5 rounded">v{c.version}</span>
                          ) : <span className="text-sm text-muted-foreground">&mdash;</span>}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {trendData?.trends?.rating ? (
                            <span className={`inline-flex items-center gap-0.5 text-xs font-semibold ${
                              trendData.trends.rating === "up" ? "text-emerald-600" : trendData.trends.rating === "down" ? "text-red-500" : "text-muted-foreground"
                            }`}>
                              {trendData.trends.rating === "up" ? <TrendingUp className="h-3 w-3" /> : trendData.trends.rating === "down" ? <TrendingDown className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
                              {trendData.trends.rating === "up" ? "Hausse" : trendData.trends.rating === "down" ? "Baisse" : "Stable"}
                            </span>
                          ) : <span className="text-xs text-muted-foreground">&mdash;</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Brand Position Insight */}
          {brandName && sorted.length > 1 && (() => {
            const brandIdx = sorted.findIndex(c => isBrand(c.competitor_name));
            if (brandIdx < 0) return null;
            if (brandIdx === 0) return (
              <div className="rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 p-4 flex items-center gap-3">
                <Trophy className="h-5 w-5 text-emerald-600 shrink-0" />
                <p className="text-sm text-emerald-800 dark:text-emerald-200">
                  <span className="font-semibold">{brandName}</span> est leader {config.label} en {getRankingLabel()}.
                </p>
              </div>
            );
            const leaderVal = getRankingValue(sorted[0]);
            const brandVal = getRankingValue(sorted[brandIdx]);
            const gap = leaderVal > 0 ? Math.round(((leaderVal - brandVal) / leaderVal) * 100) : 0;
            return (
              <div className="rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 p-4 flex items-center gap-3">
                <Trophy className="h-5 w-5 text-amber-600 shrink-0" />
                <p className="text-sm text-amber-800 dark:text-amber-200">
                  <span className="font-semibold">{brandName}</span> est {brandIdx + 1}&egrave;me sur {sorted.length} en {getRankingLabel()}, {gap}% derriere le leader.
                </p>
              </div>
            );
          })()}

          {/* Recommendations */}
          {brandName && sorted.length > 1 && (() => {
            const recs: string[] = [];
            const brandItem = sorted.find(c => isBrand(c.competitor_name));
            const brandIdx = sorted.findIndex(c => isBrand(c.competitor_name));
            if (!brandItem) return null;

            // Rating analysis
            const ratingRank = [...currentComparison].sort((a, b) => (b.rating || 0) - (a.rating || 0));
            const brandRatingIdx = ratingRank.findIndex(c => isBrand(c.competitor_name));
            const leader = ratingRank[0];
            if (brandRatingIdx > 0 && leader && leader.rating && brandItem.rating) {
              const diff = (leader.rating - brandItem.rating).toFixed(1);
              if (parseFloat(diff) >= 0.2) {
                recs.push(`Note ${config.label} : ${brandName} (${brandItem.rating.toFixed(1)}) est a ${diff} pts de ${leader.competitor_name} (${leader.rating.toFixed(1)}). Ameliorer l'UX et repondre aux avis negatifs pour combler l'ecart.`);
              }
            }

            // Reviews analysis
            const reviewsRank = [...currentComparison].sort((a, b) => (b.reviews_count || 0) - (a.reviews_count || 0));
            const brandReviewIdx = reviewsRank.findIndex(c => isBrand(c.competitor_name));
            if (brandReviewIdx > 0 && reviewsRank[0] && brandItem.reviews_count) {
              const ratio = reviewsRank[0].reviews_count / Math.max(brandItem.reviews_count, 1);
              if (ratio > 2) {
                recs.push(`${reviewsRank[0].competitor_name} a ${formatNumber(reviewsRank[0].reviews_count)} avis contre ${formatNumber(brandItem.reviews_count)} pour ${brandName} (${ratio.toFixed(0)}x plus). Encourager les utilisateurs a noter l'app via des in-app prompts.`);
              }
            }

            // Downloads analysis (Play Store only)
            if (store === "playstore") {
              const dlRank = [...currentComparison].filter(c => c.downloads_numeric).sort((a, b) => (b.downloads_numeric || 0) - (a.downloads_numeric || 0));
              const brandDlIdx = dlRank.findIndex(c => isBrand(c.competitor_name));
              if (brandDlIdx > 0 && dlRank[0] && brandItem.downloads_numeric) {
                recs.push(`${dlRank[0].competitor_name} domine les telechargements avec ${dlRank[0].downloads || "N/A"}. Renforcer l'ASO (App Store Optimization) et les campagnes d'acquisition.`);
              }
            }

            // Version/update frequency
            const withVersion = currentComparison.filter(c => c.version);
            if (withVersion.length > 1 && brandItem.version) {
              const trendKey = `${store === "playstore" ? "ps" : "as"}_${brandItem.competitor_id}`;
              const brandTrend = trends[trendKey];
              if (brandTrend?.trends?.rating === "down") {
                recs.push(`La note de ${brandName} est en baisse. Analyser les derniers avis pour identifier les points de friction et prioriser les correctifs.`);
              }
            }

            // Top performer highlight
            if (brandRatingIdx === 0) {
              recs.push(`${brandName} est leader en note ${config.label}. Maintenir cet avantage en continuant a repondre aux avis et a publier des mises a jour regulieres.`);
            }

            if (recs.length === 0) return null;

            return (
              <div className="rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50 to-indigo-50 p-6">
                <h2 className="text-base font-semibold text-violet-800 mb-4 flex items-center gap-2">
                  <Sparkles className="h-4 w-4" />
                  Recommandations Applications
                </h2>
                <div className="space-y-3">
                  {recs.map((rec, i) => (
                    <div key={i} className="rounded-xl bg-white/80 border border-violet-100 p-4 text-sm text-violet-900">
                      {rec}
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* Selected Competitor Detail */}
      {selectedCompetitor && hasStoreForSelected && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800">
                <Smartphone className="h-4 w-4 text-slate-600 dark:text-slate-400" />
              </div>
              <div>
                <h3 className="text-sm font-semibold">{selectedComp?.name}</h3>
                <p className="text-[11px] text-muted-foreground">D&eacute;tail {config.label}</p>
              </div>
            </div>
            {storeUrl && (
              <a href={storeUrl} target="_blank" rel="noopener noreferrer"
                className={`flex items-center gap-1 text-[11px] ${config.accent} hover:underline`}>
                <ExternalLink className="h-3 w-3" />
                Voir sur le store
              </a>
            )}
          </div>

          {/* Stats strip */}
          {latestData && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-px rounded-xl bg-border overflow-hidden shadow-sm">
              <div className="bg-card px-5 py-4">
                <div className="text-[11px] text-muted-foreground uppercase tracking-widest">Note</div>
                <div className="mt-2"><StarRating rating={latestData.rating} /></div>
              </div>
              <div className="bg-card px-5 py-4">
                <div className="text-[11px] text-muted-foreground uppercase tracking-widest">Avis</div>
                <div className="text-2xl font-bold mt-1 tabular-nums">{latestData.reviews_count ? formatNumber(latestData.reviews_count) : "\u2014"}</div>
              </div>
              <div className="bg-card px-5 py-4">
                <div className="text-[11px] text-muted-foreground uppercase tracking-widest">
                  {store === "playstore" ? "Downloads" : "Version"}
                </div>
                <div className="text-2xl font-bold mt-1 tabular-nums">
                  {store === "playstore" ? (latestData.downloads || "\u2014") : (latestData.version ? `v${latestData.version}` : "\u2014")}
                </div>
              </div>
              <div className="bg-card px-5 py-4">
                <div className="text-[11px] text-muted-foreground uppercase tracking-widest flex items-center gap-1">
                  <Clock className="h-3 w-3" />Maj
                </div>
                <div className="text-sm font-medium mt-2 tabular-nums">{latestData.recorded_at ? formatDate(latestData.recorded_at) : "\u2014"}</div>
              </div>
            </div>
          )}

          {/* Changelog */}
          {latestData?.changelog && (
            <div className="rounded-2xl border bg-card p-5 space-y-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900">
                  <RefreshCw className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
                </div>
                <h3 className="text-[12px] font-semibold text-foreground">Dernier changelog {latestData.version && `(v${latestData.version})`}</h3>
              </div>
              <p className="text-sm leading-relaxed text-foreground/80 whitespace-pre-wrap">{latestData.changelog}</p>
            </div>
          )}

          {/* History */}
          {appData.length > 1 && (
            <div className="rounded-2xl border bg-card overflow-hidden">
              <div className="px-5 py-3 bg-muted/20 border-b flex items-center gap-2.5">
                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-100 dark:bg-slate-800">
                  <BarChart3 className="h-3.5 w-3.5 text-slate-600 dark:text-slate-400" />
                </div>
                <span className="text-[12px] font-semibold text-foreground">Historique</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-muted/30">
                      <th className="text-left text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Date</th>
                      <th className="text-left text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Version</th>
                      <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Note</th>
                      <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Avis</th>
                      {store === "playstore" && (
                        <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Downloads</th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {appData.map((entry, i) => (
                      <tr key={entry.id} className={`border-t transition-colors hover:bg-muted/30 ${i === 0 ? "bg-emerald-50/50 dark:bg-emerald-950/20" : ""}`}>
                        <td className="px-4 py-3 text-sm tabular-nums">{formatDate(entry.recorded_at)}</td>
                        <td className="px-4 py-3">
                          {entry.version ? (
                            <span className="inline-block text-xs font-medium bg-muted px-2 py-0.5 rounded">v{entry.version}</span>
                          ) : <span className="text-sm text-muted-foreground">&mdash;</span>}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {entry.rating ? (
                            <div className="flex items-center justify-end gap-1">
                              <Star className="h-3 w-3 text-amber-400 fill-amber-400" />
                              <span className="text-sm font-medium tabular-nums">{entry.rating.toFixed(1)}</span>
                            </div>
                          ) : <span className="text-sm text-muted-foreground">&mdash;</span>}
                        </td>
                        <td className="px-4 py-3 text-right text-sm tabular-nums">{entry.reviews_count ? formatNumber(entry.reviews_count) : "\u2014"}</td>
                        {store === "playstore" && (
                          <td className="px-4 py-3 text-right text-sm tabular-nums">{entry.downloads || "\u2014"}</td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// ASO Analysis Component
// ═══════════════════════════════════════════════════════════════════════════════

const ASO_DIMENSIONS = [
  { key: "metadata", label: "Metadata", icon: Search, color: "text-blue-600", bg: "bg-blue-100" },
  { key: "visual", label: "Visuels", icon: Image, color: "text-purple-600", bg: "bg-purple-100" },
  { key: "rating", label: "Note", icon: Star, color: "text-amber-600", bg: "bg-amber-100" },
  { key: "reviews", label: "Avis", icon: MessageSquare, color: "text-green-600", bg: "bg-green-100" },
  { key: "freshness", label: "Fraicheur", icon: Zap, color: "text-cyan-600", bg: "bg-cyan-100" },
];

function AsoScoreRing({ score, size = 52 }: { score: number; size?: number }) {
  const radius = (size - 6) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;
  const color = score >= 70 ? "#16a34a" : score >= 50 ? "#ca8a04" : score >= 30 ? "#ea580c" : "#dc2626";

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="currentColor" strokeWidth={4} className="text-muted/20" />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={color} strokeWidth={4}
          strokeDasharray={circumference} strokeDashoffset={circumference - progress}
          strokeLinecap="round" className="transition-all duration-700" />
      </svg>
      <span className="absolute text-xs font-bold tabular-nums" style={{ color }}>{Math.round(score)}</span>
    </div>
  );
}

function AsoScoreBar({ score, label, detail }: { score: number; label: string; detail?: string }) {
  const color = score >= 70 ? "bg-emerald-500" : score >= 50 ? "bg-yellow-500" : score >= 30 ? "bg-orange-500" : "bg-red-500";
  const textColor = score >= 70 ? "text-emerald-700" : score >= 50 ? "text-yellow-700" : score >= 30 ? "text-orange-700" : "text-red-600";

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-foreground">{label}</span>
        <span className={`text-xs font-bold tabular-nums ${textColor}`}>{Math.round(score)}/100</span>
      </div>
      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${Math.max(score, 2)}%` }} />
      </div>
      {detail && <p className="text-[10px] text-muted-foreground">{detail}</p>}
    </div>
  );
}

function AsoSection({ data, brandName }: { data: any; brandName: string | null }) {
  const [expandedCompetitor, setExpandedCompetitor] = useState<number | null>(null);
  const [selectedStore, setSelectedStore] = useState<"playstore" | "appstore" | "both">("both");

  const competitors = data.competitors || [];
  const recommendations = data.recommendations || [];

  const dimensionLeaders = useMemo(() => {
    const leaders: Record<string, { name: string; score: number }> = {};
    for (const dim of ASO_DIMENSIONS) {
      let best = { name: "", score: 0 };
      for (const comp of competitors) {
        const ps = comp.playstore?.[`${dim.key}_score`]?.total || 0;
        const as_ = comp.appstore?.[`${dim.key}_score`]?.total || 0;
        const avg = comp.playstore && comp.appstore ? (ps + as_) / 2 : (ps || as_);
        if (avg > best.score) best = { name: comp.competitor_name, score: avg };
      }
      leaders[dim.key] = best;
    }
    return leaders;
  }, [competitors]);

  return (
    <div className="space-y-3">
      {/* ASO Comparison Matrix (merged header + table) */}
      <div className="rounded-2xl border bg-card overflow-hidden">
        <div className="px-4 py-2.5 border-b bg-gradient-to-r from-violet-600 to-indigo-600 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Target className="h-3.5 w-3.5 text-white" />
            <span className="text-xs font-semibold text-white">Analyse ASO</span>
          </div>
          <div className="flex items-center gap-0.5 p-0.5 rounded-full bg-white/10">
            {(["both", "playstore", "appstore"] as const).map((s) => (
              <button key={s} onClick={() => setSelectedStore(s)}
                className={`px-2.5 py-0.5 rounded-full text-[10px] font-medium transition-all ${selectedStore === s ? "bg-white/20 text-white" : "text-white/50 hover:text-white/70"}`}>
                {s === "both" ? "Les deux" : s === "playstore" ? "Play Store" : "App Store"}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px]">
            <thead>
              <tr className="bg-muted/30">
                <th className="text-left text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-3 py-2">Concurrent</th>
                {ASO_DIMENSIONS.map(d => (
                  <th key={d.key} className="text-center text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-2 py-2">
                    <div className="flex items-center justify-center gap-1">
                      <d.icon className="h-3 w-3" />
                      {d.label}
                    </div>
                  </th>
                ))}
                <th className="text-center text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-3 py-2">Global</th>
              </tr>
            </thead>
            <tbody>
              {competitors.map((comp: any, i: number) => {
                const storeData = selectedStore === "playstore" ? comp.playstore
                  : selectedStore === "appstore" ? comp.appstore
                  : null;
                const isBrandComp = comp.is_brand;
                const overallScore = selectedStore === "both" ? comp.aso_score_avg
                  : storeData?.aso_score || 0;

                return (
                  <tr key={comp.competitor_id}
                    onClick={() => setExpandedCompetitor(expandedCompetitor === comp.competitor_id ? null : comp.competitor_id)}
                    className={`border-t transition-colors cursor-pointer hover:bg-muted/30 ${isBrandComp ? "bg-violet-50/50 dark:bg-violet-950/20" : i === 0 ? "bg-emerald-50/30 dark:bg-emerald-950/10" : ""} ${expandedCompetitor === comp.competitor_id ? "ring-1 ring-inset ring-violet-300 dark:ring-violet-700" : ""}`}>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1.5">
                        <span className={`flex items-center justify-center h-4.5 w-4.5 rounded-full text-[9px] font-bold shrink-0 ${i < 3 ? ["bg-amber-400 text-amber-950", "bg-slate-300 text-slate-700", "bg-orange-300 text-orange-800"][i] : "bg-muted text-muted-foreground"}`}>{i + 1}</span>
                        {(comp.playstore?.icon_url || comp.appstore?.icon_url) && (
                          <img src={comp.playstore?.icon_url || comp.appstore?.icon_url} alt="" className="h-5 w-5 rounded shrink-0" />
                        )}
                        <span className="text-xs font-medium truncate">{comp.competitor_name}</span>
                        {isBrandComp && <span className="text-[8px] font-bold uppercase px-1 py-0.5 rounded bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-300 shrink-0">Vous</span>}
                      </div>
                    </td>
                    {ASO_DIMENSIONS.map(d => {
                      let score: number;
                      if (selectedStore === "both") {
                        const ps = comp.playstore?.[`${d.key}_score`]?.total || 0;
                        const as_ = comp.appstore?.[`${d.key}_score`]?.total || 0;
                        score = comp.playstore && comp.appstore ? (ps + as_) / 2 : (ps || as_);
                      } else {
                        score = storeData?.[`${d.key}_score`]?.total || 0;
                      }
                      const isLeader = dimensionLeaders[d.key]?.name === comp.competitor_name;
                      const bgColor = score >= 70 ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                        : score >= 50 ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"
                        : score >= 30 ? "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
                        : "bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400";

                      return (
                        <td key={d.key} className="px-2 py-2 text-center">
                          <span className={`inline-flex items-center gap-0.5 text-[11px] font-bold tabular-nums px-1.5 py-0.5 rounded-md ${bgColor}`}>
                            {Math.round(score)}
                            {isLeader && <Crown className="h-2.5 w-2.5 text-amber-500" />}
                          </span>
                        </td>
                      );
                    })}
                    <td className="px-3 py-2 text-center">
                      <AsoScoreRing score={overallScore} size={32} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Expanded Competitor Detail (inline under table) */}
      {expandedCompetitor && (() => {
        const comp = competitors.find((c: any) => c.competitor_id === expandedCompetitor);
        if (!comp) return null;
        const stores = [
          comp.playstore && { key: "playstore", label: "Play Store", data: comp.playstore, gradient: "from-green-500 to-emerald-600" },
          comp.appstore && { key: "appstore", label: "App Store", data: comp.appstore, gradient: "from-blue-500 to-blue-600" },
        ].filter(Boolean) as any[];

        return (
          <div className="rounded-xl border bg-card p-3 space-y-3">
            <div className="flex items-center gap-2">
              <Eye className="h-3.5 w-3.5 text-violet-600 dark:text-violet-400" />
              <h3 className="text-xs font-semibold">{comp.competitor_name} — Detail ASO</h3>
            </div>

            <div className={`grid gap-3 ${stores.length > 1 ? "sm:grid-cols-2" : ""}`}>
              {stores.map((store: any) => (
                <div key={store.key} className="rounded-lg border p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <div className={`h-1.5 w-1.5 rounded-full bg-gradient-to-r ${store.gradient}`} />
                      <span className="text-[11px] font-semibold">{store.label}</span>
                      <span className="text-[10px] text-muted-foreground">v{store.data.version || "?"}</span>
                    </div>
                    <AsoScoreRing score={store.data.aso_score || 0} size={28} />
                  </div>

                  <div className="space-y-1.5">
                    <AsoScoreBar score={store.data.metadata_score?.total || 0} label="Metadata"
                      detail={`Titre: ${store.data.metadata_score?.title_length_detail || "?"} | Desc: ${store.data.metadata_score?.description_length_detail || "?"}`} />
                    <AsoScoreBar score={store.data.visual_score?.total || 0} label="Visuels"
                      detail={`${store.data.visual_score?.screenshot_count_detail || "?"} | ${store.data.visual_score?.video_present_detail || "?"}`} />
                    <AsoScoreBar score={store.data.rating_score?.total || 0} label="Note"
                      detail={store.data.rating_score?.rating_detail || "?"} />
                    <AsoScoreBar score={store.data.reviews_score?.total || 0} label="Avis"
                      detail={store.data.reviews_score?.volume_detail || "?"} />
                    <AsoScoreBar score={store.data.freshness_score?.total || 0} label="Fraicheur"
                      detail={store.data.freshness_score?.freshness_detail || "?"} />
                  </div>

                  <div className="flex flex-wrap gap-1 pt-1.5 border-t">
                    {store.data.screenshot_count != null && (
                      <span className="inline-flex items-center gap-0.5 text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">
                        <Image className="h-2.5 w-2.5" />{store.data.screenshot_count} screenshots
                      </span>
                    )}
                    {store.data.has_video && (
                      <span className="inline-flex items-center gap-0.5 text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                        <CheckCircle2 className="h-2.5 w-2.5" />Video
                      </span>
                    )}
                    {store.data.has_video === false && (
                      <span className="inline-flex items-center gap-0.5 text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-red-100 text-red-600">
                        <XCircle className="h-2.5 w-2.5" />Pas de video
                      </span>
                    )}
                    {store.data.has_header_image && (
                      <span className="inline-flex items-center gap-0.5 text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                        <CheckCircle2 className="h-2.5 w-2.5" />Feature graphic
                      </span>
                    )}
                    {store.data.content_rating && (
                      <span className="inline-flex items-center gap-0.5 text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">
                        <Shield className="h-2.5 w-2.5" />{store.data.content_rating}
                      </span>
                    )}
                    {store.data.ad_supported && (
                      <span className="text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700">Pubs</span>
                    )}
                    {store.data.in_app_purchases && (
                      <span className="text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700">Achats in-app</span>
                    )}
                  </div>

                  {store.data.rating_score?.histogram && (
                    <div className="pt-1.5 border-t space-y-1">
                      <span className="text-[9px] font-semibold text-muted-foreground uppercase tracking-widest">Distribution des notes</span>
                      {[5, 4, 3, 2, 1].map((star) => {
                        const hist = store.data.rating_score.histogram;
                        const total = hist.reduce((a: number, b: number) => a + b, 0);
                        const count = hist[star - 1] || 0;
                        const pct = total > 0 ? (count / total) * 100 : 0;
                        return (
                          <div key={star} className="flex items-center gap-1.5">
                            <span className="text-[9px] font-medium text-muted-foreground w-2 text-right">{star}</span>
                            <Star className="h-2 w-2 text-amber-400 fill-amber-400" />
                            <div className="flex-1 h-1 bg-muted rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${star >= 4 ? "bg-emerald-500" : star === 3 ? "bg-yellow-500" : "bg-red-400"}`}
                                style={{ width: `${Math.max(pct, 0.5)}%` }} />
                            </div>
                            <span className="text-[9px] text-muted-foreground tabular-nums w-8 text-right">{pct.toFixed(0)}%</span>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {store.data.screenshot_urls?.length > 0 && (
                    <div className="pt-1.5 border-t space-y-1">
                      <span className="text-[9px] font-semibold text-muted-foreground uppercase tracking-widest">Screenshots</span>
                      <div className="flex gap-1.5 overflow-x-auto pb-1">
                        {store.data.screenshot_urls.map((url: string, idx: number) => (
                          <img key={idx} src={url} alt={`Screenshot ${idx + 1}`}
                            className="h-20 rounded-md border shadow-sm shrink-0 object-cover" />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      {/* ASO Recommendations (expert) */}
      {recommendations.length > 0 && (
        <div className="rounded-xl border border-violet-200 bg-gradient-to-r from-violet-50 to-indigo-50 dark:from-violet-950/30 dark:to-indigo-950/30 dark:border-violet-800 p-3 space-y-2">
          <div className="flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-violet-600" />
            <h3 className="text-xs font-semibold text-violet-800 dark:text-violet-200">Recommandations ASO Expert</h3>
            <span className="text-[9px] text-violet-500 dark:text-violet-400">{recommendations.length} axes d&apos;amelioration</span>
          </div>
          <div className="space-y-2">
            {recommendations.map((rec: any, i: number) => {
              const points = (rec.advice as string).split(" | ").filter(Boolean);
              return (
                <div key={i} className={`rounded-lg bg-white/80 dark:bg-white/5 border px-3 py-2.5 ${rec.priority === "high" ? "border-red-200 dark:border-red-800" : rec.priority === "low" ? "border-emerald-200 dark:border-emerald-800" : "border-violet-100 dark:border-violet-800"}`}>
                  <div className="flex items-center gap-2 mb-1.5">
                    {rec.priority === "high" ? <AlertTriangle className="h-3 w-3 text-red-600 shrink-0" /> : rec.priority === "low" ? <Sparkles className="h-3 w-3 text-emerald-600 shrink-0" /> : <Info className="h-3 w-3 text-amber-600 shrink-0" />}
                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{rec.dimension}</span>
                    <span className={`text-[9px] font-bold tabular-nums px-1 py-0.5 rounded ${rec.priority === "high" ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" : rec.priority === "low" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"}`}>
                      {Math.round(rec.score)}/100
                    </span>
                    <span className={`text-[8px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded-full ${rec.priority === "high" ? "bg-red-600 text-white" : rec.priority === "low" ? "bg-emerald-600 text-white" : "bg-amber-500 text-white"}`}>
                      {rec.priority === "high" ? "Critique" : rec.priority === "low" ? "Avance" : "Important"}
                    </span>
                  </div>
                  <ul className="space-y-1">
                    {points.map((point: string, j: number) => (
                      <li key={j} className="flex items-start gap-1.5 text-[11px] text-foreground/80 leading-relaxed">
                        <span className="text-violet-400 mt-0.5 shrink-0">&#8250;</span>
                        <span>{point.trim()}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
