"use client";

import { useEffect, useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import {
  competitorsAPI,
  playstoreAPI,
  appstoreAPI,
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
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [periodDays, setPeriodDays] = useState<PeriodDays>(7);
  const [initialLoad, setInitialLoad] = useState(true);

  useEffect(() => {
    async function loadAll() {
      try {
        const [comp, ps, as_, brand] = await Promise.allSettled([
          competitorsAPI.list(),
          playstoreAPI.getComparison(periodDays),
          appstoreAPI.getComparison(periodDays),
          brandAPI.getProfile(),
        ]);
        const allComp = comp.status === "fulfilled" ? comp.value : [];
        const withApps = allComp.filter((c) => c.playstore_app_id || c.appstore_app_id);
        setCompetitors(withApps);
        if (ps.status === "fulfilled") setPsComparison(ps.value);
        if (as_.status === "fulfilled") setAsComparison(as_.value);
        if (brand.status === "fulfilled") setBrandName((brand.value as any).company_name || null);
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
                {crossStoreData.map((c, i) => (
                  <tr key={c.id} className={`border-t border-white/10 ${isBrand(c.name) ? "bg-violet-500/15" : ""}`}>
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
                ))}
              </tbody>
            </table>
          </div>
        </div>
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

              return (
                <button
                  key={c.competitor_id}
                  onClick={() => setSelectedCompetitor(c.competitor_id)}
                  className={`rounded-xl border p-4 transition-all hover:shadow-md text-left ${
                    brand ? "ring-2 ring-violet-500/40 bg-violet-50/30 dark:bg-violet-950/20" :
                    isSelected ? `${config.lightBg} ${config.border}` :
                    i === 0 ? `${config.lightBg} ${config.border}` : "bg-card"
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
                      <div className={`h-full rounded-full transition-all duration-700 ${i === 0 ? `bg-gradient-to-r ${config.gradient}` : "bg-slate-300 dark:bg-slate-600"}`}
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
                    return (
                      <tr key={c.competitor_id} className={`border-t transition-colors hover:bg-muted/30 ${brand ? "bg-violet-50/50 dark:bg-violet-950/20" : i === 0 ? config.lightBg : ""}`}>
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
